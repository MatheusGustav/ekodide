"""O código de pareamento: sorteado forte, digitável, e o verificador acusa typo na hora."""
import pytest

from ekodide import frase


def test_alfabeto_31_simbolos_sem_confundiveis():
    assert len(frase.ALFABETO) == 31 == len(set(frase.ALFABETO))
    # 0/O e 1/I/L ficam FORA de propósito (parecidos demais numa tela/voz)
    assert not set("0O1IL") & set(frase.ALFABETO)


def test_gera_canonico_11_caracteres_do_alfabeto():
    c = frase.gerar()
    assert len(c) == frase.TAMANHO == 11
    assert all(ch in frase.ALFABETO for ch in c)
    assert frase.validar(c) == c  # o que sai do sorteio já é canônico


def test_dois_codigos_diferentes():
    # sorteio forte: 31^10 combinações — sair igual duas vezes é praticamente impossível
    assert frase.gerar() != frase.gerar()


def test_formatar_veste_e_validar_tira_a_roupa():
    c = frase.gerar()
    vestido = frase.formatar(c)
    assert vestido == f"{c[:5]}-{c[5:10]}-{c[10]}"
    assert frase.validar(vestido) == c                       # com traço
    assert frase.validar(vestido.lower()) == c               # caixa baixa
    assert frase.validar(" " + vestido.replace("-", " ")) == c  # espaço no lugar do traço


def test_vetores_ouro_do_verificador():
    # os MESMOS vetores do FraseTest.kt — mudou a conta de um lado, o outro acende
    assert frase._verificador("2222222222") == "2"
    assert frase._verificador("K7TP3XQ9FM") == "H"  # o exemplo do plano
    assert frase._verificador("ZZZZZZZZZZ") == "9"
    assert frase._verificador("23456789AB") == "P"
    assert frase.validar("K7TP3-XQ9FM-H") == "K7TP3XQ9FMH"


def test_typo_de_um_caractere_eh_acusado_sempre():
    c = frase.gerar()
    for i in range(len(c)):
        for outro in frase.ALFABETO:
            if outro == c[i]:
                continue
            with pytest.raises(ValueError):
                frase.validar(c[:i] + outro + c[i + 1:])


def test_troca_de_vizinhos_eh_acusada():
    c = "K7TP3XQ9FMH"
    for i in range(len(c) - 1):
        if c[i] == c[i + 1]:
            continue
        trocado = c[:i] + c[i + 1] + c[i] + c[i + 2:]
        with pytest.raises(ValueError):
            frase.validar(trocado)


def test_tamanho_errado_recusado_com_medida():
    with pytest.raises(ValueError, match="11"):
        frase.validar("K7TP3")


def test_caractere_confundivel_recusado_ensinando():
    # 'O' nunca existe num código de verdade: é erro de leitura, e a mensagem ensina
    with pytest.raises(ValueError, match="0/O"):
        frase.validar("K7TPO-XQ9FM-H")


def test_frase_antiga_de_palavras_recusada():
    # o formato velho (6 palavras) não passa; segredo antigo JÁ GRAVADO segue valendo
    # (é só string na config — ninguém revalida), mas não entra como pareamento novo
    with pytest.raises(ValueError):
        frase.validar("casa-vento-rio-azul-pedra-lobo")
