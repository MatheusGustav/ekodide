"""A config (~/.config/ekodide/config.json): grava com cadeado, lê segredo e
traduz nomes de destino em URLs."""
import stat

import pytest

from ekodide import config


@pytest.fixture(autouse=True)
def config_isolada(tmp_path, monkeypatch):
    """Joga a config pra uma pasta temporária e limpa os segredos do ambiente."""
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path))
    monkeypatch.delenv("EKODIDE_SEGREDO", raising=False)
    monkeypatch.delenv("OROGBO_SEGREDO", raising=False)


def test_salva_com_cadeado_600(tmp_path):
    arq = config.salvar({"segredo": "x"})
    modo = stat.S_IMODE(arq.stat().st_mode)
    assert modo == 0o600  # só o dono lê — tem segredo dentro


def test_ida_e_volta():
    config.salvar({"segredo": "abc", "destinos": {"pc": "http://h:1"}})
    cfg = config.carregar()
    assert cfg["segredo"] == "abc" and cfg["destinos"]["pc"] == "http://h:1"


def test_segredo_do_ambiente_vence(monkeypatch):
    config.salvar({"segredo": "da-config"})
    monkeypatch.setenv("EKODIDE_SEGREDO", "do-ambiente")
    assert config.segredo() == "do-ambiente"


def test_segredo_cai_pra_config():
    config.salvar({"segredo": "da-config"})
    assert config.segredo() == "da-config"


def test_sem_segredo_explica():
    config.salvar({})
    with pytest.raises(config.ErroConfig):
        config.segredo()


def test_destino_desconhecido_explica():
    config.salvar({"destinos": {"pc": "http://h:1"}})
    assert config.url_do_destino("pc") == "http://h:1"
    with pytest.raises(config.ErroConfig):
        config.url_do_destino("marte")
