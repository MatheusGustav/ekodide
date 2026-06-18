"""O portal web: o aparelho SEM Ekodide manda/baixa pelo navegador, gateado por PIN.
Sobe um recebedor de verdade e bate nele como um navegador faria (urllib)."""
import threading
import urllib.error
import urllib.request
from http.server import ThreadingHTTPServer

import pytest

from ekodide.recebedor import criar_handler

SEGREDO = "s3gr3d0"
PIN = "pin-de-teste"


@pytest.fixture()
def web(tmp_path):
    base = tmp_path / "recebidos"
    base.mkdir()
    srv = ThreadingHTTPServer(("127.0.0.1", 0), criar_handler(base.resolve(), SEGREDO, PIN, web=True))
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    host, porta = srv.server_address
    yield f"http://{host}:{porta}", base
    srv.shutdown()


def _get(url):
    with urllib.request.urlopen(url) as r:
        return r.status, r.read()


def test_pagina_sem_pin_pede_pin(web):
    url, _ = web
    _, corpo = _get(f"{url}/")
    assert b"Digite o PIN" in corpo


def test_pagina_com_pin_mostra_envio_e_download(web):
    url, _ = web
    _, corpo = _get(f"{url}/?k={PIN}")
    texto = corpo.decode("utf-8")
    assert "Enviar pra cá" in texto and "Baixar daqui" in texto


def test_upload_pelo_navegador_grava_o_arquivo(web):
    url, base = web
    req = urllib.request.Request(
        f"{url}/web/upload?k={PIN}&nome=ola.txt", data=b"vindo do navegador", method="POST"
    )
    with urllib.request.urlopen(req) as r:
        assert r.status == 200
    assert (base / "ola.txt").read_bytes() == b"vindo do navegador"


def test_download_pelo_navegador_baixa_o_arquivo(web):
    url, base = web
    (base / "baixe.txt").write_bytes(b"conteudo pra baixar")
    _, corpo = _get(f"{url}/web/download?nome=baixe.txt&k={PIN}")
    assert corpo == b"conteudo pra baixar"


def test_pin_errado_barra_upload_e_download(web):
    url, base = web
    (base / "segredo.txt").write_bytes(b"x")
    # upload com PIN errado
    req = urllib.request.Request(f"{url}/web/upload?k=errado&nome=x.txt", data=b"x", method="POST")
    with pytest.raises(urllib.error.HTTPError) as e1:
        urllib.request.urlopen(req)
    assert e1.value.code == 403
    # download com PIN errado
    with pytest.raises(urllib.error.HTTPError) as e2:
        urllib.request.urlopen(f"{url}/web/download?nome=segredo.txt&k=errado")
    assert e2.value.code == 403


def test_download_nao_escapa_da_pasta(web):
    url, _ = web
    with pytest.raises(urllib.error.HTTPError) as e:
        urllib.request.urlopen(f"{url}/web/download?nome=../../etc/passwd&k={PIN}")
    assert e.value.code == 404


def test_web_desligado_nao_serve_portal(tmp_path):
    base = tmp_path / "r"
    base.mkdir()
    srv = ThreadingHTTPServer(("127.0.0.1", 0), criar_handler(base.resolve(), SEGREDO, None, web=False))
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    host, porta = srv.server_address
    try:
        with pytest.raises(urllib.error.HTTPError) as e:
            urllib.request.urlopen(f"http://{host}:{porta}/")
        assert e.value.code == 404
    finally:
        srv.shutdown()
