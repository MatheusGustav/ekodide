"""A caixa postal do Ekodide: grava com segurança o que CHEGA pela rede.

Lógica pura (sem rede, sem variáveis de ambiente): recebe uma carga já aberta
pelo lacre e grava DENTRO de uma pasta `base` que o chamador escolhe. Um ponto de
escrita é poder, então a pasta é cercada:

  - travessia de caminho ('../') é descartada — nunca escapa da base;
  - arquivo existente NÃO é sobrescrito (ganha sufixo ' (1)', ' (2)'…);
  - arquivo grande chega PICADO e é remontado num '.parcial' até o último pedaço.

Quem expõe isso pela rede (HTTP) é o recebedor (recebedor.py). A caixa postal só
sabe gravar — é a parte mais reaproveitável.
"""
from __future__ import annotations

import base64
from pathlib import Path


def _nome_livre(base: Path, nome: str) -> Path:
    """Um caminho que ainda não existe dentro de `base`: 'foto.png', 'foto (1).png'…
    Nunca sobrescreve um arquivo do usuário."""
    alvo = base / nome
    if not alvo.exists():
        return alvo
    tronco, sufixo = alvo.stem, alvo.suffix
    n = 1
    while (base / f"{tronco} ({n}){sufixo}").exists():
        n += 1
    return base / f"{tronco} ({n}){sufixo}"


def _caminho_seguro(nome: str, base: Path) -> tuple[Path, str]:
    """De um `nome` (que pode ser caminho relativo 'Fotos/sub/img.png') devolve
    (pasta_destino, nome_do_arquivo) DENTRO da base, NUNCA escapando dela:
    componentes perigosos ('..', raiz absoluta) são descartados e o resultado é
    conferido contra a base. Levanta ValueError se o nome for inválido."""
    rel = Path(nome)
    if rel.is_absolute():  # caminho absoluto vira relativo (tira a raiz '/')
        rel = Path(*rel.parts[1:])
    # descarta componentes vazios/perigosos ('', '.', '..') -> não dá pra subir de pasta
    partes = [p for p in rel.parts if p not in ("", ".", "..")]
    if not partes:
        raise ValueError("nome de arquivo inválido")
    alvo_dir = base.joinpath(*partes[:-1])
    # cinto e suspensório: a pasta resolvida tem que ficar DENTRO da base
    if base != alvo_dir.resolve() and base not in alvo_dir.resolve().parents:
        raise ValueError("destino fora da pasta permitida")
    return alvo_dir, partes[-1]


def guardar(nome: str, conteudo: bytes, base: Path) -> Path:
    """Grava um arquivo INTEIRO dentro de `base` (recria subpastas, sem escapar,
    sem sobrescrever)."""
    base = base.resolve()
    alvo_dir, filename = _caminho_seguro(nome, base)
    alvo = _nome_livre(alvo_dir, filename)
    alvo_dir.mkdir(parents=True, exist_ok=True)
    alvo.write_bytes(conteudo)
    return alvo


def gravar_fluxo(nome: str, leitor, tamanho: int, base: Path, pedaco: int = 1024 * 1024) -> Path:
    """Grava `tamanho` bytes lidos de `leitor` (um arquivo/stream) dentro de `base`,
    aos pedaços (sem carregar tudo na memória). Mesma cerca do guardar (sem escapar,
    sem sobrescrever). Usado pelo portal web, onde o upload vem como corpo cru."""
    base = base.resolve()
    alvo_dir, filename = _caminho_seguro(nome, base)
    alvo = _nome_livre(alvo_dir, filename)
    alvo_dir.mkdir(parents=True, exist_ok=True)
    restante = tamanho
    with alvo.open("wb") as f:
        while restante > 0:
            bloco = leitor.read(min(pedaco, restante))
            if not bloco:
                break
            f.write(bloco)
            restante -= len(bloco)
    return alvo


def caminho_leitura(nome: str, base: Path) -> Path:
    """Resolve um arquivo pra LER dentro de `base`, sem deixar escapar dela ('../').
    Levanta ValueError (fora da base) ou FileNotFoundError (não existe). Usado pelos
    downloads do portal web."""
    base = base.resolve()
    alvo = (base / nome).resolve()
    if base != alvo and base not in alvo.parents:
        raise ValueError("caminho fora da pasta permitida")
    if not alvo.is_file():
        raise FileNotFoundError(nome)
    return alvo


def guardar_pedaco(
    nome: str, conteudo: bytes, parte: int, partes: int, base: Path
) -> Path | None:
    """Recebe UM pedaço de um arquivo grande e vai montando num arquivo temporário
    '.parcial' (parte 0 cria/zera, as seguintes anexam, na ordem). No ÚLTIMO pedaço
    fecha e renomeia pro nome final (sem sobrescrever) — e devolve esse caminho.
    Enquanto monta, devolve None. Mesma cerca de segurança do guardar."""
    base = base.resolve()
    alvo_dir, filename = _caminho_seguro(nome, base)
    alvo_dir.mkdir(parents=True, exist_ok=True)
    parcial = alvo_dir / (filename + ".parcial")
    with parcial.open("wb" if parte == 0 else "ab") as f:
        f.write(conteudo)
    if parte >= partes - 1:  # último pedaço: vira o arquivo final
        final = _nome_livre(alvo_dir, filename)
        parcial.replace(final)
        return final
    return None


def gravar_recebido(carga: dict, base: Path) -> Path | None:
    """Grava uma carga já desempacotada (do envelope assinado) dentro de `base`.
    Se vier 'partes', é um arquivo grande picado (monta pedaço a pedaço; destino só
    no último); senão é o arquivo inteiro. Levanta KeyError/ValueError em carga
    inválida."""
    nome = carga["nome"]
    conteudo = base64.b64decode(carga["conteudo"], validate=True)
    if "partes" in carga:
        parte, partes = int(carga["parte"]), int(carga["partes"])
        if partes < 1 or parte < 0 or parte >= partes:
            raise ValueError("índice de pedaço inválido")
        return guardar_pedaco(nome, conteudo, parte, partes, base)
    return guardar(nome, conteudo, base)
