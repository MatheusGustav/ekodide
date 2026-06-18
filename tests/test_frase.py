"""A frase-código: gera segredo forte e digitável, sem repetir palavra fraca."""
import pytest

from ekodide import frase


def test_lista_sem_duplicatas():
    assert len(frase.PALAVRAS) == len(set(frase.PALAVRAS))


def test_gera_com_o_tamanho_pedido():
    f = frase.gerar(palavras=6)
    assert len(f.split("-")) == 6
    assert all(p in frase.PALAVRAS for p in f.split("-"))


def test_duas_frases_diferentes():
    # sorteio forte: praticamente impossível sair igual com 6 palavras
    assert frase.gerar() != frase.gerar()


def test_recusa_frase_curta_demais():
    with pytest.raises(ValueError):
        frase.gerar(palavras=3)


def test_separador_custom():
    assert " " in frase.gerar(palavras=4, separador=" ")
