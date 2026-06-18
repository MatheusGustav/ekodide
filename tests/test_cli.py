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


def test_pair_gera_frase_e_a_outra_ponta_recebe(capsys):
    # ponta A gera: a frase fica guardada como segredo e aparece na saída
    assert cli.main(["pair"]) == 0
    saida = capsys.readouterr().out
    assert "ekodide pair " in saida
    frase_gerada = config.carregar()["segredo"]
    assert frase_gerada in saida

    # ponta B recebe a MESMA frase: os dois ficam com o segredo idêntico
    assert cli.main(["pair", frase_gerada]) == 0
    assert config.carregar()["segredo"] == frase_gerada


def test_config_nome_grava(capsys):
    assert cli.main(["config", "nome", "meu-pc"]) == 0
    assert config.carregar()["nome"] == "meu-pc"


def test_normalizar_url_aceita_ip_cru_ip_porta_e_url():
    assert cli._normalizar_url("192.168.0.10") == "http://192.168.0.10:8778"
    assert cli._normalizar_url("192.168.0.10:9000") == "http://192.168.0.10:9000"
    assert cli._normalizar_url("http://192.168.0.10:8778") == "http://192.168.0.10:8778"
    assert cli._normalizar_url("  ") is None


def test_config_destino_com_url_explicita_ainda_funciona():
    assert cli.main(["config", "destino", "pc", "http://10.0.0.5:8778"]) == 0
    assert config.carregar()["destinos"]["pc"] == "http://10.0.0.5:8778"


def test_config_destino_escolhendo_da_rede(monkeypatch, capsys):
    # finge que a descoberta achou dois aparelhos e que o usuário digitou "2"
    achados = [
        {"nome": "galaxy", "ip": "192.168.0.9", "porta": 8778},
        {"nome": "note", "ip": "192.168.0.20", "porta": 8778},
    ]
    monkeypatch.setattr(cli.vizinhanca, "procurar", lambda *a, **k: achados)
    monkeypatch.setattr(cli, "_perguntar", lambda prompt: "2")
    assert cli.main(["config", "destino", "celular"]) == 0
    assert config.carregar()["destinos"]["celular"] == "http://192.168.0.20:8778"


def test_config_destino_nada_na_rede_cancela(monkeypatch, capsys):
    # sem ninguém anunciando, não há o que cadastrar: cancela e ensina a abrir a caixa
    monkeypatch.setattr(cli.vizinhanca, "procurar", lambda *a, **k: [])
    assert cli.main(["config", "destino", "tv"]) == 1
    assert "tv" not in config.carregar().get("destinos", {})
    assert "caixa aberta" in capsys.readouterr().out


def test_config_destino_escolha_invalida_cancela(monkeypatch):
    monkeypatch.setattr(cli.vizinhanca, "procurar", lambda *a, **k: [
        {"nome": "x", "ip": "192.168.0.5", "porta": 8778},
    ])
    monkeypatch.setattr(cli, "_perguntar", lambda prompt: "9")  # fora da faixa
    assert cli.main(["config", "destino", "tv"]) == 1
    assert "tv" not in config.carregar().get("destinos", {})
