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
    compartilhar = args.compartilhar or receber.get("compartilhar")
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
    servir(
        Path(base).expanduser(), segredo, host=host, porta=int(porta),
        compartilhar=Path(compartilhar).expanduser() if compartilhar else None,
    )
    return 0


def _tam_humano(n: int) -> str:
    """Tamanho legível: 2.0 KB, 14.8 MB… (pra listagem do que dá pra puxar)."""
    tam = float(n)
    for unidade in ("B", "KB", "MB", "GB", "TB"):
        if tam < 1024 or unidade == "TB":
            return f"{int(tam)} {unidade}" if unidade == "B" else f"{tam:.1f} {unidade}"
        tam /= 1024
    return f"{n} B"


def _cmd_pull(args) -> int:
    from .buscador import puxar

    try:
        url = _resolver_destino(args.de, args.descobrir)
        segredo = config.segredo()
    except config.ErroConfig as erro:
        print(erro, file=sys.stderr)
        return 1
    cfg = config.carregar()
    destino_dir = args.dir or (cfg.get("receber") or {}).get("dir") or "~/Downloads"
    ok, info = puxar(args.arquivo, url, segredo, Path(destino_dir).expanduser(),
                     pasta=args.pasta)
    if ok:
        print(f"Puxei '{args.arquivo}' de '{args.de}'. Salvo em: {info}")
    else:
        print(f"Não consegui puxar '{args.arquivo}': {info}", file=sys.stderr)
    return 0 if ok else 1


def _cmd_list(args) -> int:
    from .buscador import ErroPuxar, listar, navegar

    try:
        url = _resolver_destino(args.de, args.descobrir)
        segredo = config.segredo()
    except config.ErroConfig as erro:
        print(erro, file=sys.stderr)
        return 1

    if args.pasta is not None:
        # Navegação por pastas: vista RASA (um nível, como um 'ls' remoto).
        try:
            vista = navegar(url, segredo, args.pasta)
        except ErroPuxar as erro:
            print(f"Não consegui navegar em '{args.de}': {erro}", file=sys.stderr)
            return 1
        rotulo = args.pasta or "(raiz)"
        if not vista["pastas"] and not vista["itens"]:
            print(f"'{rotulo}' está vazia em '{args.de}'.")
            return 0
        print(f"Em '{args.de}', pasta '{rotulo}':")
        for p in vista["pastas"]:
            base = f"{args.pasta}/{p}" if args.pasta else p
            print(f"      pasta  {p}/   (desça com: --pasta \"{base}\")")
        for it in vista["itens"]:
            print(f"  {_tam_humano(it['tamanho']):>9}  {it['nome']}")
        if vista["itens"]:
            print(f"\nPuxe com:  ekodide pull <arquivo> --de {args.de} --pasta \"{args.pasta}\"")
        return 0

    try:
        itens = listar(url, segredo)
    except ErroPuxar as erro:
        print(f"Não consegui listar de '{args.de}': {erro}", file=sys.stderr)
        return 1
    if not itens:
        print(f"'{args.de}' não está compartilhando nada pra puxar "
              f"(o outro lado serve com --compartilhar <pasta>?).")
        return 0
    print(f"Disponível em '{args.de}' pra puxar:")
    for it in itens:
        print(f"  {_tam_humano(it['tamanho']):>9}  {it['nome']}")
    print(f"\nPuxe com:  ekodide pull <arquivo> --de {args.de}")
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


def _adotar_codigo(cfg: dict, texto: str) -> int:
    """Adota um código vindo de outra tela. Só passa o formato SORTEADO com o
    verificador batendo — 'definir a própria senha' não existe por construção."""
    try:
        cfg["segredo"] = frase.validar(texto)
    except ValueError as erro:
        print(f"Código recusado: {erro}", file=sys.stderr)
        print("Código de pareamento é sempre SORTEADO (rode 'ekodide pair' na outra "
              "ponta) — senha escolhida por humano cai em dicionário.", file=sys.stderr)
        return 1
    config.salvar(cfg)
    print(f"Pareado. Segredo guardado em {config.caminho()} (cadeado 600).")
    print("Confira quem está on com:  ekodide devices")
    return 0


