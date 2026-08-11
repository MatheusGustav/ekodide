"""A tomada MCP: casca fina sobre o maquinário, e que nunca estoura na mão do agente.

O transporte já é testado nos outros arquivos (voo, puxar, lacre, cofre). Aqui se
testa só o que a tomada acrescenta: o registro das ferramentas, a tradução do
resultado neutro em frase, e a promessa de que uma falha vira texto de volta em
vez de exceção — um agente não tem como tratar traceback.
"""
import asyncio

import pytest

pytest.importorskip("mcp", reason="a tomada é extra opcional: pip install 'ekodide[agente]'")

from ekodide import buscador, config, tomada, vizinhanca  # noqa: E402


def _envio(ok=True, is_pasta=False, total=1, enviados=1, destino="", falhas=None):
    from types import SimpleNamespace

    return SimpleNamespace(
        ok=ok, is_pasta=is_pasta, total=total, enviados=enviados,
        destino=destino, falhas=falhas or [],
    )


@pytest.fixture
def linha_pronta(monkeypatch):
    """Destino resolvido e segredo na mão — sem tocar na config real nem na rede."""
    monkeypatch.setattr(tomada, "_resolver_destino", lambda nome, descobrir=False: "http://1.2.3.4:8778")
    monkeypatch.setattr(config, "segredo", lambda cfg=None: "frase-de-teste")
    monkeypatch.setattr(config, "carregar", lambda: {"receber": {"dir": "/tmp/recebidos"}})


@pytest.fixture
def sem_config(monkeypatch):
    """A config não está pronta (sem segredo ou sem destino)."""
    def _falta(nome, descobrir=False):
        raise config.ErroConfig("Destino 'celular' não está na config.")

    monkeypatch.setattr(tomada, "_resolver_destino", _falta)


# --- o registro ---------------------------------------------------------------

def _ferramentas():
    return asyncio.run(tomada.servidor.list_tools())


def test_as_cinco_ferramentas_estao_na_tomada():
    nomes = {f.name for f in _ferramentas()}
    assert nomes == {
        "enviar_arquivo", "listar_arquivos", "puxar_arquivo",
        "espiar_arquivo", "aparelhos",
    }


def test_toda_ferramenta_se_explica_pro_agente():
    """Descrição e schema saem da docstring e dos type hints — é por eles que o
    agente decide o que chamar. Ferramenta muda de assinatura sem docstring
    quebra aqui, não em produção."""
    for f in _ferramentas():
        assert f.description and len(f.description) > 40, f.name
        assert f.input_schema["type"] == "object", f.name


def test_o_apelido_do_aparelho_tem_padrao_menos_onde_nao_faz_sentido():
    schemas = {f.name: f.input_schema for f in _ferramentas()}
    assert schemas["enviar_arquivo"]["required"] == ["caminho"]   # 'para' tem padrão
    assert schemas["puxar_arquivo"]["required"] == ["nome"]       # 'de' tem padrão
    assert schemas["aparelhos"].get("required", []) == []


# --- enviar -------------------------------------------------------------------

def test_enviar_arquivo_inexistente_nem_vai_pra_rede(linha_pronta, monkeypatch, tmp_path):
    def _nao_deve_ser_chamado(*a, **k):
        raise AssertionError("foi pra rede com caminho inexistente")

    monkeypatch.setattr(tomada, "enviar", _nao_deve_ser_chamado)
    fala = tomada.enviar_arquivo(str(tmp_path / "sumido.pdf"))
    assert "Não achei nada" in fala


def test_enviar_traduz_o_resultado_neutro(linha_pronta, monkeypatch, tmp_path):
    alvo = tmp_path / "relatorio.pdf"
    alvo.write_text("x", encoding="utf-8")
    monkeypatch.setattr(tomada, "enviar", lambda *a: _envio(destino="/Download/relatorio.pdf"))
    fala = tomada.enviar_arquivo(str(alvo), para="celular")
    assert "Enviei 'relatorio.pdf' pro 'celular'" in fala
    assert "/Download/relatorio.pdf" in fala


def test_enviar_pasta_vazia_nao_mente(linha_pronta, monkeypatch, tmp_path):
    pasta = tmp_path / "vazia"
    pasta.mkdir()
    monkeypatch.setattr(tomada, "enviar", lambda *a: _envio(ok=True, is_pasta=True, total=0, enviados=0))
    assert "está vazia" in tomada.enviar_arquivo(str(pasta))


def test_enviar_que_falha_explica_e_sugere(linha_pronta, monkeypatch, tmp_path):
    alvo = tmp_path / "a.pdf"
    alvo.write_text("x", encoding="utf-8")
    monkeypatch.setattr(tomada, "enviar", lambda *a: _envio(ok=False, enviados=0, falhas=["conexão recusada"]))
    fala = tomada.enviar_arquivo(str(alvo))
    assert "Não consegui enviar" in fala and "conexão recusada" in fala
    assert "ekodide serve" in fala


def test_enviar_que_quebra_vira_frase(linha_pronta, monkeypatch, tmp_path):
    """A promessa da tomada: exceção nunca chega ao agente."""
    alvo = tmp_path / "a.pdf"
    alvo.write_text("x", encoding="utf-8")

    def _quebra(*a):
        raise RuntimeError("a rede sumiu")

    monkeypatch.setattr(tomada, "enviar", _quebra)
    assert "Quebrou no meio do envio" in tomada.enviar_arquivo(str(alvo))


# --- listar -------------------------------------------------------------------

