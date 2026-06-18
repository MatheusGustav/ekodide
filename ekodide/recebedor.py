"""O recebedor do Ekodide: um servidor HTTP leve que ESCUTA e grava o que chega.

É a outra ponta do carteiro. Confere o lacre (HMAC) de cada envio e grava com a
caixa postal (cercado, sem travessia, sem sobrescrever, remontando pedaços). Não
sabe nada de "PC" ou "celular": recebe a pasta destino e o segredo prontos.

Duas portas de entrada:
  - /receber           Ekodide-pra-Ekodide, lacrado (HMAC). É a porta forte.
  - portal web (--web) pro aparelho SEM Ekodide: navegador manda/baixa arquivo,
    protegido só por um PIN (sem o lacre). Porta mais fraca, opcional.

Uso direto:
    from ekodide import recebedor
    recebedor.servir(base=Path("~/Downloads").expanduser(), segredo="...")
"""
from __future__ import annotations

import binascii
import hmac
import shutil
import socket
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, unquote, urlparse

from . import portal
from .caixa_postal import caminho_leitura, gravar_fluxo, gravar_recebido
from .lacre import TrancaInvalida, desempacotar, empacotar

# Teto do corpo: base64 incha ~33%, então ~32 MB aqui ≈ ~24 MB de arquivo real.
# Arquivo maior chega picado em pedaços (cada pedaço cabe nisto).
LIMITE_CORPO = 32 * 1024 * 1024


def criar_handler(base: Path, segredo: str, token: str | None = None, web: bool = False) -> type[BaseHTTPRequestHandler]:
    """Fabrica um Handler amarrado a esta pasta e este segredo (sem estado global).
    Se `web` e `token`, também serve o portal web (navegador) gateado pelo PIN."""

    class Handler(BaseHTTPRequestHandler):
        # ---- Ekodide-pra-Ekodide (lacrado) + upload do portal web ----
        def do_POST(self) -> None:
            rota = urlparse(self.path)
            if rota.path == "/receber":
                self._receber_lacrado()
            elif web and rota.path == "/web/upload":
                self._web_upload(parse_qs(rota.query))
            else:
                self._texto(404, "rota desconhecida")

        # ---- portal web (navegador): página e downloads ----
        def do_GET(self) -> None:
            if not web:
                self._texto(404, "rota desconhecida")
                return
            rota = urlparse(self.path)
            q = parse_qs(rota.query)
            if rota.path == "/":
                if self._pin_ok(q):
                    self._html(portal.pagina(token, _listar(base)))
                else:
                    self._html(portal.pagina_pin())
            elif rota.path == "/web/download":
                if not self._pin_ok(q):
                    self._texto(403, "PIN errado")
                else:
                    self._web_download(unquote((q.get("nome") or [""])[0]))
            else:
                self._texto(404, "rota desconhecida")

        def _receber_lacrado(self) -> None:
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

        def _web_upload(self, q: dict) -> None:
            if not self._pin_ok(q):
                self._texto(403, "PIN errado")
                return
            nome = unquote((q.get("nome") or [""])[0]) or "arquivo"
            tamanho = int(self.headers.get("Content-Length") or 0)
            if tamanho <= 0:
                self._texto(400, "corpo vazio")
                return
            try:
                alvo = gravar_fluxo(nome, self.rfile, tamanho, base)
            except (ValueError, OSError) as erro:
                self._texto(400, f"upload inválido: {erro}")
                return
            self._texto(200, f"recebido: {alvo.name}")

        def _web_download(self, nome: str) -> None:
            try:
                alvo = caminho_leitura(nome, base)
            except (ValueError, FileNotFoundError):
                self._texto(404, "arquivo não encontrado")
                return
            self.send_response(200)
            self.send_header("Content-Type", "application/octet-stream")
            self.send_header("Content-Disposition", f'attachment; filename="{alvo.name}"')
            self.send_header("Content-Length", str(alvo.stat().st_size))
            self.end_headers()
            with alvo.open("rb") as f:
                shutil.copyfileobj(f, self.wfile)

        def _pin_ok(self, q: dict) -> bool:
            dado = (q.get("k") or [""])[0]
            return bool(token) and hmac.compare_digest(dado, token)

        def _html(self, pagina_html: str) -> None:
            dados = pagina_html.encode("utf-8")
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Content-Length", str(len(dados)))
            self.end_headers()
            self.wfile.write(dados)

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


def _listar(base: Path) -> list[str]:
    """Os arquivos já recebidos (caminho relativo à base), pra lista de download."""
    base = base.resolve()
    return sorted(str(p.relative_to(base)) for p in base.rglob("*") if p.is_file())


def _ip_lan() -> str | None:
    """Descobre o IP desta máquina na LAN (sem mandar pacote — só consulta a rota)."""
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        s.connect(("8.8.8.8", 80))
        return s.getsockname()[0]
    except OSError:
        return None
    finally:
        s.close()


def servir(
    base: Path, segredo: str, host: str = "127.0.0.1", porta: int = 8778,
    web: bool = False, token: str | None = None,
) -> None:
    """Sobe o recebedor e bloqueia até Ctrl-C. Grava em `base`, lacrado com `segredo`.
    Com `web=True`, também sobe o portal web (navegador) protegido por `token` (PIN)."""
    base = Path(base).expanduser()
    base.mkdir(parents=True, exist_ok=True)
    if web and not token:
        import secrets
        token = secrets.token_urlsafe(6)
    servidor = ThreadingHTTPServer((host, porta), criar_handler(base.resolve(), segredo, token, web))
    onde = "só nesta máquina (localhost)" if host == "127.0.0.1" else "ABERTA na sua rede"
    print(f"Recebedor Ekodide ouvindo em {host}:{porta} — {onde}. Destino: {base}")
    if host != "127.0.0.1":
        print("  aviso: sem TLS, o conteúdo dos arquivos trafega visível na LAN.")
    if web:
        ip = (_ip_lan() if host != "127.0.0.1" else "127.0.0.1") or host
        print(f"  Portal web (navegador): http://{ip}:{porta}/?k={token}   — PIN: {token}")
        print("  abra esse link no navegador do outro aparelho (ou só o IP e digite o PIN).")
        print("  o portal é protegido só por PIN (sem o lacre forte) — use em rede de confiança.")
    try:
        servidor.serve_forever()
    except KeyboardInterrupt:
        print("\nrecebedor desligado.")
        servidor.shutdown()