def _desenhar_qr(payload: str) -> None:
    """Desenha o QR no terminal. O QR é só ROUPA pro mesmo código; o extra é opcional —
    sem ele, o código escrito já resolve: mostra a receita e segue (o padrão da casa)."""
    try:
        import qrcode
    except ImportError:
        print("(sem o desenho do QR — pra ganhá-lo:  pipx install 'ekodide[qr]')\n")
        return
    qr = qrcode.QRCode(border=1)
    qr.add_data(payload)
    qr.print_ascii(invert=True)
    print()


def _cmd_pair(args) -> int:
    """UMA entrada estilo login: mostra o código deste lado (QR + escrito) e aceita
    digitar um código vindo de outra tela. Quem sorteia é SEMPRE a máquina."""
    cfg = config.carregar()
    if args.codigo:  # veio digitado de outra tela (ou por script)
        return _adotar_codigo(cfg, args.codigo)

    atual = cfg.get("segredo")
    mostra_atual = False
    if atual and not args.novo:
        try:
            frase.validar(atual)
            mostra_atual = True
        except ValueError:
            pass  # frase antiga de palavras (ou segredo manual): sorteia código novo
    if mostra_atual:
        codigo = atual
        print("Este aparelho JÁ TEM código de pareamento — mostrando o atual, pra somar")
        print("aparelho sem trocar a rede. (--novo sorteia outro e aposenta este.)\n")
    else:
        codigo = frase.gerar()
        cfg["segredo"] = codigo
        config.salvar(cfg)
        print("Código de pareamento sorteado e guardado AQUI (cadeado 600).\n")

    _desenhar_qr(frase.qr_payload(codigo))
    print(f"    {frase.formatar(codigo)}\n")
    print("No celular:  Parear com o computador → escaneie o QR (ou digite o código).")
    print(f"Noutro PC:   ekodide pair {frase.formatar(codigo)}")
    print("O código é o segredo — não trafega pela rede; vai pela tela, câmera ou dedos.")

    digitado = _perguntar("\nVeio um código de OUTRA tela? Digite-o (Enter mantém o de cima): ")
    if digitado:
        return _adotar_codigo(cfg, digitado)
    return 0


def _normalizar_url(texto: str) -> str | None:
    """Aceita 'http://IP:porta', 'IP:porta' ou só 'IP' e devolve a URL completa.
    None se vier vazio. Só IP -> completa com a porta padrão de transferência."""
    texto = (texto or "").strip()
    if not texto:
        return None
    if not texto.startswith(("http://", "https://")):
        if ":" not in texto:
            texto = f"{texto}:{cortina.PORTA_TRANSFERENCIA}"  # só IP -> porta padrão
        texto = "http://" + texto
    return texto


def _perguntar(prompt: str) -> str:
    """input() que não estoura em terminal sem teclado (pipe/script): devolve ''."""
    try:
        return input(prompt).strip()
    except (EOFError, OSError):
        return ""


def _cadastrar_destino(apelido: str) -> str | None:
    """Mostra quem está na rede e deixa ESCOLHER o aparelho; devolve a URL. O IP fica
    escondido — daí em diante você usa só o apelido. Só aparece quem está com a caixa
    aberta (serve) — quem não aparece também não receberia nada."""
    print(f"Procurando aparelhos na rede pra cadastrar '{apelido}'…")
    achados = vizinhanca.procurar()
    if not achados:
        print("  Ninguém apareceu. O outro aparelho precisa estar com a caixa aberta")
        print("  (ekodide serve --host 0.0.0.0). Abra lá e tente de novo.")
        return None
    for i, ap in enumerate(achados, 1):
        print(f"  {i}) {ap['nome']:<16} {vizinhanca.url_de(ap)}")
    escolha = _perguntar("Qual é o aparelho? [número]: ")
    if escolha.isdigit() and 1 <= int(escolha) <= len(achados):
        return vizinhanca.url_de(achados[int(escolha) - 1])
    print("  Escolha inválida.")
    return None


