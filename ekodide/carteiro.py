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
import http.client
import time
import urllib.parse
from dataclasses import dataclass, field
from pathlib import Path

from .cofre import cifrar
from .lacre import TrancaInvalida, desempacotar, empacotar

TIMEOUT_S = 30  # mata o POST se a rede travar

# Tamanho do PEDAÇO ao mandar um arquivo grande. Fica abaixo do corpo que o
# recebedor aceita (32 MB), já contando que o base64 incha ~33%: 16 MB viram
# ~21,3 MB no fio. Arquivo <= isto vai num envio só; maior, vai em pedaços.
# Pedaço maior = menos idas-e-voltas de rede por arquivo (mais rápido), ainda
# longe do limite de 32 MB e leve de RAM (processa um por vez).
PEDACO = 16 * 1024 * 1024

# Reenvio de UM pedaço quando a rede pisca: tenta algumas vezes com espera
# crescente antes de desistir. Se desistir, o '.parcial' fica no destino e um
# novo `send` RETOMA de onde parou (não recomeça do zero).
TENTATIVAS = 4    # tentativas por pedaço (1ª + 3 reenvios)
ESPERA_S = 1.0    # espera-base entre tentativas (cresce a cada uma)


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


class _Linha:
    """Conexão HTTP reaproveitada (keep-alive): mantém a porta aberta e passa vários
    pedaços pela MESMA conexão, em vez de reabrir uma a cada pedaço — corta o aperto
    de mão de TCP repetido (mais rápido no Wi-Fi real). Reabre sozinha se a rede cair."""

    def __init__(self, url: str) -> None:
        alvo = urllib.parse.urlsplit(url)
        self._host = alvo.hostname or "127.0.0.1"
        self._porta = alvo.port or 80
        self._conn: http.client.HTTPConnection | None = None

    def postar(self, caminho: str, corpo: bytes) -> tuple[int, bytes]:
        """POST de um corpo já lacrado. Devolve (status, resposta). Levanta
        HTTPException/OSError se a rede falhar — aí a conexão é descartada pra a
        próxima tentativa reabrir limpa."""
        if self._conn is None:
            self._conn = http.client.HTTPConnection(self._host, self._porta, timeout=TIMEOUT_S)
        try:
            self._conn.request(
                "POST", caminho, body=corpo,
                headers={"Content-Type": "application/json", "Content-Length": str(len(corpo))},
            )
            resp = self._conn.getresponse()
            return resp.status, resp.read()
        except (http.client.HTTPException, OSError):
            self.fechar()
            raise

    def fechar(self) -> None:
        if self._conn is not None:
            try:
                self._conn.close()
            except OSError:
                pass
            self._conn = None


def _postar(
    linha: _Linha, nome: str, dados: bytes, segredo: str,
    parte: int | None = None, partes: int | None = None, tamanho: int | None = None,
) -> tuple[bool, str]:
    """Lacra UM bloco e manda pela `linha` (rota /receber). Se `partes` vier, é um
    PEDAÇO (índice `parte` de `partes`, com o `tamanho` total junto pra travar a
    retomada); senão é o arquivo inteiro de uma vez. `nome` pode ser caminho relativo
    ('Fotos/sub/img.png'). Devolve (ok, info): info é o destino (preenchido no último
    pedaço) ou o motivo da falha."""
    # CIFRA o conteúdo antes de mandar: na rede passa só embaralhado (o cofre). A
    # chave sai do segredo; o destino decifra e grava byte-idêntico ao original.
    carga = {"nome": nome, "conteudo": base64.b64encode(cifrar(dados, segredo)).decode("ascii")}
    if partes is not None:
        carga["parte"], carga["partes"] = parte, partes
        if tamanho is not None:
            carga["tamanho"] = tamanho
    try:
        status, bruto = linha.postar("/receber", empacotar(carga, segredo))
    except (http.client.HTTPException, OSError) as erro:
        return False, f"não alcancei o destino ({erro})"
    if status != 200:
        return False, f"destino recusou ({status}): {bruto.decode('utf-8', 'replace')}"
    try:
        volta = desempacotar(bruto, segredo)
    except (TrancaInvalida, binascii.Error) as erro:
        return False, f"resposta fora da tranca: {erro}"
    return True, str(volta.get("destino") or "")


def _postar_resiliente(
    linha: _Linha, nome: str, dados: bytes, segredo: str,
    parte: int | None = None, partes: int | None = None, tamanho: int | None = None,
) -> tuple[bool, str]:
    """Como `_postar`, mas reenvia os MESMOS bytes algumas vezes (espera crescente)
    se a rede piscar. Reenviar um pedaço já gravado é inofensivo — o recebedor é
    idempotente. Só desiste depois de TENTATIVAS falhas seguidas."""
    info = ""
    for tentativa in range(TENTATIVAS):
        ok, info = _postar(linha, nome, dados, segredo, parte, partes, tamanho)
        if ok:
            return True, info
        if tentativa < TENTATIVAS - 1:
            time.sleep(ESPERA_S * (tentativa + 1))
    return False, info


def _ja_recebidos(linha: _Linha, nome: str, segredo: str, partes: int, tamanho: int) -> int:
    """Pergunta ao destino quantos pedaços deste arquivo ele já tem (pra RETOMAR).
    Qualquer erro na consulta → 0 (começa do zero, sem nunca atrapalhar o envio)."""
    carga = {"nome": nome, "partes": partes, "tamanho": tamanho}
    try:
        status, bruto = linha.postar("/progresso", empacotar(carga, segredo))
        if status != 200:
            return 0
        volta = desempacotar(bruto, segredo)
        return max(0, min(int(volta.get("recebidos", 0)), partes))
    except (http.client.HTTPException, OSError, TrancaInvalida, binascii.Error, ValueError):
        return 0


def _enviar_arquivo(origem: Path, nome: str, url: str, segredo: str) -> tuple[bool, str]:
    """Envia UM arquivo por UMA conexão reaproveitada (keep-alive). Se couber num
    pedaço, vai de uma vez; se for grande, vai PICADO (lendo do disco aos pedaços, sem
    carregar tudo na memória). Pergunta ao destino o que ele já tem e RETOMA de onde
    parou; cada pedaço é reenviado se a rede piscar. Devolve (ok, info)."""
    tamanho = origem.stat().st_size
    linha = _Linha(url)
    try:
        if tamanho <= PEDACO:
            return _postar_resiliente(linha, nome, origem.read_bytes(), segredo)

        partes = (tamanho + PEDACO - 1) // PEDACO
        inicio = _ja_recebidos(linha, nome, segredo, partes, tamanho)  # RETOMA daqui
        destino = ""
        with origem.open("rb") as f:
            if inicio:
                f.seek(inicio * PEDACO)  # pula os pedaços que o destino já tem
            for i in range(inicio, partes):
                bloco = f.read(PEDACO)   # lê UMA vez; o reenvio usa estes mesmos bytes
                ok, info = _postar_resiliente(linha, nome, bloco, segredo, i, partes, tamanho)
                if not ok:
                    return False, f"pedaço {i + 1}/{partes}: {info} (rode o `send` de novo pra retomar)"
                destino = info or destino
        return True, destino or "(montado no destino)"
    finally:
        linha.fechar()


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
