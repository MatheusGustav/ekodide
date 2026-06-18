"""A frase-código do Ekodide: um segredo forte que dá pra DIGITAR.

O segredo dos dois lados tem que ser o MESMO. Inventar e copiar uma chave aleatória
("9f3a...") é chato e dá erro. Aqui geramos o segredo como uma FRASE de palavras
simples ('casa-vento-rio-azul-pedra-lobo'): forte o bastante e fácil de ditar/digitar.

Importante: a frase *é* o segredo (a chave do HMAC). Ela NUNCA cruza a rede — vai de
um aparelho ao outro pela boca/tela (você lê, o outro digita). É o "out-of-band" do
pareamento. Sem dependência: só `secrets` (sorteio forte) e uma lista embutida.
"""
from __future__ import annotations

import secrets

# Lista de palavras curtas, sem acento (fáceis de ditar e digitar em qualquer teclado).
# São 164 palavras (~7,4 bits cada); o padrão de 6 palavras dá ~44 bits — folgado pra
# parear numa LAN (o lacre ainda tem janela de 5 min e HMAC; força bruta pela rede é
# inviável).
PALAVRAS = [
    "abelha", "agua", "anel", "areia", "arroz", "arvore", "asa", "aviao",
    "bambu", "banana", "barco", "bicho", "bola", "bolo", "boto", "brisa",
    "cabra", "cacto", "caju", "carro", "casa", "cavalo", "chave", "chuva",
    "cobra", "copo", "corda", "couro", "dado", "dedo", "dente", "disco",
    "doce", "dragao", "duna", "elefante", "erva", "escada", "espelho", "estrela",
    "faca", "farol", "festa", "flor", "fogo", "folha", "forte", "fruta",
    "galho", "ganso", "gato", "gelo", "gema", "gota", "grama", "gruta",
    "harpa", "haste", "hera", "hino", "horta", "iate", "iglu", "ilha",
    "indio", "ipe", "isca", "jacare", "janela", "jardim", "jarro", "jiboia",
    "jogo", "joia", "juba", "lago", "lama", "leao", "leite", "lenha",
    "livro", "lobo", "lua", "mar", "mato", "mel", "mesa", "milho",
    "moeda", "monte", "mundo", "nabo", "navio", "nervo", "neve", "ninho",
    "noite", "norte", "nuvem", "oasis", "olho", "ombro", "onca", "onda",
    "ostra", "ouro", "ovo", "pao", "pato", "pedra", "peixe", "pena",
    "pinha", "ponte", "porta", "quadra", "quati", "queijo", "quilo", "quintal",
    "raiz", "rato", "rede", "rio", "rocha", "roda", "rosa", "rumo",
    "sapo", "selva", "serra", "sino", "sol", "sopa", "suco", "sul",
    "tatu", "teia", "telha", "terra", "tigre", "torre", "trem", "trilha",
    "uniao", "unha", "urna", "ursa", "urso", "urubu", "uva", "uivo",
    "vaca", "vale", "vela", "vento", "verao", "vidro", "vinho", "voo",
    "zebra", "zinco", "zona", "ziper",
]


def gerar(palavras: int = 6, separador: str = "-") -> str:
    """Sorteia uma frase-código forte (segredo pronto pra usar nos dois lados)."""
    if palavras < 4:
        raise ValueError("uma frase fraca demais não pareia com segurança; use >= 4 palavras")
    return separador.join(secrets.choice(PALAVRAS) for _ in range(palavras))
