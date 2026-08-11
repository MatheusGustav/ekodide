"""A tomada: liga o Ekodide em qualquer agente de IA, pelo padrão MCP.

O Ekodide continua burro e determinístico — não tem IA aqui dentro. O que este
arquivo faz é dar ao maquinário um **encaixe de formato padrão**: em vez de cada
agente escrever o próprio adaptador (traduzir as funções pro dialeto dele), o
Ekodide se apresenta sozinho e qualquer cliente MCP o enxerga.

    ekodide mcp        # sobe a tomada; o agente conversa por stdin/stdout

É casca fina: cada ferramenta abaixo resolve o destino e o segredo pela config
(a mesma do CLI), chama a peça de sempre (carteiro/buscador/vizinhança) e traduz
o resultado neutro numa frase. Nenhuma regra de transporte mora aqui.

Duas travas que não podem ser afrouxadas por conveniência:

  - **Nada de `print`.** No transporte stdio, a saída padrão É o canal do
    protocolo: uma linha solta em stdout corrompe a conversa com o agente.
    Recado pra humano vai em stderr, ou não vai.
  - **Ferramenta não estoura.** Toda falha vira frase de volta. Exceção que
    escapa derruba a chamada do agente sem explicar nada.

⚠️ Quem pluga a tomada num agente está dando a ele o mesmo poder do
`ekodide send`/`pull`: mandar arquivo deste computador pra outro aparelho e
trazer de lá. Não é mais poder que o CLI já tinha — mas é poder na mão de quem
decide sozinho. Plugue em agente que você controla.
"""
from __future__ import annotations

from pathlib import Path

from mcp.server import MCPServer

from . import __version__, config, vizinhanca
from .carteiro import enviar
from .cli import _resolver_destino, _tam_humano

# A espiada mostra os primeiros 100 KB e avisa que cortou — espiar não é ler
# livro, e o `limite` corta na origem: o resto do arquivo nem viaja.
ESPIADA_MAX = 100 * 1024

servidor = MCPServer(
    name="ekodide",
    # O cliente lê isto no aperto de mão — sem versão, o agente não tem como
    # saber com qual Ekodide está falando.
    version=__version__,
    instructions=(
        "O Ekodide move arquivos entre aparelhos da mesma rede (PC, celular), "
        "cifrados e byte-idênticos. Use 'aparelhos' pra descobrir quem está na "
        "rede, 'listar_arquivos' pra ver o que o outro lado compartilha, "
        "'espiar_arquivo' pra LER um texto sem baixar nada, e 'puxar_arquivo' "
        "só quando precisar mesmo da cópia em disco. O parâmetro 'de'/'para' é "
        "o apelido do aparelho (ex.: 'celular', 'pc'), não um IP."
    ),
)


def _linha(nome: str) -> tuple[str, str]:
    """(url, segredo) do aparelho — a config vence, senão procura na rede."""
    return _resolver_destino(nome, descobrir=False), config.segredo()


@servidor.tool()
def enviar_arquivo(caminho: str, para: str = "celular") -> str:
    """Envia um ARQUIVO ou uma PASTA INTEIRA deste computador pra outro aparelho
    da rede, cifrado no caminho e byte-idêntico na chegada.

    Args:
        caminho: o arquivo ou a pasta aqui neste computador.
        para: apelido do aparelho que recebe (ex.: 'celular', 'pc').
    """
    origem = Path(caminho).expanduser()
    if not origem.exists():
        return f"Não achei nada em '{origem}' — confira o caminho."
    try:
        url, segredo = _linha(para)
    except config.ErroConfig as erro:
        return f"O Ekodide não está pronto: {erro}"
    try:
        r = enviar(origem, url, segredo)
    except Exception as e:  # noqa: BLE001 — ferramenta nunca estoura
        return f"Quebrou no meio do envio: {e}"

    if r.is_pasta and r.total == 0:
        return f"A pasta '{origem.name}' está vazia — nada foi enviado."
    if not r.ok:
        motivo = r.falhas[0] if r.falhas else "falha sem motivo declarado"
        return (
            f"Não consegui enviar '{origem.name}' pro '{para}': {motivo}. "
            f"O outro lado está com 'ekodide serve' aberto e pareado?"
        )
    if r.is_pasta:
        feito = f"Enviei {r.enviados} de {r.total} arquivo(s) da pasta '{origem.name}' pro '{para}'."
        return f"{feito} Falharam {len(r.falhas)}." if r.falhas else feito
    return f"Enviei '{origem.name}' pro '{para}'. Chegou em: {r.destino}"


