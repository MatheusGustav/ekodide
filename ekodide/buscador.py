"""O buscador do Ekodide: PUXA um arquivo de outra ponta (o inverso do carteiro).

O carteiro EMPURRA (posta na /receber do outro). O buscador PUXA: pergunta o que há
(/listar) e pede o arquivo (/buscar) da pasta que o outro compartilhou. Cada pedaço
volta CIFRADO (cofre) e lacrado (HMAC); aqui a gente abre o lacre, decifra, e grava
local reusando a caixa postal (mesma cerca de escrita, mesma remontagem de pedaços).

Além do `puxar` (que grava) existe o `espiar`: a mesma viagem, mas os bytes ficam
SÓ NA MEMÓRIA e são devolvidos na mão de quem chamou — olhar ≠ puxar. Nenhum dos
dois mexe no protocolo: as rotas são as mesmas, a outra ponta não muda.

Não lê variáveis de ambiente: recebe a URL e o segredo prontos, como o carteiro.
"""
from __future__ import annotations

import base64
import binascii
import http.client
from pathlib import Path

from cryptography.exceptions import InvalidTag

from . import acervo, caixa_postal
from .carteiro import _Linha  # mesma conexão keep-alive do empurrar (reaproveitada)
from .cofre import decifrar
from .lacre import TrancaInvalida, desempacotar, empacotar


class ErroPuxar(Exception):
    """Falha ao puxar (origem fora do ar, recusada, ou resposta fora da tranca)."""


def _consultar_listar(url: str, segredo: str, carga: dict) -> dict:
    """Posta a `carga` na /listar e devolve a resposta aberta (lacre conferido)."""
    linha = _Linha(url)
    try:
        try:
            status, bruto = linha.postar("/listar", empacotar(carga, segredo))
        except (http.client.HTTPException, OSError) as erro:
            raise ErroPuxar(f"não alcancei a origem ({erro})")
        if status != 200:
            raise ErroPuxar(f"origem recusou listar ({status}): {bruto.decode('utf-8', 'replace')}")
        try:
            return desempacotar(bruto, segredo)
        except (TrancaInvalida, binascii.Error) as erro:
            raise ErroPuxar(f"lista fora da tranca: {erro}")
    finally:
        linha.fechar()


def listar(url: str, segredo: str) -> list[dict]:
    """O que dá pra puxar da `url`: lista de {'nome', 'tamanho'}. Levanta ErroPuxar
    se a origem recusar ou a resposta não abrir o lacre."""
    itens = _consultar_listar(url, segredo, {}).get("itens", [])
    return itens if isinstance(itens, list) else []


def navegar(url: str, segredo: str, pasta: str) -> dict:
    """A vista RASA de uma `pasta` da origem (navegação por pastas): devolve
    {'itens': [{'nome','tamanho'}...], 'pastas': ['sub', ...]} — um nível, como um 'ls'.
    Só funciona se a origem liberou a navegação (o celular com acesso total);
    origem que não navega recusa com o motivo (ErroPuxar)."""
    volta = _consultar_listar(url, segredo, {"pasta": pasta})
    itens = volta.get("itens", [])
    pastas = volta.get("pastas", [])
    return {
        "itens": itens if isinstance(itens, list) else [],
        "pastas": pastas if isinstance(pastas, list) else [],
    }


def _pedir_pedaco(
    linha: _Linha, nome: str, parte: int, partes: int, segredo: str,
    pasta: str | None = None,
) -> tuple[bool, bytes | str]:
    """Pede UM pedaço pela /buscar e devolve (ok, bytes-decifrados) ou (False, motivo)."""
    carga = {"nome": nome, "parte": parte, "partes": partes}
    if pasta is not None:
        carga["pasta"] = pasta
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


