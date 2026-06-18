"""A boca de comando do Ekodide: o 'git' da transferência de arquivos.

Determinístico, SEM IA — você (ou um script) aciona pela mão. Lê o segredo e os
endereços da config (~/.config/ekodide/), então funciona de qualquer pasta.

    ekodide send foto.png --para pc            # manda foto.png (da pasta atual) pro 'pc'
    ekodide send ~/Downloads/x --para celular  # arquivo ou pasta inteira
    ekodide serve                              # sobe a ponta que ESCUTA e grava
    ekodide config segredo <chave>             # guarda o segredo (cadeado 600)
    ekodide config destino pc http://IP:8778   # cadastra um destino
    ekodide config show                        # mostra a config (segredo mascarado)
"""
from __future__ import annotations

import argparse
import sys
import time
from pathlib import Path

from . import config
from .carteiro import enviar


def _falar_envio(r, origem: Path, destino: str) -> None:
    """Traduz o EnvioResultado neutro numa frase pro terminal."""
    if r.is_pasta:
        if r.total == 0:
            print(f"Pasta '{origem.name}' está vazia — nada pra enviar.")
            return
        print(f"Enviei {r.enviados} de {r.total} arquivo(s) da pasta '{origem.name}' pro '{destino}'.")
        if r.falhas:
            amostra = "; ".join(r.falhas[:5]) + (" …" if len(r.falhas) > 5 else "")
            print(f"  falharam {len(r.falhas)}: {amostra}")
        elif r.destino:
            print(f"  ex.: chegou em {r.destino}")
    elif r.ok:
        print(f"Enviei '{origem.name}' pro '{destino}'. Chegou em: {r.destino}")
    else:
        motivo = r.falhas[0] if r.falhas else "falha"
        print(f"Não consegui enviar '{origem.name}': {motivo}")


def _registrar(para: str, origem: Path, rotulo: str) -> None:
    """Anota o envio no histórico local (o análogo do -m do git)."""
    log = config.caminho().parent / "historico.log"
    log.parent.mkdir(parents=True, exist_ok=True)
    carimbo = time.strftime("%Y-%m-%d %H:%M:%S")
    with log.open("a", encoding="utf-8") as f:
        f.write(f"{carimbo}\t{para}\t{origem}\t{rotulo}\n")


def _cmd_send(args) -> int:
    origem = Path(args.caminho).expanduser()
    if not origem.exists():
        print(f"Não achei: {origem}", file=sys.stderr)
        return 1
    try:
        url = config.url_do_destino(args.para)
        segredo = config.segredo()
    except config.ErroConfig as erro:
        print(erro, file=sys.stderr)
        return 1

    if args.mensagem:
        print(f'· {args.mensagem}')
        _registrar(args.para, origem, args.mensagem)

    r = enviar(origem, url, segredo)
    _falar_envio(r, origem, args.para)
    return 0 if r.ok else 1


def _cmd_serve(args) -> int:
    from .recebedor import servir

    cfg = config.carregar()
    receber = cfg.get("receber") or {}
    base = args.dir or receber.get("dir") or "~/Downloads"
    porta = args.porta or receber.get("porta") or 8778
    host = args.host or receber.get("host") or "127.0.0.1"
    try:
        segredo = config.segredo(cfg)
    except config.ErroConfig as erro:
        print(erro, file=sys.stderr)
        return 1
    servir(Path(base).expanduser(), segredo, host=host, porta=int(porta))
    return 0


def _cmd_config(args) -> int:
    cfg = config.carregar()
    if args.acao == "segredo":
        cfg["segredo"] = args.valor
        config.salvar(cfg)
        print(f"Segredo guardado em {config.caminho()} (cadeado 600).")
    elif args.acao == "destino":
        cfg.setdefault("destinos", {})[args.nome] = args.url
        config.salvar(cfg)
        print(f"Destino '{args.nome}' = {args.url}")
    elif args.acao == "show":
        mostra = dict(cfg)
        if mostra.get("segredo"):
            mostra["segredo"] = "***(guardado)***"
        import json
        print(f"# {config.caminho()}")
        print(json.dumps(mostra, indent=2, ensure_ascii=False))
    return 0


def construir_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="ekodide", description="Enviar/receber arquivos lacrados pela rede.")
    sub = p.add_subparsers(dest="cmd", required=True)

    s = sub.add_parser("send", help="envia um arquivo ou pasta pra um destino")
    s.add_argument("caminho", help="arquivo OU pasta (da pasta atual, como no git)")
    s.add_argument("--para", required=True, help="nome do destino (ex.: pc, celular)")
    s.add_argument("-m", "--mensagem", default="", help="rótulo do envio (vai pro histórico)")
    s.set_defaults(func=_cmd_send)

    v = sub.add_parser("serve", help="sobe a ponta que escuta e grava o que chega")
    v.add_argument("--dir", help="pasta destino (padrão: config ou ~/Downloads)")
    v.add_argument("--porta", type=int, help="porta (padrão: config ou 8778)")
    v.add_argument("--host", help="0.0.0.0 pra abrir na LAN (padrão: 127.0.0.1)")
    v.set_defaults(func=_cmd_serve)

    c = sub.add_parser("config", help="mexe na config (segredo, destinos)")
    csub = c.add_subparsers(dest="acao", required=True)
    cseg = csub.add_parser("segredo", help="guarda o segredo (a mesma chave das duas pontas)")
    cseg.add_argument("valor")
    cdes = csub.add_parser("destino", help="cadastra/atualiza um destino")
    cdes.add_argument("nome")
    cdes.add_argument("url")
    csub.add_parser("show", help="mostra a config (segredo mascarado)")
    c.set_defaults(func=_cmd_config)

    return p


def main(argv: list[str] | None = None) -> int:
    args = construir_parser().parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
