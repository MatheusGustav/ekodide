"""O comando 'ekodide' de verdade: config grava, send manda contra um recebedor
vivo, destino errado falha com jeito."""
import threading
from http.server import ThreadingHTTPServer

import pytest

from ekodide import cli, config
from ekodide.recebedor import criar_handler

SEGREDO = "s3gr3d0"


@pytest.fixture(autouse=True)
def ambiente(tmp_path, monkeypatch):
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path / "cfg"))
    monkeypatch.delenv("EKODIDE_SEGREDO", raising=False)
    monkeypatch.delenv("OROGBO_SEGREDO", raising=False)


@pytest.fixture()
def servidor(tmp_path):
    base = tmp_path / "recebidos"
    base.mkdir()
    srv = ThreadingHTTPServer(("127.0.0.1", 0), criar_handler(base.resolve(), SEGREDO))
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    host, porta = srv.server_address
    yield f"http://{host}:{porta}", base
    srv.shutdown()


def test_config_e_send_ponta_a_ponta(servidor, tmp_path, capsys):
    url, base = servidor
    assert cli.main(["config", "segredo", SEGREDO]) == 0
    assert cli.main(["config", "destino", "pc", url]) == 0

    arq = tmp_path / "doc.txt"
    arq.write_bytes(b"conteudo")
    rc = cli.main(["send", str(arq), "--para", "pc", "-m", "print do erro"])

    assert rc == 0
    assert (base / "doc.txt").read_bytes() == b"conteudo"
    saida = capsys.readouterr().out
    assert "Enviei" in saida and "print do erro" in saida
    # o -m foi pro histórico local
    assert (config.caminho().parent / "historico.log").exists()


def test_send_destino_desconhecido_falha(tmp_path, capsys):
    cli.main(["config", "segredo", SEGREDO])
    arq = tmp_path / "x.txt"
    arq.write_bytes(b"a")
    rc = cli.main(["send", str(arq), "--para", "marte"])
    assert rc == 1
    assert "marte" in capsys.readouterr().err


def test_send_arquivo_inexistente_falha(capsys):
    rc = cli.main(["send", "/nao/existe.txt", "--para", "pc"])
    assert rc == 1
    assert "Não achei" in capsys.readouterr().err


def test_config_show_mascara_segredo(capsys):
    cli.main(["config", "segredo", "super-secreto"])
    cli.main(["config", "show"])
    saida = capsys.readouterr().out
    assert "super-secreto" not in saida and "guardado" in saida
