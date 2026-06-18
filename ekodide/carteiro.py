"""O carteiro do Ekodide: ENVIA um arquivo ou uma pasta inteira pela rede.

Lacra cada bloco (HMAC) e posta na rota /receber do destino. Arquivo que cabe vai
de uma vez; arquivo grande vai PICADO em pedaços (lidos do disco aos poucos, sem
carregar tudo na memória) — a caixa postal do outro lado remonta. Pasta vira vários
envios preservando as subpastas (o caminho relativo viaja junto).

Devolve um EnvioResultado neutro (números e caminhos), pra quem aciona montar a
própria resposta. Não lê variáveis de ambiente: recebe a URL e o segredo prontos.
"""
from __future__ import annotations

import base64
import binascii
import urllib.error
import urllib.request
from dataclasses import dataclass, field
from pathlib import Path

from .lacre import TrancaInvalida, desempacotar, empacotar

TIMEOUT_S = 30  # mata o POST se a rede travar

# Tamanho do PEDAÇO ao mandar um arquivo grande. Fica abaixo do corpo que o
# recebedor aceita (32 MB), já contando que o base64 incha ~33%: 8 MB viram
# ~10,7 MB no fio. Arquivo <= isto vai num envio só; maior, vai em pedaços.
PEDACO = 8 * 1024 * 1024


@dataclass
class EnvioResultado:
    """O que o carteiro devolve — dados crus, sem frase pronta. `ok` resume; o resto
    deixa o chamador montar a mensagem que quiser."""

    ok: bool
    is_pasta: bool
    total: int                       # quantos arquivos tentou enviar
    enviados: int                    # quantos foram de fato
    destino: str = ""                # caminho de exemplo no destino (último/único)
    falhas: list[str] = field(default_factory=list)  # motivos, vazio = tudo ok


def _postar(
    nome: str, dados: bytes, url: str, segredo: str,
    parte: int | None = None, partes: int | None = None,
) -> tuple[bool, str]:
    """POSTa UM bloco pro recebedor. Se `partes` vier, é um PEDAÇO (índice `parte`
    de `partes`); senão é o arquivo inteiro de uma vez. `nome` pode ser caminho
    relativo ('Fotos/sub/img.png'). Devolve (ok, info): info é o destino
    (preenchido no último pedaço) ou o motivo da falha."""
    carga = {"nome": nome, "conteudo": base64.b64encode(dados).decode("ascii")}
    if partes is not None:
        carga["parte"], carga["partes"] = parte, partes
    req = urllib.request.Request(
        url.rstrip("/") + "/receber",
        data=empacotar(carga, segredo),
        method="POST",
        headers={"Content-Type": "application/json"},
    )
    try:
        with urllib.request.urlopen(req, timeout=TIMEOUT_S) as resp:
            bruto = resp.read()
    except urllib.error.HTTPError as erro:
        motivo = erro.read().decode("utf-8", "replace") if erro.fp else str(erro)
        return False, f"destino recusou ({erro.code}): {motivo}"
    except (urllib.error.URLError, OSError) as erro:
        return False, f"não alcancei {url} ({erro})"
    try:
        volta = desempacotar(bruto, segredo)
    except (TrancaInvalida, binascii.Error) as erro:
        return False, f"resposta fora da tranca: {erro}"
    return True, str(volta.get("destino") or "")


def _enviar_arquivo(origem: Path, nome: str, url: str, segredo: str) -> tuple[bool, str]:
    """Envia UM arquivo. Se couber num pedaço, vai de uma vez; se for grande, vai
    PICADO (lendo do disco aos pedaços, sem carregar tudo na memória). O recebedor
    remonta. Devolve (ok, info)."""
    tamanho = origem.stat().st_size
    if tamanho <= PEDACO:
        return _postar(nome, origem.read_bytes(), url, segredo)

    partes = (tamanho + PEDACO - 1) // PEDACO
    destino = ""
    with origem.open("rb") as f:
        for i in range(partes):
            ok, info = _postar(nome, f.read(PEDACO), url, segredo, parte=i, partes=partes)
            if not ok:
                return False, f"pedaço {i + 1}/{partes}: {info}"
            destino = info or destino
    return True, destino or "(montado no destino)"


def _enviar_pasta(raiz: Path, url: str, segredo: str) -> EnvioResultado:
    """Percorre a pasta e envia cada arquivo preservando a estrutura (o nome da
    pasta + subpastas viram o caminho relativo). Arquivo grande vai picado."""
    arquivos = sorted(x for x in raiz.rglob("*") if x.is_file())
    if not arquivos:
        return EnvioResultado(ok=True, is_pasta=True, total=0, enviados=0)

    enviados, falhas, exemplo = 0, [], ""
    for arq in arquivos:
        rel = Path(raiz.name) / arq.relative_to(raiz)  # 'Fotos/sub/img.png'
        try:
            ok, info = _enviar_arquivo(arq, str(rel), url, segredo)
        except OSError as erro:
            falhas.append(f"{rel} (não li: {erro})")
            continue
        if ok:
            enviados += 1
            exemplo = exemplo or info
        else:
            falhas.append(f"{rel} ({info})")

    return EnvioResultado(
        ok=enviados > 0, is_pasta=True, total=len(arquivos),
        enviados=enviados, destino=exemplo, falhas=falhas,
    )


def enviar(origem: Path, url: str, segredo: str) -> EnvioResultado:
    """Manda um arquivo OU uma pasta inteira pra `url` (rota /receber), lacrado com
    `segredo`. Arquivo grande vai picado; pasta preserva as subpastas. Devolve um
    EnvioResultado neutro — sem frase pronta, pra o chamador montar a sua."""
    origem = Path(origem)
    if origem.is_dir():
        return _enviar_pasta(origem, url, segredo)
    ok, info = _enviar_arquivo(origem, origem.name, url, segredo)  # grande vai picado
    return EnvioResultado(
        ok=ok, is_pasta=False, total=1, enviados=1 if ok else 0,
        destino=info if ok else "", falhas=[] if ok else [info],
    )
