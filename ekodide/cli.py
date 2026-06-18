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

from . import config, cortina, frase, vizinhanca
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


def _resolver_destino(nome: str, descobrir: bool) -> str:
    """Acha a URL do destino. Sem --descobrir, a config vence (rápido). Se o nome não
    está na config (ou --descobrir forçado), procura o aparelho na rede pelo nome —
    assim funciona mesmo sem cadastrar IP e mesmo que o IP tenha mudado (DHCP)."""
    if not descobrir:
        try:
            return config.url_do_destino(nome)
        except config.ErroConfig:
            pass  # não cadastrado — cai pra descoberta abaixo
    print(f"Procurando '{nome}' na rede…", file=sys.stderr)
    for aparelho in vizinhanca.procurar():
        if aparelho["nome"] == nome:
            return vizinhanca.url_de(aparelho)
    raise config.ErroConfig(
        f"Não achei '{nome}' (nem na config, nem na rede). "
        f"Veja quem está disponível com:  ekodide devices"
    )


def _cmd_send(args) -> int:
    origem = Path(args.caminho).expanduser()
    if not origem.exists():
        print(f"Não achei: {origem}", file=sys.stderr)
        return 1
    try:
        url = _resolver_destino(args.para, args.descobrir)
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
    # Se a caixa está aberta na LAN, anuncia presença pra outros acharem sem digitar IP.
    if host != "127.0.0.1":
        nome = config.nome_do_aparelho(cfg)
        vizinhanca.anunciar_em_thread(nome, int(porta))
        print(f"Anunciando como '{nome}' na rede (descoberta automática).")
        fechadas = [k for k, v in cortina.portas_liberadas(cortina.portas(int(porta))).items() if v is False]
        if fechadas:
            print(f"  dica: o firewall parece bloquear {', '.join(fechadas)} — "
                  f"libere com:  ekodide firewall --abrir")
    servir(Path(base).expanduser(), segredo, host=host, porta=int(porta))
    return 0


def _cmd_firewall(args) -> int:
    portas = cortina.portas()
    sistema = cortina.detectar()
    if sistema is None:
        print("Não reconheci o firewall. Se houver um, libere no lado que RECEBE:")
        print("  Linux/firewalld: sudo firewall-cmd --add-port=8778/tcp --add-port=8779/udp")
        print("                   --permanent && sudo systemctl restart firewalld")
        print("  Linux/ufw:       sudo ufw allow 8778/tcp && sudo ufw allow 8779/udp")
        print('  Windows (Admin): netsh advfirewall firewall add rule name="Ekodide 8778/tcp"')
        print("                   dir=in action=allow protocol=TCP localport=8778  (idem 8779/UDP)")
        return 0
    print(f"Firewall detectado: {sistema}")

    # macOS é POR APP (libera o Python), não por porta — e costuma vir desligado.
    if cortina.por_aplicativo(sistema):
        ligado = cortina.estado_macos()
        if ligado is False:
            print("  O firewall do Mac está DESLIGADO — nada bloqueia, não precisa abrir nada.")
            return 0
        print("  No Mac libera-se o PROGRAMA (o Python que roda o Ekodide), não a porta.")
    else:
        rotulo = {True: "liberada", False: "FECHADA", None: "?"}
        for chave, ok in cortina.portas_liberadas(portas, sistema).items():
            print(f"  {chave}: {rotulo[ok]}")

    if args.abrir:
        comoabre = "vai pedir sudo" if sistema != "netsh" else "precisa de um prompt de Administrador"
        print(f"Liberando ({comoabre})…")
        rc = cortina.liberar(portas, sistema)
        if rc == 0:
            print("Pronto.")
        elif sistema == "netsh":
            print("Falhou — provável falta de Administrador. Abra o Prompt de Comando como")
            print("Administrador e rode os comandos abaixo:")
            for c in cortina.comandos(portas, sistema):
                print(f"  {c}")
        else:
            print("Algo falhou ao abrir — rode os comandos à mão.")
        return rc
    print("\nPra liberar:")
    for c in cortina.comandos(portas, sistema):
        print(f"  {c}")
    nota = "  (no Windows, rode num Prompt de Administrador)" if sistema == "netsh" else \
           "  (ou rode:  ekodide firewall --abrir)"
    print(f"\n{nota}")
    return 0


