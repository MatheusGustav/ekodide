"""O lacre do Ekodide: assina e verifica cada mensagem com um segredo.

O segredo NUNCA cruza a rede. Quem manda assina a mensagem com ele (HMAC-SHA256);
quem recebe recalcula a assinatura e compara. É código burro e determinístico de
propósito. O lacre prova:

  - quem mandou tinha o segredo   (autenticação)
  - ninguém mexeu no caminho      (integridade)
  - a mensagem é recente          (carimbo de tempo: limita repetição a uma janela curta)

É o MESMO lacre para Wi-Fi agora e para a internet depois — ele viaja com a
mensagem, não depende do cano. O conteúdo já vai cifrado à parte (ver cofre.py,
AES-256-GCM); o lacre cuida de autenticidade/integridade/recência, não de esconder.
"""
from __future__ import annotations

import hmac
import json
import os
import time
from hashlib import sha256


class TrancaInvalida(Exception):
    """Mensagem recusada pela fechadura (assinatura, formato ou tempo)."""


# Janela do carimbo de tempo: barra repetição de mensagens antigas sem exigir
# relógios cravados no mesmo segundo. 5 min cobre folga de relógio na LAN.
JANELA_SEGUNDOS = 300


def segredo_do_ambiente() -> str:
    """Lê o segredo de EKODIDE_SEGREDO (ou OROGBO_SEGREDO, p/ compatibilidade).
    Erro claro se faltar — nunca há padrão. O CLI também sabe ler do arquivo de
    config e passar o segredo direto pra enviar()/servir()."""
    segredo = os.environ.get("EKODIDE_SEGREDO") or os.environ.get("OROGBO_SEGREDO", "")
    if not segredo:
        raise TrancaInvalida(
            "Falta o segredo: defina EKODIDE_SEGREDO (ou guarde em "
            "~/.config/ekodide/config.json com 'ekodide config')."
        )
    return segredo


def _canonico(carga: dict) -> bytes:
    """JSON estável (chaves ordenadas, sem espaços) p/ a assinatura bater dos dois lados."""
    return json.dumps(
        carga, sort_keys=True, separators=(",", ":"), ensure_ascii=False
    ).encode("utf-8")


def _assinar(corpo: bytes, segredo: str) -> str:
    return hmac.new(segredo.encode("utf-8"), corpo, sha256).hexdigest()


def empacotar(carga: dict, segredo: str, agora: float | None = None) -> bytes:
    """Carimba o tempo, assina e devolve os bytes prontos para enviar."""
    selada = {**carga, "ts": int(agora if agora is not None else time.time())}
    assinatura = _assinar(_canonico(selada), segredo)
    return _canonico({"carga": selada, "assinatura": assinatura})


def desempacotar(corpo: bytes, segredo: str, agora: float | None = None) -> dict:
    """Verifica assinatura e tempo; devolve a carga. Levanta TrancaInvalida se algo não bate."""
    try:
        envelope = json.loads(corpo)
        carga = envelope["carga"]
        assinatura = envelope["assinatura"]
    except (ValueError, KeyError, TypeError):
        raise TrancaInvalida("mensagem malformada")

    esperada = _assinar(_canonico(carga), segredo)
    # compare_digest: comparação em tempo constante (não vaza o segredo por timing).
    if not hmac.compare_digest(esperada, str(assinatura)):
        raise TrancaInvalida("assinatura não confere (segredo errado ou corpo adulterado)")

    ts = carga.get("ts")
    if not isinstance(ts, int):
        raise TrancaInvalida("sem carimbo de tempo")
    agora = agora if agora is not None else time.time()
    if abs(agora - ts) > JANELA_SEGUNDOS:
        raise TrancaInvalida("mensagem fora da janela de tempo (possível repetição)")

    return carga