def test_listar_mostra_tamanho_legivel(linha_pronta, monkeypatch):
    monkeypatch.setattr(buscador, "listar", lambda url, seg: [
        {"nome": "a.pdf", "tamanho": 2048}, {"nome": "Fotos/b.png", "tamanho": 15_500_000},
    ])
    fala = tomada.listar_arquivos(de="celular")
    assert "2.0 KB" in fala and "14.8 MB" in fala and "Fotos/b.png" in fala


def test_listar_vazio_diz_o_que_fazer(linha_pronta, monkeypatch):
    monkeypatch.setattr(buscador, "listar", lambda url, seg: [])
    assert "--compartilhar" in tomada.listar_arquivos()


def test_listar_com_o_outro_lado_fora_do_ar(linha_pronta, monkeypatch):
    def _erro(url, seg):
        raise buscador.ErroPuxar("não alcancei a origem")

    monkeypatch.setattr(buscador, "listar", _erro)
    assert "não alcancei a origem" in tomada.listar_arquivos()


# --- puxar --------------------------------------------------------------------

def test_puxar_usa_a_pasta_de_recebimento_da_config(linha_pronta, monkeypatch):
    vistos = {}

    def _puxar(nome, url, segredo, base, tamanho=None):
        vistos["base"] = str(base)
        return True, "/tmp/recebidos/a.pdf"

    monkeypatch.setattr(buscador, "puxar", _puxar)
    fala = tomada.puxar_arquivo("a.pdf", de="celular")
    assert vistos["base"] == "/tmp/recebidos"   # decisão da config, não da tomada
    assert "Salvo em: /tmp/recebidos/a.pdf" in fala


def test_puxar_que_falha_diz_o_motivo(linha_pronta, monkeypatch):
    monkeypatch.setattr(buscador, "puxar", lambda *a, **k: (False, "não está disponível"))
    assert "não está disponível" in tomada.puxar_arquivo("sumido.pdf")


# --- espiar (lê sem gravar) ---------------------------------------------------

def test_espiar_devolve_o_texto_e_avisa_que_nao_gravou(linha_pronta, monkeypatch):
    conteudo = "anotação do celular".encode()
    monkeypatch.setattr(buscador, "espiar", lambda *a, **k: (True, conteudo, len(conteudo)))
    fala = tomada.espiar_arquivo("nota.txt")
    assert "anotação do celular" in fala and "nada foi gravado" in fala


def test_espiar_pede_o_limite_pra_nao_trazer_o_arquivo_todo(linha_pronta, monkeypatch):
    vistos = {}

    def _espiar(nome, url, segredo, limite=None):
        vistos["limite"] = limite
        return True, b"oi", 2

    monkeypatch.setattr(buscador, "espiar", _espiar)
    tomada.espiar_arquivo("nota.txt")
    assert vistos["limite"] == tomada.ESPIADA_MAX


def test_espiar_avisa_quando_cortou(linha_pronta, monkeypatch):
    monkeypatch.setattr(buscador, "espiar", lambda *a, **k: (True, b"a" * tomada.ESPIADA_MAX, 5_000_000))
    fala = tomada.espiar_arquivo("grande.log")
    assert "maior que a espiada" in fala and "4.8 MB" in fala


def test_espiar_apara_acento_partido_no_corte(linha_pronta, monkeypatch):
    partido = "café".encode()[:-1]   # perde o segundo byte do 'é'
    monkeypatch.setattr(buscador, "espiar", lambda *a, **k: (True, partido, 9_000))
    fala = tomada.espiar_arquivo("nota.txt")
    assert "caf" in fala


def test_espiar_binario_disfarcado_recusa(linha_pronta, monkeypatch):
    monkeypatch.setattr(buscador, "espiar", lambda *a, **k: (True, b"\xff\xfe\x00\x01lixo demais", 14))
    fala = tomada.espiar_arquivo("falso.txt")
    assert "não é texto por dentro" in fala and "puxar_arquivo" in fala


def test_espiar_arquivo_vazio(linha_pronta, monkeypatch):
    monkeypatch.setattr(buscador, "espiar", lambda *a, **k: (True, b"", 0))
    assert "está vazio" in tomada.espiar_arquivo("vazio.txt")


# --- aparelhos ----------------------------------------------------------------

def test_aparelhos_lista_apelido_e_url(monkeypatch):
    monkeypatch.setattr(vizinhanca, "procurar", lambda *a, **k: [
        {"nome": "celular", "ip": "192.168.0.9", "porta": 8778},
    ])
    monkeypatch.setattr(vizinhanca, "url_de", lambda a: f"http://{a['ip']}:{a['porta']}")
    fala = tomada.aparelhos()
    assert "celular" in fala and "192.168.0.9" in fala


def test_aparelhos_vazio_explica(monkeypatch):
    monkeypatch.setattr(vizinhanca, "procurar", lambda *a, **k: [])
    assert "ekodide serve" in tomada.aparelhos()


# --- config incompleta: recusa com jeito, nunca estoura -----------------------

@pytest.mark.parametrize("chamada", [
    lambda: tomada.listar_arquivos(),
    lambda: tomada.puxar_arquivo("a.pdf"),
    lambda: tomada.espiar_arquivo("a.txt"),
])
def test_sem_config_recusa_com_jeito(sem_config, chamada):
    fala = chamada()
    assert "não está pronto" in fala and "não está na config" in fala


def test_enviar_sem_config_recusa_depois_de_conferir_o_arquivo(sem_config, tmp_path):
    alvo = tmp_path / "a.pdf"
    alvo.write_text("x", encoding="utf-8")
    assert "não está pronto" in tomada.enviar_arquivo(str(alvo))
