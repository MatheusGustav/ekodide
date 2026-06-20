"""O recebedor do Ekodide: um servidor HTTP leve que ESCUTA e grava o que chega.

É a outra ponta do carteiro. Confere o lacre (HMAC) de cada envio e grava com a
caixa postal (cercado, sem travessia, sem sobrescrever, remontando pedaços). Não
sabe nada de "PC" ou "celular": recebe a pasta destino e o segredo prontos.

Uso direto:
    from ekodide import recebedor
    recebedor.servir(base=Path("~/Downloads").expanduser(), segredo="...")
"""
from __future__ import annotations

import base64
import binascii
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

from cryptography.exceptions import InvalidTag

from . import acervo
from .caixa_postal import gravar_recebido, progresso_de
from .cofre import cifrar, decifrar
from .lacre import TrancaInvalida, desempacotar, empacotar

# Teto do corpo: base64 incha ~33%, então ~32 MB aqui ≈ ~24 MB de arquivo real.
# Arquivo maior chega picado em pedaços (cada pedaço cabe nisto).
LIMITE_CORPO = 32 * 1024 * 1024


def criar_handler(
    base: Path, segredo: str, compartilhar: Path | None = None
) -> type[BaseHTTPRequestHandler]:
    """Fabrica um Handler amarrado a esta pasta e este segredo (sem estado global).

    `compartilhar` é a pasta que o admin pode PUXAR (rotas /listar e /buscar). None
    (padrão) = nada exposto pra leitura: o 'puxar' fica desligado."""

    class Handler(BaseHTTPRequestHandler):
        # HTTP/1.1 mantém a conexão viva entre pedaços (keep-alive): o carteiro
        # reaproveita a mesma porta em vez de reabrir a cada um. Cada resposta já
        # manda Content-Length, então o cliente sabe onde um corpo acaba e o próximo
        # começa — requisito pra reusar a conexão sem embolar.
        protocol_version = "HTTP/1.1"

        def do_POST(self) -> None:
            if self.path == "/receber":
                self._receber()
            elif self.path == "/progresso":
                self._progresso()
            elif self.path == "/listar":
                self._listar()
            elif self.path == "/buscar":
                self._buscar()
            else:
                self._texto(404, "rota desconhecida")

        def _ler_carga(self) -> dict | None:
            """Lê o corpo e abre o lacre. Devolve a carga, ou None (já respondeu o
            erro). Nada acontece sem a assinatura bater."""
            tamanho = int(self.headers.get("Content-Length") or 0)
            if tamanho <= 0 or tamanho > LIMITE_CORPO:
                self._texto(400, "corpo ausente ou grande demais")
                return None
            corpo = self.rfile.read(tamanho)
            try:
                return desempacotar(corpo, segredo)
            except TrancaInvalida as erro:
                self._texto(401, f"recusado pela tranca: {erro}")
                return None

        def _receber(self) -> None:
            carga = self._ler_carga()
            if carga is None:
                return
            # DECIFRA o conteúdo (o cofre) — na rede veio embaralhado. Daqui pra frente
            # a caixa postal lida com o texto-claro, como sempre.
            try:
                cifrado = base64.b64decode(carga["conteudo"], validate=True)
                aberto = base64.b64encode(decifrar(cifrado, segredo)).decode("ascii")
                carga = {**carga, "conteudo": aberto}
            except (KeyError, binascii.Error, InvalidTag) as erro:
                self._texto(400, f"conteúdo não abriu o cofre: {erro}")
                return
            # GRAVA, com o nome cercado na pasta permitida.
            try:
                alvo = gravar_recebido(carga, base)
            except (KeyError, ValueError, binascii.Error, OSError) as erro:
                self._texto(400, f"envio inválido: {erro}")
                return
            # Confirma assinado: o destino (último pedaço / arquivo inteiro), ou vazio
            # enquanto um grande ainda está sendo montado.
            self._selar({"ok": True, "destino": str(alvo) if alvo else ""})

        def _progresso(self) -> None:
            """Diz quantos pedaços contíguos já tem deste arquivo — pro carteiro
            RETOMAR de onde parou em vez de recomeçar do zero."""
            carga = self._ler_carga()
            if carga is None:
                return
            try:
                nome = carga["nome"]
                partes = int(carga["partes"])
                tamanho = int(carga.get("tamanho", -1))
                recebidos = progresso_de(nome, partes, base, tamanho)
            except (KeyError, ValueError) as erro:
                self._texto(400, f"consulta inválida: {erro}")
                return
            self._selar({"recebidos": recebidos})

        def _listar(self) -> None:
            """Diz o que dá pra PUXAR daqui: a lista da pasta compartilhada (vazia se
            este aparelho não compartilha nada). Só responde a quem tem o segredo."""
            if self._ler_carga() is None:  # exige o lacre, mesmo sem usar a carga
                return
            self._selar({"itens": acervo.listar(compartilhar)})

        def _buscar(self) -> None:
            """Entrega UM pedaço de um arquivo da pasta compartilhada, CIFRADO (cofre).
            Recusa se nada é compartilhado ou se o nome tentar escapar da pasta."""
            carga = self._ler_carga()
            if carga is None:
                return
            if compartilhar is None:
                self._texto(403, "este aparelho não compartilha nada (sirva com --compartilhar)")
                return
            try:
                nome = carga["nome"]
                parte = int(carga["parte"])
                partes = int(carga["partes"])
                bruto = acervo.ler_pedaco(nome, compartilhar, parte, partes)
            except (KeyError, ValueError) as erro:
                self._texto(400, f"pedido inválido: {erro}")
                return
            # CIFRA antes de mandar: na rede passa só embaralhado (o cofre), como no /receber.
            cifrado = base64.b64encode(cifrar(bruto, segredo)).decode("ascii")
            self._selar({"nome": nome, "parte": parte, "partes": partes, "conteudo": cifrado})

        def _selar(self, dados: dict) -> None:
            """Responde 200 com o corpo lacrado (assinado com o segredo)."""
            selada = empacotar(dados, segredo)
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(selada)))
            self.end_headers()
            self.wfile.write(selada)

        def _texto(self, codigo: int, msg: str) -> None:
            dados = msg.encode("utf-8")
            self.send_response(codigo)
            self.send_header("Content-Type", "text/plain; charset=utf-8")
            self.send_header("Content-Length", str(len(dados)))
            self.end_headers()
            self.wfile.write(dados)

        def log_message(self, formato: str, *args) -> None:
            print(f"  [recebedor] {self.address_string()} {formato % args}")

    return Handler


