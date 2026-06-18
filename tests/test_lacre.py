"""Testa a fechadura sozinha: segredo certo passa, errado/adulterado/velho falha.
Tudo determinístico — passo o tempo na mão (agora=...), sem relógio nem rede."""
import json

import pytest

from ekodide.lacre import JANELA_SEGUNDOS, TrancaInvalida, desempacotar, empacotar

SEGREDO = "chave-de-teste"
AGORA = 1_000_000


def test_ida_e_volta():
    corpo = empacotar({"nome": "x.txt", "conteudo": "abc"}, SEGREDO, agora=AGORA)
    carga = desempacotar(corpo, SEGREDO, agora=AGORA)
    assert carga["nome"] == "x.txt" and carga["conteudo"] == "abc"


def test_segredo_errado_falha():
    corpo = empacotar({"a": 1}, SEGREDO, agora=AGORA)
    with pytest.raises(TrancaInvalida):
        desempacotar(corpo, "segredo-errado", agora=AGORA)


def test_corpo_adulterado_falha():
    corpo = empacotar({"nome": "a", "conteudo": "x"}, SEGREDO, agora=AGORA)
    envelope = json.loads(corpo)
    envelope["carga"]["conteudo"] = "ADULTERADO"
    adulterado = json.dumps(envelope).encode("utf-8")
    with pytest.raises(TrancaInvalida):
        desempacotar(adulterado, SEGREDO, agora=AGORA)


def test_mensagem_velha_falha():
    corpo = empacotar({"a": 1}, SEGREDO, agora=AGORA)
    with pytest.raises(TrancaInvalida):
        desempacotar(corpo, SEGREDO, agora=AGORA + JANELA_SEGUNDOS + 1)


def test_dentro_da_janela_passa():
    corpo = empacotar({"a": 1}, SEGREDO, agora=AGORA)
    assert desempacotar(corpo, SEGREDO, agora=AGORA + JANELA_SEGUNDOS - 1)["a"] == 1


def test_lixo_malformado_falha():
    with pytest.raises(TrancaInvalida):
        desempacotar(b"isso nao e json", SEGREDO, agora=AGORA)
