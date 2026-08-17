"""A mala do Ekodide: junta uma pasta (ou um arquivo) num .zip só, pra viajar.

Existe porque pasta com 500 arquivinhos hoje são 500 envios separados — cada um com
sua ida e volta de rede. Fechada na mala, vira UM envio.

Duas travas de propósito:

  - **Fora do caminho do `send`.** Zipar MUDA os bytes, e byte-idêntico é pilar da
    casa. Então isto é comando à parte (`ekodide zipar`), que o dono chama de
    propósito — nunca automático em cima de quem manda arquivo. O que o carteiro
    leva depois é o .zip, esse sim byte-idêntico.
  - **Gera arquivo NOVO, nunca mexe no original.** A origem fica intocada; se o
    destino já existe, recusa em vez de passar por cima.

Só biblioteca padrão (`zipfile`), zero dependência nova. Escreve arquivo por
arquivo, sem carregar nada inteiro na memória — a máquina pode ser magra.

Lógica pura (sem rede, sem config): recebe caminhos, devolve um MalaResultado
neutro — quem aciona monta a própria frase.
"""
from __future__ import annotations

import zipfile
from dataclasses import dataclass
from pathlib import Path


@dataclass
class MalaResultado:
    """O que a mala devolve — dados crus, sem frase pronta."""

    ok: bool
    saida: Path | None = None        # o .zip gerado
    total: int = 0                   # quantos arquivos entraram
    bytes_origem: int = 0            # soma do que entrou
    bytes_zip: int = 0               # tamanho do .zip
    erro: str = ""                   # vazio = deu certo


def caminho_padrao(origem: Path) -> Path:
    """Onde o .zip cai por padrão: ao LADO da origem, com o nome dela + '.zip'
    ('Fotos' -> 'Fotos.zip', 'video.mp4' -> 'video.mp4.zip'). O nome inteiro fica no
    meio de propósito — assim dá pra ler o que tem dentro sem abrir."""
    return origem.parent / (origem.name + ".zip")


def _arquivos_de(origem: Path, saida: Path) -> list[tuple[Path, str]]:
    """Lista (arquivo no disco, nome dentro do zip). Pasta preserva as subpastas e
    entra com o próprio nome na frente ('Fotos/sub/img.png') — assim quem abre não
    espalha tralha na pasta atual. O PRÓPRIO .zip é pulado se estiver na origem
    (senão a mala tentaria se guardar dentro de si mesma)."""
    if origem.is_file():
        return [(origem, origem.name)]
    achados = []
    for p in sorted(origem.rglob("*")):
        if not p.is_file() or p.resolve() == saida:
            continue
        achados.append((p, (Path(origem.name) / p.relative_to(origem)).as_posix()))
    return achados


def zipar(origem: Path, saida: Path | None = None) -> MalaResultado:
    """Fecha a mala: junta `origem` (arquivo ou pasta) num .zip. Sem `saida`, cai ao
    lado da origem. Recusa (sem escrever nada) se a origem não existe, se a pasta está
    vazia ou se o destino já existe. Se der erro no meio, apaga o .zip pela metade —
    não fica lixo pra trás."""
    origem = Path(origem).expanduser()
    if not origem.exists():
        return MalaResultado(ok=False, erro=f"não achei: {origem}")
    if not origem.is_file() and not origem.is_dir():
        return MalaResultado(ok=False, erro=f"não é arquivo nem pasta: {origem}")

    saida = Path(saida).expanduser() if saida is not None else caminho_padrao(origem)
    if saida.exists():
        return MalaResultado(ok=False, saida=saida, erro=f"já existe: {saida}")

    itens = _arquivos_de(origem, saida.resolve())
    if not itens:
        return MalaResultado(ok=False, saida=saida, erro=f"'{origem.name}' está vazia — nada pra zipar")

    bytes_origem = 0
    try:
        saida.parent.mkdir(parents=True, exist_ok=True)
        # ZIP_DEFLATED: o zipfile escreve arquivo por arquivo, lendo aos pedaços —
        # nada é carregado inteiro na memória.
        with zipfile.ZipFile(saida, "w", zipfile.ZIP_DEFLATED) as zf:
            for arq, nome in itens:
                zf.write(arq, nome)
                bytes_origem += arq.stat().st_size
    except (OSError, zipfile.BadZipFile) as erro:
        saida.unlink(missing_ok=True)  # nada de mala pela metade no disco
        return MalaResultado(ok=False, saida=saida, erro=f"não fechei a mala: {erro}")
    except BaseException:  # Ctrl+C no meio também não deixa rastro
        saida.unlink(missing_ok=True)
        raise

    return MalaResultado(
        ok=True, saida=saida, total=len(itens),
        bytes_origem=bytes_origem, bytes_zip=saida.stat().st_size,
    )
