"""O cofre: cifra o conteúdo com AES-256-GCM chaveado pelo segredo. Vai-e-volta
idêntico, embaralha de verdade, e recusa chave errada ou conteúdo adulterado."""
import pytest
from cryptography.exceptions import InvalidTag

from ekodide.cofre import cifrar, decifrar

SEGREDO = "frase-codigo-do-pareamento"


def test_vai_e_volta_identico():
    claro = b"conteudo \x00\x01\x02 binario qualquer"
    assert decifrar(cifrar(claro, SEGREDO), SEGREDO) == claro


def test_embaralha_de_verdade():
    claro = b"SENHA-SUPER-SECRETA"
    blob = cifrar(claro, SEGREDO)
    assert claro not in blob          # o texto-claro não aparece na cifra
    assert len(blob) > len(claro)     # nonce + tag de autenticação somam bytes


def test_nonce_novo_a_cada_chamada():
    claro = b"mesmo conteudo"
    assert cifrar(claro, SEGREDO) != cifrar(claro, SEGREDO)  # nonce aleatório


def test_chave_errada_nao_abre():
    blob = cifrar(b"oi", SEGREDO)
    with pytest.raises(InvalidTag):
        decifrar(blob, "segredo-errado")


def test_adulteracao_e_recusada():
    blob = bytearray(cifrar(b"oi", SEGREDO))
    blob[-1] ^= 0x01  # mexe num byte da cifra
    with pytest.raises(InvalidTag):
        decifrar(bytes(blob), SEGREDO)