def _cmd_config(args) -> int:
    cfg = config.carregar()
    if args.acao == "segredo":
        cfg["segredo"] = args.valor
        config.salvar(cfg)
        print(f"Segredo guardado em {config.caminho()} (cadeado 600).")
    elif args.acao == "destino":
        # sem url -> escolhe da rede; com url (avançado/scripts) aceita IP cru ou completo
        url = _normalizar_url(args.url) if args.url else _cadastrar_destino(args.nome)
        if not url:
            print("Cadastro cancelado (sem endereço).", file=sys.stderr)
            return 1
        cfg.setdefault("destinos", {})[args.nome] = url
        config.salvar(cfg)
        print(f"Destino '{args.nome}' = {url}")
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


def _cmd_mcp(args) -> int:
    """Sobe a tomada MCP. O `mcp` é extra OPCIONAL: sem ele, recusa com a receita
    em vez de estourar — quem só manda arquivo não precisa carregar essa mala."""
    try:
        from .tomada import servir
    except ImportError:
        print(
            "Pra ligar o Ekodide num agente de IA falta o extra do MCP.\n"
            "Instale com:  pipx install 'ekodide[agente]'   "
            "(ou pip install 'ekodide[agente]')",
            file=sys.stderr,
        )
        return 1
    # Daqui pra frente o stdout é do PROTOCOLO — nada de print.
    print("Tomada MCP de pé (stdio). Ctrl+C encerra.", file=sys.stderr)
    try:
        servir()
    except KeyboardInterrupt:
        pass
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
    v.add_argument("--compartilhar", help="pasta que o outro lado pode PUXAR (padrão: nada exposto)")
    v.set_defaults(func=_cmd_serve)

    pl = sub.add_parser("pull", help="puxa um arquivo que outro aparelho compartilha")
    pl.add_argument("arquivo", help="nome do arquivo (como aparece no 'ekodide list')")
    pl.add_argument("--de", required=True, help="aparelho de onde puxar (ex.: pc, celular)")
    pl.add_argument("--dir", help="onde salvar (padrão: config ou ~/Downloads)")
    pl.add_argument("--pasta", help="pasta da origem de onde puxar (navegação; ex.: DCIM/Camera)")
    pl.add_argument("--descobrir", action="store_true",
                    help="acha a origem pela rede (ignora o IP da config)")
    pl.set_defaults(func=_cmd_pull)

    li = sub.add_parser("list", help="lista o que outro aparelho compartilha pra puxar")
    li.add_argument("--de", required=True, help="aparelho a consultar (ex.: pc, celular)")
    li.add_argument("--pasta", help="navega numa pasta da origem (ex.: DCIM/Screenshots; '' = raiz)")
    li.add_argument("--descobrir", action="store_true",
                    help="acha a origem pela rede (ignora o IP da config)")
    li.set_defaults(func=_cmd_list)

    d = sub.add_parser("devices", help="lista aparelhos Ekodide visíveis na rede (sem digitar IP)")
    d.add_argument("--tempo", type=float, default=2.5, help="segundos de escuta (padrão: 2.5)")
    d.set_defaults(func=_cmd_devices)

    pr = sub.add_parser("pair", help="parear: mostra o código deste lado (QR + escrito) ou adota um digitado")
    pr.add_argument("codigo", nargs="?",
                    help="código vindo de outra tela (sempre sorteado, com verificador)")
    pr.add_argument("--novo", action="store_true",
                    help="sorteia outro código (o antigo deixa de valer nas duas pontas)")
    pr.set_defaults(func=_cmd_pair)

    fw = sub.add_parser("firewall", help="checa/libera as portas do Ekodide (no lado que recebe)")
    fw.add_argument("--abrir", action="store_true", help="roda o comando pra liberar (pede sudo)")
    fw.set_defaults(func=_cmd_firewall)

    sub.add_parser(
        "mcp", help="sobe a tomada MCP: liga o Ekodide num agente de IA"
    ).set_defaults(func=_cmd_mcp)

    c = sub.add_parser("config", help="mexe na config (segredo, destinos, nome)")
    csub = c.add_subparsers(dest="acao", required=True)
    cseg = csub.add_parser("segredo", help="guarda o segredo (a mesma chave das duas pontas)")
    cseg.add_argument("valor")
    cdes = csub.add_parser("destino", help="cadastra um destino: sem url, escolhe da rede")
    cdes.add_argument("nome")
    cdes.add_argument("url", nargs="?", help="http://IP:porta (omita pra escolher da rede)")
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
