"""A mala fecha pasta (ou arquivo) num .zip só — sem tocar no original, sem passar
por cima do que já existe e sem deixar mala pela metade no disco."""
import zipfile

from ekodide import cli, mala


def test_zipa_pasta_preservando_subpastas(tmp_path):
    raiz = tmp_path / "Fotos"
    (raiz / "sub").mkdir(parents=True)
    (raiz / "a.txt").write_bytes(b"aaa")
    (raiz / "sub" / "img.png").write_bytes(b"img")

    r = mala.zipar(raiz)

    assert r.ok and r.total == 2
    assert r.saida == tmp_path / "Fotos.zip"
    with zipfile.ZipFile(r.saida) as zf:
        assert sorted(zf.namelist()) == ["Fotos/a.txt", "Fotos/sub/img.png"]


def test_conteudo_volta_byte_identico(tmp_path):
    raiz = tmp_path / "Coisas"
    raiz.mkdir()
    bytes_crus = bytes(range(256)) * 10  # binário de verdade, não só texto
    (raiz / "bin.dat").write_bytes(bytes_crus)

    r = mala.zipar(raiz)

    with zipfile.ZipFile(r.saida) as zf:
        assert zf.read("Coisas/bin.dat") == bytes_crus


def test_zipa_arquivo_solto(tmp_path):
    arq = tmp_path / "video.mp4"
    arq.write_bytes(b"mp4")

    r = mala.zipar(arq)

    assert r.ok and r.total == 1
    assert r.saida == tmp_path / "video.mp4.zip"
    with zipfile.ZipFile(r.saida) as zf:
        assert zf.namelist() == ["video.mp4"]


def test_original_fica_intacto(tmp_path):
    raiz = tmp_path / "Fotos"
    raiz.mkdir()
    (raiz / "a.txt").write_bytes(b"aaa")

    mala.zipar(raiz)

    assert (raiz / "a.txt").read_bytes() == b"aaa"
    assert sorted(p.name for p in raiz.iterdir()) == ["a.txt"]


def test_saida_escolhida_a_mao(tmp_path):
    arq = tmp_path / "doc.txt"
    arq.write_bytes(b"x")
    alvo = tmp_path / "outra" / "mala.zip"

    r = mala.zipar(arq, alvo)

    assert r.ok and r.saida == alvo and alvo.exists()


def test_recusa_passar_por_cima_do_que_ja_existe(tmp_path):
    arq = tmp_path / "doc.txt"
    arq.write_bytes(b"x")
    ja = tmp_path / "doc.txt.zip"
    ja.write_bytes(b"nao me sobrescreva")

    r = mala.zipar(arq)

    assert not r.ok and "já existe" in r.erro
    assert ja.read_bytes() == b"nao me sobrescreva"


def test_pasta_vazia_nao_gera_zip(tmp_path):
    vazia = tmp_path / "Vazia"
    vazia.mkdir()

    r = mala.zipar(vazia)

    assert not r.ok and "vazia" in r.erro
    assert not (tmp_path / "Vazia.zip").exists()


def test_origem_inexistente_recusa(tmp_path):
    r = mala.zipar(tmp_path / "nao-existe")
    assert not r.ok and "não achei" in r.erro


def test_nao_guarda_o_proprio_zip_dentro_de_si(tmp_path):
    raiz = tmp_path / "Fotos"
    raiz.mkdir()
    (raiz / "a.txt").write_bytes(b"aaa")

    r = mala.zipar(raiz, raiz / "mala.zip")  # a saída cai DENTRO da origem

    assert r.ok and r.total == 1
    with zipfile.ZipFile(r.saida) as zf:
        assert zf.namelist() == ["Fotos/a.txt"]


def test_cli_zipar(tmp_path, capsys):
    raiz = tmp_path / "Fotos"
    raiz.mkdir()
    (raiz / "a.txt").write_bytes(b"aaa")

    assert cli.main(["zipar", str(raiz)]) == 0

    saida = capsys.readouterr().out
    assert "Fotos.zip" in saida
    assert (tmp_path / "Fotos.zip").exists()


def test_cli_zipar_falha_devolve_1(tmp_path, capsys):
    assert cli.main(["zipar", str(tmp_path / "nao-existe")]) == 1