def _cmd_devices(args) -> int:
    print("Procurando aparelhos Ekodide na rede…")
    achados = vizinhanca.procurar(timeout=args.tempo)
    if not achados:
        print("Nenhum encontrado. (O outro lado está com 'ekodide serve --host 0.0.0.0'?)")
        return 1
    print(f"{len(achados)} aparelho(s):")
    for ap in achados:
        print(f"  {ap['nome']:<16} {vizinhanca.url_de(ap)}")
    print("\nEnvie com:  ekodide send <arquivo> --para <nome>")
    return 0


def _cmd_pair(args) -> int:
    cfg = config.carregar()
    if args.frase:  # esta ponta RECEBE a frase ditada pela outra
        cfg["segredo"] = args.frase
        config.salvar(cfg)
        print(f"Pareado. Segredo guardado em {config.caminho()} (cadeado 600).")
        return 0
    # esta ponta GERA a frase e a mostra pra ditar na outra
    nova = frase.gerar(palavras=args.palavras)
    cfg["segredo"] = nova
    config.salvar(cfg)
    print("Frase-código gerada e guardada AQUI. Digite-a no OUTRO aparelho:\n")
    print(f"    ekodide pair {nova}\n")
    print("Ela é o segredo (a chave do cadeado) — não trafega pela rede; passe pela")
    print("tela/voz. Depois confira quem está on com:  ekodide devices")
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
    elif args.acao == "nome":
        cfg["nome"] = args.valor
        config.salvar(cfg)
        print(f"Nome deste aparelho na rede = {args.valor}")
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
    s.add_argument("--descobrir", action="store_true",
                   help="acha o destino pela rede (ignora o IP da config — útil se mudou)")
    s.set_defaults(func=_cmd_send)

    v = sub.add_parser("serve", help="sobe a ponta que escuta e grava o que chega")
    v.add_argument("--dir", help="pasta destino (padrão: config ou ~/Downloads)")
    v.add_argument("--porta", type=int, help="porta (padrão: config ou 8778)")
    v.add_argument("--host", help="0.0.0.0 pra abrir na LAN (padrão: 127.0.0.1)")
    v.set_defaults(func=_cmd_serve)

    d = sub.add_parser("devices", help="lista aparelhos Ekodide visíveis na rede (sem digitar IP)")
    d.add_argument("--tempo", type=float, default=2.5, help="segundos de escuta (padrão: 2.5)")
    d.set_defaults(func=_cmd_devices)

    pr = sub.add_parser("pair", help="parear: sem frase, gera e mostra; com frase, recebe a do outro")
    pr.add_argument("frase", nargs="?", help="a frase-código ditada pelo outro aparelho")
    pr.add_argument("--palavras", type=int, default=6, help="tamanho da frase ao gerar (padrão: 6)")
    pr.set_defaults(func=_cmd_pair)

    fw = sub.add_parser("firewall", help="checa/libera as portas do Ekodide (no lado que recebe)")
    fw.add_argument("--abrir", action="store_true", help="roda o comando pra liberar (pede sudo)")
    fw.set_defaults(func=_cmd_firewall)

    c = sub.add_parser("config", help="mexe na config (segredo, destinos, nome)")
    csub = c.add_subparsers(dest="acao", required=True)
    cseg = csub.add_parser("segredo", help="guarda o segredo (a mesma chave das duas pontas)")
    cseg.add_argument("valor")
    cdes = csub.add_parser("destino", help="cadastra/atualiza um destino")
    cdes.add_argument("nome")
    cdes.add_argument("url")
    cnom = csub.add_parser("nome", help="como este aparelho aparece na descoberta (padrão: hostname)")
    cnom.add_argument("valor")
    csub.add_parser("show", help="mostra a config (segredo mascarado)")
    c.set_defaults(func=_cmd_config)

    return p


def main(argv: list[str] | None = None) -> int:
    args = construir_parser().parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
