"""O recebedor do Ekodide: um servidor HTTP leve que ESCUTA e grava o que chega.

É a outra ponta do carteiro. Confere o lacre (HMAC) de cada envio e grava com a
caixa postal (cercado, sem travessia, sem sobrescrever, remontando pedaços). Não
sabe nada de "PC" ou "celular": recebe a pasta destino e o segredo prontos.

Uso direto:
    from ekodide import recebedor
    recebedor.servir(base=Path("~/Downloads").expanduser(), segredo="...")
"""
from __future__ import annotations

import binascii
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

from .caixa_postal import gravar_recebido
from .lacre import TrancaInvalida, desempacotar, empacotar

# Teto do corpo: base64 incha ~33%, então ~32 MB aqui ≈ ~24 MB de arquivo real.
# Arquivo maior chega picado em pedaços (cada pedaço cabe nisto).
LIMITE_CORPO = 32 * 1024 * 1024


def criar_handler(base: Path, segredo: str) -> type[BaseHTTPRequestHandler]:
    """Fabrica um Handler amarrado a esta pasta e este segredo (sem estado global)."""

    class Handler(BaseHTTPRequestHandler):
        def do_POST(self) -> None:
            if self.path != "/receber":
                self._texto(404, "rota desconhecida")
                return
            tamanho = int(self.headers.get("Content-Length") or 0)
            if tamanho <= 0 or tamanho > LIMITE_CORPO:
                self._texto(400, "corpo ausente ou grande demais")
                return
            corpo = self.rfile.read(tamanho)

            # 1) LACRE: nada é gravado sem a assinatura bater.
            try:
                carga = desempacotar(corpo, segredo)
            except TrancaInvalida as erro:
                self._texto(401, f"recusado pela tranca: {erro}")
                return

            # 2) GRAVA, com o nome cercado na pasta permitida.
            try:
                alvo = gravar_recebido(carga, base)
            except (KeyError, ValueError, binascii.Error, OSError) as erro:
                self._texto(400, f"envio inválido: {erro}")
                return

            # 3) Confirma assinado: o destino (último pedaço / arquivo inteiro), ou
            #    vazio enquanto um grande ainda está sendo montado.
            selada = empacotar({"ok": True, "destino": str(alvo) if alvo else ""}, segredo)
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


def servir(base: Path, segredo: str, host: str = "127.0.0.1", porta: int = 8778) -> None:
    """Sobe o recebedor e bloqueia até Ctrl-C. Grava em `base`, lacrado com `segredo`."""
    base = Path(base).expanduser()
    base.mkdir(parents=True, exist_ok=True)
    servidor = ThreadingHTTPServer((host, porta), criar_handler(base.resolve(), segredo))
    onde = "só nesta máquina (localhost)" if host == "127.0.0.1" else "ABERTA na sua rede"
    print(f"Recebedor Ekodide ouvindo em {host}:{porta} — {onde}. Destino: {base}")
    if host != "127.0.0.1":
        print("  aviso: sem TLS, o conteúdo dos arquivos trafega visível na LAN.")
    try:
        servidor.serve_forever()
    except KeyboardInterrupt:
        print("\nrecebedor desligado.")
        servidor.shutdown()
