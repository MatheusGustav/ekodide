"""O acervo LÊ o que dá pra puxar — com a pasta CERCADA (sem travessia, sem fuga por
symlink) e sem expor os temporários de recebimento."""
import pytest

from ekodide import acervo


def test_listar_traz_arquivos_com_tamanho(tmp_path):
    (tmp_path / "a.txt").write_bytes(b"oi")
    (tmp_path / "b.bin").write_bytes(b"12345")
    itens = acervo.listar(tmp_path)
    assert itens == [
        {"nome": "a.txt", "tamanho": 2},
        {"nome": "b.bin", "tamanho": 5},
    ]


def test_listar_recursivo_em_posix(tmp_path):
    sub = tmp_path / "Fotos" / "sub"
    sub.mkdir(parents=True)
    (sub / "img.png").write_bytes(b"img")
    itens = acervo.listar(tmp_path)
    assert itens == [{"nome": "Fotos/sub/img.png", "tamanho": 3}]


def test_listar_ignora_temporarios_de_recebimento(tmp_path):
    (tmp_path / "ok.txt").write_bytes(b"x")
    (tmp_path / "g.bin.parcial").write_bytes(b"meio")
    (tmp_path / "g.bin.parcial.meta").write_text("2 1 99")
    assert acervo.listar(tmp_path) == [{"nome": "ok.txt", "tamanho": 1}]


def test_listar_pasta_inexistente_ou_none_vem_vazia(tmp_path):
    assert acervo.listar(tmp_path / "nao-existe") == []
    assert acervo.listar(None) == []


def test_ler_pedaco_arquivo_inteiro(tmp_path):
    (tmp_path / "x.txt").write_bytes(b"conteudo")
    assert acervo.ler_pedaco("x.txt", tmp_path, 0, 1) == b"conteudo"


def test_ler_pedaco_picado_na_ordem(tmp_path, monkeypatch):
    monkeypatch.setattr(acervo, "PEDACO", 3)  # pedaço minúsculo pra testar sem GB
    (tmp_path / "g.bin").write_bytes(b"AAABBBCC")
    assert acervo.ler_pedaco("g.bin", tmp_path, 0, 3) == b"AAA"
    assert acervo.ler_pedaco("g.bin", tmp_path, 1, 3) == b"BBB"
    assert acervo.ler_pedaco("g.bin", tmp_path, 2, 3) == b"CC"


def test_recusa_travessia_de_caminho(tmp_path):
    with pytest.raises(ValueError):
        acervo.ler_pedaco("../../etc/passwd", tmp_path, 0, 1)
    with pytest.raises(ValueError):
        acervo.tamanho_de("../segredo", tmp_path)


def test_recusa_fuga_por_symlink(tmp_path):
    fora = tmp_path.parent / "fora.txt"
    fora.write_bytes(b"segredo de fora")
    base = tmp_path / "compartilhado"
    base.mkdir()
    link = base / "atalho.txt"
    try:
        link.symlink_to(fora)
    except (OSError, NotImplementedError):
        pytest.skip("symlink não suportado neste sistema")
    # o atalho até aparece como arquivo, mas LER ele é barrado (alvo real cai fora)
    with pytest.raises(ValueError):
        acervo.ler_pedaco("atalho.txt", base, 0, 1)


def test_tamanho_de(tmp_path):
    (tmp_path / "x.bin").write_bytes(b"12345")
    assert acervo.tamanho_de("x.bin", tmp_path) == 5


def test_ler_pedaco_indice_invalido(tmp_path):
    (tmp_path / "x.txt").write_bytes(b"oi")
    with pytest.raises(ValueError):
        acervo.ler_pedaco("x.txt", tmp_path, 5, 2)