@servidor.tool()
def listar_arquivos(de: str = "celular") -> str:
    """Lista o que outro aparelho está COMPARTILHANDO pra ser puxado. Use antes
    de puxar ou espiar, pra descobrir o nome exato do arquivo.

    Args:
        de: apelido do aparelho a consultar (ex.: 'celular', 'pc').
    """
    from .buscador import ErroPuxar, listar

    try:
        url, segredo = _linha(de)
    except config.ErroConfig as erro:
        return f"O Ekodide não está pronto: {erro}"
    try:
        itens = listar(url, segredo)
    except ErroPuxar as erro:
        return f"Não consegui falar com '{de}': {erro}"
    if not itens:
        return (
            f"'{de}' não está compartilhando nada. O outro lado precisa servir "
            f"com 'ekodide serve --compartilhar <pasta>'."
        )
    linhas = "\n".join(f"  {_tam_humano(i['tamanho']):>9}  {i['nome']}" for i in itens)
    return f"Disponível em '{de}':\n{linhas}"


@servidor.tool()
def puxar_arquivo(nome: str, de: str = "celular") -> str:
    """BAIXA um arquivo de outro aparelho pra este computador, GRAVANDO em disco
    (na pasta de recebimento da config). Pra só LER um texto, prefira
    espiar_arquivo — olhar e puxar são atos diferentes.

    Args:
        nome: o nome do arquivo como aparece em listar_arquivos.
        de: apelido do aparelho de onde puxar (ex.: 'celular', 'pc').
    """
    from .buscador import puxar

    try:
        url, segredo = _linha(de)
    except config.ErroConfig as erro:
        return f"O Ekodide não está pronto: {erro}"
    base = (config.carregar().get("receber") or {}).get("dir") or "~/Downloads"
    try:
        ok, info = puxar(nome, url, segredo, Path(base).expanduser())
    except Exception as e:  # noqa: BLE001
        return f"Quebrou no meio do download: {e}"
    if ok:
        return f"Puxei '{nome}' de '{de}'. Salvo em: {info}"
    return f"Não consegui puxar '{nome}' de '{de}': {info}"


@servidor.tool()
def espiar_arquivo(nome: str, de: str = "celular") -> str:
    """LÊ o conteúdo de um arquivo de TEXTO de outro aparelho SEM baixar nada: o
    conteúdo vem cifrado pela rede, fica só na memória e nenhum arquivo é
    gravado aqui. Só serve pra texto — foto, PDF e vídeo não.

    Args:
        nome: o nome do arquivo como aparece em listar_arquivos.
        de: apelido do aparelho a espiar (ex.: 'celular', 'pc').
    """
    from .buscador import espiar

    try:
        url, segredo = _linha(de)
    except config.ErroConfig as erro:
        return f"O Ekodide não está pronto: {erro}"
    try:
        ok, carga, tamanho = espiar(nome, url, segredo, limite=ESPIADA_MAX)
    except Exception as e:  # noqa: BLE001
        return f"Quebrou no meio da espiada: {e}"
    if not ok:
        return f"Não consegui espiar '{nome}' em '{de}': {carga}"

    cortado = tamanho > len(carga)
    try:
        texto = carga.decode("utf-8")
    except UnicodeDecodeError as erro:
        # Corte no meio de um caractere multibyte não é binário — apara o rabo
        # quebrado. Erro longe do fim é binário disfarçado de texto.
        if not (cortado and erro.start >= len(carga) - 3):
            return (
                f"'{nome}' não é texto por dentro (bytes fora do UTF-8). "
                f"Se precisar do arquivo, use puxar_arquivo."
            )
        texto = carga[: erro.start].decode("utf-8")

    aviso = (
        f" O arquivo é maior que a espiada: mostro só os primeiros "
        f"{_tam_humano(ESPIADA_MAX)}." if cortado else ""
    )
    cabecalho = f"'{nome}' ({_tam_humano(tamanho)}) em '{de}' — nada foi gravado aqui.{aviso}"
    return f"{cabecalho} O arquivo está vazio." if not texto else f"{cabecalho}\n\n{texto}"


@servidor.tool()
def aparelhos() -> str:
    """Lista os aparelhos com Ekodide visíveis NESTA rede, com o apelido de cada
    um. Use quando não souber o nome a passar em 'de'/'para', ou pra conferir se
    o outro aparelho está no ar.
    """
    try:
        achados = vizinhanca.procurar()
    except Exception as e:  # noqa: BLE001
        return f"Não consegui procurar na rede: {e}"
    if not achados:
        return (
            "Nenhum aparelho Ekodide visível na rede agora. O outro lado está "
            "ligado, na mesma rede e com 'ekodide serve' aberto?"
        )
    linhas = "\n".join(f"  {a['nome']} — {vizinhanca.url_de(a)}" for a in achados)
    return f"Aparelhos na rede:\n{linhas}"


def servir() -> None:
    """Sobe a tomada no transporte stdio (o que os clientes MCP falam)."""
    servidor.run()
