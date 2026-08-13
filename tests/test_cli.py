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


@pytest.fixture()
def sem_teclado(monkeypatch):
    """pair sem ninguém digitando no prompt (Enter mantém o código mostrado)."""
    monkeypatch.setattr(cli, "_perguntar", lambda prompt: "")


def test_pair_sorteia_codigo_e_a_outra_ponta_adota(sem_teclado, capsys):
    from ekodide import frase

    # ponta A sorteia: o segredo canônico fica guardado e a saída mostra o código VESTIDO
    assert cli.main(["pair"]) == 0
    saida = capsys.readouterr().out
    assert "ekodide pair " in saida
    codigo = config.carregar()["segredo"]
    assert codigo == frase.validar(codigo)  # canônico (sem traço, maiúsculo)
    assert frase.formatar(codigo) in saida

    # ponta B digita o código vestido (com traços): guarda o MESMO segredo canônico
    assert cli.main(["pair", frase.formatar(codigo)]) == 0
    assert config.carregar()["segredo"] == codigo


def test_pair_de_novo_mostra_o_mesmo_codigo_pra_somar_aparelho(sem_teclado, capsys):
    from ekodide import frase

    assert cli.main(["pair"]) == 0
    codigo = config.carregar()["segredo"]
    capsys.readouterr()

    # segunda vez NÃO troca o segredo: mostra o atual (somar aparelho sem trocar a rede)
    assert cli.main(["pair"]) == 0
    assert config.carregar()["segredo"] == codigo
    saida = capsys.readouterr().out
    assert frase.formatar(codigo) in saida and "JÁ TEM" in saida

    # --novo sorteia outro e aposenta o antigo
    assert cli.main(["pair", "--novo"]) == 0
    assert config.carregar()["segredo"] != codigo


def test_pair_aposenta_frase_antiga_de_palavras(sem_teclado, capsys):
    from ekodide import frase

    cli.main(["config", "segredo", "casa-vento-rio-azul-pedra-lobo"])
    capsys.readouterr()
    assert cli.main(["pair"]) == 0  # não é código sorteado: sorteia um novo
    novo = config.carregar()["segredo"]
    assert novo == frase.validar(novo)


def test_pair_texto_livre_morre(sem_teclado, capsys):
    # 'definir a própria senha' deixou de existir: só passa código sorteado
    cli.main(["config", "segredo", "segredo-legado"])
    capsys.readouterr()
    assert cli.main(["pair", "minha-senha-esperta"]) == 1
    assert config.carregar()["segredo"] == "segredo-legado"  # intocado
    err = capsys.readouterr().err
    assert "recusado" in err and "SORTEADO" in err


def test_pair_prompt_adota_codigo_de_outra_tela(monkeypatch, capsys):
    from ekodide import frase

    # o prompt estilo login: digitou um código vestido vindo de outra tela, adota ELE
    de_fora = frase.gerar()
    monkeypatch.setattr(cli, "_perguntar", lambda prompt: frase.formatar(de_fora).lower())
    assert cli.main(["pair"]) == 0
    assert config.carregar()["segredo"] == de_fora


def test_pair_sem_extra_qr_mostra_a_receita(sem_teclado, capsys):
    import importlib.util

    if importlib.util.find_spec("qrcode"):
        pytest.skip("extra [qr] instalado — este teste cobre o caminho SEM ele")
    assert cli.main(["pair"]) == 0
    assert "ekodide[qr]" in capsys.readouterr().out


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