def espiar(
    nome: str, url: str, segredo: str, limite: int | None = None
) -> tuple[bool, bytes | str, int]:
    """ESPIA o arquivo `nome` da `url`: a MESMA viagem do puxar (lacre + cifra,
    pedaço a pedaço), mas NADA é gravado em disco — os bytes voltam na mão de quem
    chamou e morrem com ele. Olhar e puxar são atos diferentes: quem só quer ler
    não devia precisar deixar cópia.

    Com `limite`, para de pedir pedaços assim que junta `limite` bytes e apara o
    excesso — uma espiada não precisa do arquivo inteiro, e o resto nem viaja.

    Devolve (ok, bytes-ou-motivo, tamanho-total-do-arquivo): comparar o len() dos
    bytes com o tamanho diz se a espiada foi cortada.

    Não mexe no protocolo: usa as mesmas rotas /listar e /buscar do puxar, então
    a outra ponta (inclusive o APK) não precisa saber que isto existe."""
    try:
        disponivel = {i["nome"]: i["tamanho"] for i in listar(url, segredo)}
    except ErroPuxar as erro:
        return False, str(erro), 0
    if nome not in disponivel:
        return False, f"'{nome}' não está disponível pra puxar nessa origem", 0
    tamanho = int(disponivel[nome])

    partes = max(1, (tamanho + acervo.PEDACO - 1) // acervo.PEDACO)
    juntado = bytearray()
    linha = _Linha(url)
    try:
        for parte in range(partes):
            ok, payload = _pedir_pedaco(linha, nome, parte, partes, segredo)
            if not ok:
                return False, f"pedaço {parte + 1}/{partes}: {payload}", tamanho
            juntado += payload
            if limite is not None and len(juntado) >= limite:
                break  # já deu pra espiada — o resto do arquivo nem viaja
    finally:
        linha.fechar()
    if limite is not None:
        del juntado[limite:]
    return True, bytes(juntado), tamanho


def puxar(
    nome: str, url: str, segredo: str, base: Path, tamanho: int | None = None,
    pasta: str | None = None,
) -> tuple[bool, str]:
    """Puxa o arquivo `nome` da `url` pra dentro de `base` (lacrado/cifrado no caminho).
    Arquivo grande vem PICADO e é remontado pela caixa postal. Se um download anterior
    caiu no meio, RETOMA de onde parou (pula os pedaços que já estão no `.parcial` local).
    Se `tamanho` não vier, descobre via /listar. Com `pasta`, puxa da pasta navegada
    (origem precisa liberar a navegação). Devolve (ok, destino-ou-motivo)."""
    if tamanho is None:
        try:
            itens = navegar(url, segredo, pasta)["itens"] if pasta is not None \
                else listar(url, segredo)
        except ErroPuxar as erro:
            return False, str(erro)
        disponivel = {i["nome"]: i["tamanho"] for i in itens}
        if nome not in disponivel:
            return False, f"'{nome}' não está disponível pra puxar nessa origem"
        tamanho = int(disponivel[nome])

    # acervo.PEDACO é a FONTE ÚNICA do tamanho do pedaço (servidor e cliente leem o
    # mesmo) — ler em tempo de execução evita cópias dessincronizadas das duas pontas.
    partes = max(1, (tamanho + acervo.PEDACO - 1) // acervo.PEDACO)
    # RETOMADA: consulta o progresso LOCAL (eu mesmo gravo) e pula o que já baixei.
    ja = caixa_postal.progresso_de(nome, partes, base, tamanho)
    linha = _Linha(url)
    destino = None
    try:
        for parte in range(ja, partes):
            ok, payload = _pedir_pedaco(linha, nome, parte, partes, segredo, pasta)
            if not ok:
                return False, f"pedaço {parte + 1}/{partes}: {payload} (rode o pull de novo pra retomar)"
            # grava reusando a caixa postal: mesma cerca + remontagem do empurrar.
            destino = caixa_postal.guardar_pedaco(nome, payload, parte, partes, base, tamanho)
    except (OSError, ValueError) as erro:
        return False, f"não consegui gravar: {erro}"
    finally:
        linha.fechar()
    return True, str(destino) if destino else "(nada veio)"
