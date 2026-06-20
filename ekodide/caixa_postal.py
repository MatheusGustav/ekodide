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


def _ler_progresso(alvo_dir: Path, filename: str, partes: int, tamanho: int) -> int:
    """Quantos pedaços contíguos já temos no '.parcial' — lido do anotador
    '.parcial.meta'. Só vale se o meta casar com ESTE arquivo (mesmo nº de partes e
    mesmo tamanho total); senão devolve 0 (é outro arquivo de mesmo nome → recomeça)."""
    parcial = alvo_dir / (filename + ".parcial")
    meta = alvo_dir / (filename + ".parcial.meta")
    if not (parcial.exists() and meta.exists()):
        return 0
    try:
        mp, mr, mt = meta.read_text().split()
        if int(mp) == partes and int(mt) == tamanho:
            return max(0, min(int(mr), partes))
    except (ValueError, OSError):
        pass
    return 0


def progresso_de(nome: str, partes: int, base: Path, tamanho: int = -1) -> int:
    """Quantos pedaços deste arquivo o destino já tem (pro carteiro RETOMAR de onde
    parou). 0 = nada ainda / arquivo diferente. Mesma cerca de segurança do guardar."""
    base = base.resolve()
    alvo_dir, filename = _caminho_seguro(nome, base)
    return _ler_progresso(alvo_dir, filename, partes, tamanho)


def guardar_pedaco(
    nome: str, conteudo: bytes, parte: int, partes: int, base: Path, tamanho: int = -1
) -> Path | None:
    """Recebe UM pedaço de um arquivo grande e vai montando num arquivo temporário
    '.parcial', anotando o progresso no '.parcial.meta' (pra dar pra RETOMAR depois).
    No ÚLTIMO pedaço fecha, renomeia pro nome final (sem sobrescrever), apaga o meta e
    devolve o caminho. Enquanto monta, devolve None.

    Retomada/idempotência: o pedaço já recebido é ignorado (reenvio após queda da rede
    não corrompe); pedaço fora de ordem (pulou um) é recusado. Mesma cerca do guardar."""
    base = base.resolve()
    alvo_dir, filename = _caminho_seguro(nome, base)
    alvo_dir.mkdir(parents=True, exist_ok=True)
    parcial = alvo_dir / (filename + ".parcial")
    meta = alvo_dir / (filename + ".parcial.meta")

    recebidos = _ler_progresso(alvo_dir, filename, partes, tamanho)
    if parte < recebidos:        # já temos esse pedaço — reenvio repetido, ignora
        return None
    if parte > recebidos:        # pulou um pedaço: não dá pra anexar com buraco
        raise ValueError(f"pedaço fora de ordem (esperava {recebidos}, veio {parte})")

    with parcial.open("wb" if parte == 0 else "ab") as f:
        f.write(conteudo)
    recebidos = parte + 1

    if recebidos >= partes:  # último pedaço: vira o arquivo final
        final = _nome_livre(alvo_dir, filename)
        parcial.replace(final)
        meta.unlink(missing_ok=True)
        return final
    meta.write_text(f"{partes} {recebidos} {tamanho}")
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
        tamanho = int(carga.get("tamanho", -1))  # total do arquivo (pra travar a retomada)
        if partes < 1 or parte < 0 or parte >= partes:
            raise ValueError("índice de pedaço inválido")
        return guardar_pedaco(nome, conteudo, parte, partes, base, tamanho)
    return guardar(nome, conteudo, base)
