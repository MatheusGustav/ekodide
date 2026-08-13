"""O código de pareamento do Ekodide: um segredo forte que dá pra DIGITAR (e escanear).

O segredo dos dois lados tem que ser o MESMO. Inventar e copiar uma chave aleatória
("9f3a...") é chato e dá erro. Aqui o segredo nasce como um CÓDIGO curto sorteado —
'K7TP3-XQ9FM-H' — forte o bastante e fácil de ler, ditar e digitar (o QR é só outra
roupa pro mesmo código).

Importante: o código *é* o segredo (a chave do HMAC). Ele NUNCA cruza a rede — vai de
um aparelho ao outro pela tela, câmera ou dedos. É o "out-of-band" do pareamento.

Quem sorteia é SEMPRE a máquina: senha escolhida por humano fica de fora DE PROPÓSITO.
Quem está no mesmo Wi-Fi captura um pacote lacrado e testa senhas contra o HMAC
offline, sem limite de tentativas — senha humana cai em dicionário, sorteio não.

A forma CANÔNICA do segredo é maiúscula e sem traço (11 caracteres: 10 sorteados + 1
verificador). Traço e caixa baixa são ROUPA de leitura: `validar` tira a roupa e
devolve a forma canônica, e é ELA que se grava nas duas pontas — dali em diante o
segredo é usado byte-a-byte, sem mexer. Sem dependência: só `secrets` (sorteio forte).
"""
from __future__ import annotations

import secrets

# 31 símbolos: maiúsculas + dígitos, SEM os confundíveis 0/O e 1/I/L — lido numa tela
# ou ditado em voz alta, cada caractere só pode ser UMA coisa. 10 sorteados dão
# 31^10 ≈ 2^49,5 (~50 bits) — folgado pra parear numa LAN (o lacre ainda tem janela
# de 5 min + HMAC). E 31 é primo: o verificador (soma ponderada mod 31) acusa
# GARANTIDO qualquer erro de um caractere e qualquer troca de vizinhos.
ALFABETO = "23456789ABCDEFGHJKMNPQRSTUVWXYZ"
SORTEADOS = 10          # caracteres sorteados (a força do segredo)
TAMANHO = SORTEADOS + 1  # + 1 verificador no fim


def _verificador(corpo: str) -> str:
    """O caractere verificador do corpo: soma ponderada pela posição, mod 31."""
    soma = sum(peso * ALFABETO.index(c) for peso, c in enumerate(corpo, start=1))
    return ALFABETO[soma % len(ALFABETO)]


def gerar() -> str:
    """Sorteia um código novo, já com o verificador — canônico, pronto pra guardar."""
    corpo = "".join(secrets.choice(ALFABETO) for _ in range(SORTEADOS))
    return corpo + _verificador(corpo)


def formatar(codigo: str) -> str:
    """Veste um código canônico pra LEITURA: 'K7TP3-XQ9FM-H' (5 + 5 + verificador).
    O traço é só roupa — `validar` aceita com ou sem."""
    return f"{codigo[:5]}-{codigo[5:SORTEADOS]}-{codigo[SORTEADOS:]}"


def validar(texto: str) -> str:
    """Confere um código digitado/escaneado e devolve a forma canônica (a que se grava).

    Aceita a roupa da leitura (traço, espaço, caixa baixa). Recusa com mensagem clara
    o que não é código sorteado: tamanho errado, caractere fora do alfabeto ou
    verificador que não bate — o erro de digitação é acusado NA HORA, em vez de
    quebrar o lacre em silêncio depois.
    """
    canonico = "".join(texto.upper().split()).replace("-", "")
    if len(canonico) != TAMANHO:
        raise ValueError(
            f"código de pareamento tem {TAMANHO} caracteres "
            f"({SORTEADOS} sorteados + 1 verificador); vieram {len(canonico)}"
        )
    fora = sorted(set(canonico) - set(ALFABETO))
    if fora:
        raise ValueError(
            f"caractere que não existe em código de pareamento: {', '.join(fora)} "
            f"(0/O e 1/I/L ficam fora de propósito, por parecidos — releia na tela)"
        )
    if canonico[-1] != _verificador(canonico[:-1]):
        raise ValueError(
            "o verificador não bate — algum caractere saiu trocado; confira e digite de novo"
        )
    return canonico
