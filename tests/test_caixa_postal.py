"""A caixa postal grava o que chega — com a pasta CERCADA (sem travessia, sem
sobrescrever) e remontando pedaços."""
import base64

import pytest

from ekodide import caixa_postal


def test_guardar_escreve_dentro_da_base(tmp_path):
    alvo = caixa_postal.guardar("nota.txt", b"oi", base=tmp_path)
    assert alvo.parent == tmp_path.resolve()
    assert alvo.read_bytes() == b"oi"


def test_guardar_ignora_travessia_de_caminho(tmp_path):
    alvo = caixa_postal.guardar("../../etc/passwd", b"x", base=tmp_path)
    assert tmp_path.resolve() in alvo.resolve().parents
    assert alvo.name == "passwd" and alvo.read_bytes() == b"x"


def test_guardar_recria_subpastas(tmp_path):
    alvo = caixa_postal.guardar("Fotos/sub/img.png", b"img", base=tmp_path)
    assert alvo == tmp_path.resolve() / "Fotos" / "sub" / "img.png"
    assert alvo.read_bytes() == b"img"


def test_guardar_nao_sobrescreve(tmp_path):
    a = caixa_postal.guardar("foto.png", b"um", base=tmp_path)
    b = caixa_postal.guardar("foto.png", b"dois", base=tmp_path)
    assert a != b and a.read_bytes() == b"um" and b.name == "foto (1).png"


def test_guardar_nome_invalido(tmp_path):
    with pytest.raises(ValueError):
        caixa_postal.guardar("..", b"x", base=tmp_path)


def test_guardar_pedaco_monta_na_ordem(tmp_path):
    assert caixa_postal.guardar_pedaco("g.bin", b"AAA", 0, 3, base=tmp_path) is None
    assert caixa_postal.guardar_pedaco("g.bin", b"BBB", 1, 3, base=tmp_path) is None
    alvo = caixa_postal.guardar_pedaco("g.bin", b"CCC", 2, 3, base=tmp_path)
    assert alvo is not None and alvo.read_bytes() == b"AAABBBCCC"
    assert not (tmp_path / "g.bin.parcial").exists()


def test_gravar_recebido_inteiro_e_picado(tmp_path):
    inteiro = {"nome": "x.txt", "conteudo": base64.b64encode(b"oi").decode("ascii")}
    assert caixa_postal.gravar_recebido(inteiro, tmp_path).read_bytes() == b"oi"

    def carga(dados, parte, partes):
        return {"nome": "g.bin", "conteudo": base64.b64encode(dados).decode("ascii"),
                "parte": parte, "partes": partes}
    assert caixa_postal.gravar_recebido(carga(b"AA", 0, 2), tmp_path) is None
    assert caixa_postal.gravar_recebido(carga(b"BB", 1, 2), tmp_path).read_bytes() == b"AABB"
