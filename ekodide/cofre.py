"""O cofre do Ekodide: cifra o CONTEÚDO pra ninguém na rede ler — só as pontas.

O lacre (lacre.py) prova *quem* mandou e que nada foi adulterado, mas NÃO esconde:
o conteúdo trafega à vista de quem estiver na mesma rede. O cofre fecha isso — cifra
os bytes com AES-256-GCM (autenticado) usando uma chave derivada do MESMO segredo que
as pontas já compartilham (a frase-código do pareamento). A chave nunca trafega; o
segredo também não. Na rede passa só embaralhado; o destino decifra e o arquivo
gravado fica **byte-idêntico** ao original (decifrar é o inverso exato de cifrar).

Depende da lib `cryptography` (AES de verdade não existe na stdlib do Python). É a
peça que tira o Ekodide do 'só rede confiável' rumo a poder cruzar redes não confiáveis.
"""
from __future__ import annotations

import os

from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from cryptography.hazmat.primitives.kdf.hkdf import HKDF

_TAM_NONCE = 12  # AES-GCM: 96 bits, o nonce recomendado
_INFO = b"ekodide-cofre-aes256gcm-v1"  # separa o uso desta chave de outros derivados


def _chave(segredo: str) -> bytes:
    """Deriva uma chave de 32 bytes (AES-256) do segredo compartilhado, via HKDF.
    Mesma derivação dos dois lados → mesma chave, sem nunca mandá-la pela rede."""
    return HKDF(algorithm=hashes.SHA256(), length=32, salt=None, info=_INFO).derive(
        segredo.encode("utf-8")
    )


def cifrar(dados: bytes, segredo: str) -> bytes:
    """Embaralha `dados` com AES-256-GCM. Devolve nonce(12B) + cifra+tag. Cada chamada
    sorteia um nonce novo (nunca repetir nonce com a mesma chave)."""
    nonce = os.urandom(_TAM_NONCE)
    return nonce + AESGCM(_chave(segredo)).encrypt(nonce, dados, None)


def decifrar(blob: bytes, segredo: str) -> bytes:
    """Desembaralha o que `cifrar` produziu. Levanta cryptography.exceptions.InvalidTag
    se a chave estiver errada ou o conteúdo tiver sido adulterado."""
    nonce, cifra = blob[:_TAM_NONCE], blob[_TAM_NONCE:]
    return AESGCM(_chave(segredo)).decrypt(nonce, cifra, None)