def servir(
    base: Path,
    segredo: str,
    host: str = "127.0.0.1",
    porta: int = 8778,
    compartilhar: Path | None = None,
) -> None:
    """Sobe o recebedor e bloqueia até Ctrl-C. Grava em `base`, lacrado com `segredo`.
    `compartilhar` (opcional) é a pasta que o outro lado pode PUXAR; None = puxar off."""
    base = Path(base).expanduser()
    base.mkdir(parents=True, exist_ok=True)
    compartilhar = Path(compartilhar).expanduser().resolve() if compartilhar else None
    servidor = ThreadingHTTPServer(
        (host, porta), criar_handler(base.resolve(), segredo, compartilhar)
    )
    onde = "só nesta máquina (localhost)" if host == "127.0.0.1" else "ABERTA na sua rede"
    print(f"Recebedor Ekodide ouvindo em {host}:{porta} — {onde}. Destino: {base}")
    if compartilhar is not None:
        print(f"  compartilhando pra PUXAR: {compartilhar}")
    if host != "127.0.0.1":
        print("  conteúdo cifrado (AES-256-GCM) com o segredo das pontas — embaralhado na rede.")
    try:
        servidor.serve_forever()
    except KeyboardInterrupt:
        print("\nrecebedor desligado.")
        servidor.shutdown()
