"""O buscador do Ekodide: PUXA um arquivo de outra ponta (o inverso do carteiro).

O carteiro EMPURRA (posta na /receber do outro). O buscador PUXA: pergunta o que há
(/listar) e pede o arquivo (/buscar) da pasta que o outro compartilhou. Cada pedaço
volta CIFRADO (cofre) e lacrado (HMAC); aqui a gente abre o lacre, decifra, e grava
local reusando a caixa postal (mesma cerca de escrita, mesma remontagem de pedaços).

Não lê variáveis de ambiente: recebe a URL e o segredo prontos, como o carteiro.
"""
from __future__ import annotations

import base64
import binascii
import http.client
from pathlib import Path

from cryptography.exceptions import InvalidTag

from . import caixa_postal
from .acervo import PEDACO
from .carteiro import _Linha  # mesma conexão keep-alive do empurrar (reaproveitada)
from .cofre import decifrar
from .lacre import TrancaInvalida, desempacotar, empacotar


class ErroPuxar(Exception):
    """Falha ao puxar (origem fora do ar, recusada, ou resposta fora da tranca)."""


def listar(url: str, segredo: str) -> list[dict]:
    """O que dá pra puxar da `url`: lista de {'nome', 'tamanho'}. Levanta ErroPuxar
    se a origem recusar ou a resposta não abrir o lacre."""
    linha = _Linha(url)
    try:
        try:
            status, bruto = linha.postar("/listar", empacotar({}, segredo))
        except (http.client.HTTPException, OSError) as erro:
            raise ErroPuxar(f"não alcancei a origem ({erro})")
        if status != 200:
            raise ErroPuxar(f"origem recusou listar ({status}): {bruto.decode('utf-8', 'replace')}")
        try:
            itens = desempacotar(bruto, segredo).get("itens", [])
        except (TrancaInvalida, binascii.Error) as erro:
            raise ErroPuxar(f"lista fora da tranca: {erro}")
        return itens if isinstance(itens, list) else []
    finally:
        linha.fechar()


def _pedir_pedaco(
    linha: _Linha, nome: str, parte: int, partes: int, segredo: str
) -> tuple[bool, bytes | str]:
    """Pede UM pedaço pela /buscar e devolve (ok, bytes-decifrados) ou (False, motivo)."""
    carga = {"nome": nome, "parte": parte, "partes": partes}
    try:
        status, bruto = linha.postar("/buscar", empacotar(carga, segredo))
    except (http.client.HTTPException, OSError) as erro:
        return False, f"não alcancei a origem ({erro})"
    if status != 200:
        return False, f"origem recusou ({status}): {bruto.decode('utf-8', 'replace')}"
    try:
        volta = desempacotar(bruto, segredo)
        cifrado = base64.b64decode(volta["conteudo"], validate=True)
        return True, decifrar(cifrado, segredo)
    except (TrancaInvalida, KeyError, binascii.Error, InvalidTag) as erro:
        return False, f"pedaço fora da tranca: {erro}"


def puxar(
    nome: str, url: str, segredo: str, base: Path, tamanho: int | None = None
) -> tuple[bool, str]:
    """Puxa o arquivo `nome` da `url` pra dentro de `base` (lacrado/cifrado no caminho).
    Arquivo grande vem PICADO e é remontado pela caixa postal. Se `tamanho` não vier,
    descobre via /listar. Devolve (ok, destino-ou-motivo)."""
    if tamanho is None:
        try:
            disponivel = {i["nome"]: i["tamanho"] for i in listar(url, segredo)}
        except ErroPuxar as erro:
            return False, str(erro)
        if nome not in disponivel:
            return False, f"'{nome}' não está disponível pra puxar nessa origem"
        tamanho = int(disponivel[nome])

    partes = max(1, (tamanho + PEDACO - 1) // PEDACO)
    linha = _Linha(url)
    destino = None
    try:
        for parte in range(partes):
            ok, payload = _pedir_pedaco(linha, nome, parte, partes, segredo)
            if not ok:
                return False, f"pedaço {parte + 1}/{partes}: {payload}"
            # grava reusando a caixa postal: mesma cerca + remontagem do empurrar.
            destino = caixa_postal.guardar_pedaco(nome, payload, parte, partes, base, tamanho)
    except (OSError, ValueError) as erro:
        return False, f"não consegui gravar: {erro}"
    finally:
        linha.fechar()
    return True, str(destino) if destino else "(nada veio)"
