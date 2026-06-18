"""Ekodide — envia e recebe arquivos pela rede, lacrados e idênticos.

O nome é de um papagaio africano (odídẹ): repete com perfeição (o arquivo chega
cópia EXATA, sha256 idêntico) e VOA (vai de um aparelho a outro pela rede, sem
cabo). É código burro e determinístico — não tem IA aqui dentro. Algo pode ACIONAR
o Ekodide (um humano no terminal, um script, um agente), mas quem faz o trabalho é
este maquinário fixo.

Como biblioteca:
    from ekodide import enviar, servir
    enviar(origem, url, segredo)                 # manda arquivo/pasta
    servir(base, segredo, host="0.0.0.0")        # escuta e grava

Como comando (depois de instalar):
    ekodide send arquivo --para pc
    ekodide serve
"""
from __future__ import annotations

from .caixa_postal import gravar_recebido, guardar, guardar_pedaco
from .carteiro import EnvioResultado, enviar
from .lacre import (
    JANELA_SEGUNDOS,
    TrancaInvalida,
    desempacotar,
    empacotar,
    segredo_do_ambiente,
)
from .recebedor import servir

__version__ = "0.1.0"

__all__ = [
    "enviar",
    "EnvioResultado",
    "servir",
    "gravar_recebido",
    "guardar",
    "guardar_pedaco",
    "empacotar",
    "desempacotar",
    "segredo_do_ambiente",
    "TrancaInvalida",
    "JANELA_SEGUNDOS",
]
