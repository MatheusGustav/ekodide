"""O acervo do Ekodide: o lado de LEITURA que o 'puxar' expõe.

Espelho do caixa_postal (que GRAVA o que chega): aqui a gente LÊ arquivos de dentro
de uma pasta COMPARTILHADA — com a mesma cerca, e um cuidado a mais. Um ponto de
leitura é poder; então só se lê de dentro do que foi explicitamente compartilhado, e:

  - travessia de caminho ('../') é descartada — nunca escapa da pasta;
  - symlink que aponta pra FORA da pasta é recusado (o alvo real cai fora da cerca) —
    risco que o lado de escrita não corre, mas o de leitura sim;
  - os temporários de recebimento ('.parcial'/'.parcial.meta') NÃO entram na lista
    (são montagem em andamento, não arquivo pra compartilhar).

Lógica pura (sem rede, sem variáveis de ambiente): recebe a pasta `base` e um nome
relativo. Quem expõe isso pela rede (HTTP) é o recebedor (rotas /listar e /buscar).
"""
from __future__ import annotations

from pathlib import Path

# Mesmo tamanho de pedaço do carteiro: arquivo grande é lido/devolvido picado, e cada
# pedaço cabe no corpo de 32 MB do recebedor mesmo depois do base64 inchar ~33%.
PEDACO = 16 * 1024 * 1024


def _resolver_dentro(nome: str, base: Path) -> Path:
    """De um `nome` relativo ('Fotos/sub/img.png') devolve o caminho REAL dentro de
    `base`, NUNCA escapando. Componentes perigosos ('', '.', '..', raiz absoluta) são
    descartados; o resultado é resolvido (segue symlink de propósito) e conferido contra
    a base — assim um atalho apontando pra fora é pego. Levanta ValueError se escapar."""
    base = base.resolve()
    rel = Path(nome)
    if rel.is_absolute():  # caminho absoluto vira relativo (tira a raiz '/')
        rel = Path(*rel.parts[1:])
    partes = [p for p in rel.parts if p not in ("", ".", "..")]
    if not partes:
        raise ValueError("nome de arquivo inválido")
    alvo = base.joinpath(*partes).resolve()  # resolve() segue symlink: pega fuga por atalho
    if base != alvo and base not in alvo.parents:
        raise ValueError("fora da pasta compartilhada")
    return alvo


def _e_compartilhavel(p: Path) -> bool:
    """Arquivo comum de verdade — fora os temporários de recebimento em montagem."""
    return p.is_file() and not p.name.endswith((".parcial", ".parcial.meta"))


def listar(base: Path) -> list[dict]:
    """O que dá pra puxar: lista de {'nome': caminho-relativo, 'tamanho': bytes},
    ordenada por nome, recursiva (preserva subpastas). Pasta inexistente ou não
    compartilhada (None) -> lista vazia: nada fica exposto sem querer."""
    if base is None:
        return []
    base = Path(base).expanduser()
    if not base.is_dir():
        return []
    base = base.resolve()
    achados = []
    for p in sorted(base.rglob("*")):
        if _e_compartilhavel(p):
            achados.append({"nome": p.relative_to(base).as_posix(), "tamanho": p.stat().st_size})
    return achados


def tamanho_de(nome: str, base: Path) -> int:
    """Tamanho (bytes) de um arquivo compartilhado. Mesma cerca do `ler_pedaco`."""
    alvo = _resolver_dentro(nome, Path(base).expanduser())
    if not _e_compartilhavel(alvo):
        raise ValueError("arquivo não disponível")
    return alvo.stat().st_size


def ler_pedaco(nome: str, base: Path, parte: int, partes: int) -> bytes:
    """Lê o pedaço `parte` (de `partes`) do arquivo, cada um de até PEDACO bytes (o
    último vem menor). Arquivo que cabe num pedaço vai inteiro com parte=0, partes=1.
    Cerca de segurança: nunca lê fora da pasta compartilhada."""
    if partes < 1 or parte < 0 or parte >= partes:
        raise ValueError("índice de pedaço inválido")
    alvo = _resolver_dentro(nome, Path(base).expanduser())
    if not _e_compartilhavel(alvo):
        raise ValueError("arquivo não disponível")
    with alvo.open("rb") as f:
        f.seek(parte * PEDACO)
        return f.read(PEDACO)
