"""A config do Ekodide — o '~/.gitconfig' dele: guarda, FORA de qualquer projeto,
o segredo e os endereços, pra `ekodide send` funcionar de qualquer pasta.

Fica em ~/.config/ekodide/config.json (respeita XDG_CONFIG_HOME). Como tem o
segredo, o arquivo nasce com cadeado (permissão 600 — só o dono lê).

Formato:
{
  "segredo": "a-mesma-chave-das-duas-pontas",
  "destinos": {"pc": "http://192.168.0.10:8778", "celular": "http://192.168.0.9:8777"},
  "receber": {"dir": "~/Downloads", "porta": 8778, "host": "127.0.0.1"}
}
"""
from __future__ import annotations

import json
import os
from pathlib import Path


class ErroConfig(Exception):
    """Algo errado na config (falta segredo, destino desconhecido, etc.)."""


def caminho() -> Path:
    """Onde a config mora (XDG_CONFIG_HOME ou ~/.config)."""
    raiz = os.environ.get("XDG_CONFIG_HOME") or "~/.config"
    return Path(raiz).expanduser() / "ekodide" / "config.json"


def carregar() -> dict:
    """Lê a config (dicionário vazio se ainda não existe)."""
    arq = caminho()
    if not arq.exists():
        return {}
    try:
        return json.loads(arq.read_text("utf-8"))
    except (ValueError, OSError) as erro:
        raise ErroConfig(f"config ilegível em {arq}: {erro}")


def salvar(cfg: dict) -> Path:
    """Grava a config com cadeado (600). Cria a pasta se faltar."""
    arq = caminho()
    arq.parent.mkdir(parents=True, exist_ok=True)
    arq.write_text(json.dumps(cfg, indent=2, ensure_ascii=False) + "\n", "utf-8")
    arq.chmod(0o600)  # só o dono lê — tem segredo dentro
    return arq


def segredo(cfg: dict | None = None) -> str:
    """O segredo: variável de ambiente vence (EKODIDE_SEGREDO/OROGBO_SEGREDO);
    senão o da config. Erro claro se faltar nos dois."""
    do_ambiente = os.environ.get("EKODIDE_SEGREDO") or os.environ.get("OROGBO_SEGREDO")
    if do_ambiente:
        return do_ambiente
    cfg = cfg if cfg is not None else carregar()
    if cfg.get("segredo"):
        return cfg["segredo"]
    raise ErroConfig(
        "Sem segredo. Rode:  ekodide config segredo <a-chave>   "
        "(ou defina EKODIDE_SEGREDO no ambiente)."
    )


def url_do_destino(nome: str, cfg: dict | None = None) -> str:
    """Traduz um nome de destino ('pc', 'celular') na URL da config."""
    cfg = cfg if cfg is not None else carregar()
    destinos = cfg.get("destinos") or {}
    if nome not in destinos:
        conhecidos = ", ".join(destinos) or "(nenhum ainda)"
        raise ErroConfig(
            f"Destino '{nome}' não está na config. Conhecidos: {conhecidos}. "
            f"Adicione com:  ekodide config destino {nome} http://IP:PORTA"
        )
    return destinos[nome]
