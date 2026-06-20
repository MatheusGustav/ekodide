"""O voo completo: carteiro -> lacre -> recebedor -> caixa postal, por HTTP de
verdade em localhost. O papagaio repete sem errar: o sha256 do que chega bate com
o do que saiu."""
import threading
from hashlib import sha256
from http.server import ThreadingHTTPServer

import pytest

from ekodide import carteiro, enviar
from ekodide.recebedor import criar_handler

SEGREDO = "chave-de-teste"


def _sha(p):
    return sha256(p.read_bytes()).hexdigest()


@pytest.fixture()
def servidor(tmp_path):
    """Sobe o recebedor de verdade numa porta efêmera; grava em tmp_path/recebidos."""
    base = tmp_path / "recebidos"
    base.mkdir()
    srv = ThreadingHTTPServer(("127.0.0.1", 0), criar_handler(base.resolve(), SEGREDO))
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    host, porta = srv.server_address
    yield f"http://{host}:{porta}", base
    srv.shutdown()


def test_arquivo_chega_identico(servidor, tmp_path):
    url, base = servidor
    origem = tmp_path / "doc.txt"
    origem.write_bytes(b"papagaio \x00\x01\x02 binario")
    r = enviar(origem, url, SEGREDO)
    assert r.ok and _sha(base / "doc.txt") == _sha(origem)


def test_pasta_preserva_estrutura(servidor, tmp_path):
    url, base = servidor
    raiz = tmp_path / "Fotos"
    (raiz / "sub").mkdir(parents=True)
    (raiz / "a.txt").write_bytes(b"aaa")
    (raiz / "sub" / "b.txt").write_bytes(b"bbb")
    r = enviar(raiz, url, SEGREDO)
    assert r.ok and r.enviados == 2 and r.total == 2
    assert (base / "Fotos" / "a.txt").read_bytes() == b"aaa"
    assert (base / "Fotos" / "sub" / "b.txt").read_bytes() == b"bbb"


def test_arquivo_grande_picado_remonta_identico(servidor, tmp_path, monkeypatch):
    url, base = servidor
    monkeypatch.setattr(carteiro, "PEDACO", 4)  # 10 bytes -> 3 pedaços
    origem = tmp_path / "grande.bin"
    origem.write_bytes(bytes(range(10)))
    r = enviar(origem, url, SEGREDO)
    assert r.ok and _sha(base / "grande.bin") == _sha(origem)


def test_midia_mp4_mp3_chega_identica(servidor, tmp_path, monkeypatch):
    """Mídia (mp4/mp3) é só bytes pro Ekodide — tem que chegar igualzinha, inclusive
    PICADA. Forjamos os bytes na hora (sem ffmpeg) pra travar a 'cópia perfeita'
    contra regressão. NÃO testa tocabilidade: 'tratar' vídeo é fora de escopo."""
    url, base = servidor
    monkeypatch.setattr(carteiro, "PEDACO", 64 * 1024)  # força o mp4 a ir em pedaços
    # cabeçalhos plausíveis + miolo binário variado; o mp4 passa do PEDACO de propósito
    mp4 = tmp_path / "video.mp4"
    mp4.write_bytes(b"\x00\x00\x00\x18ftypmp42" + bytes(range(256)) * 700)
    mp3 = tmp_path / "musica.mp3"
    mp3.write_bytes(b"ID3\x03\x00\x00\x00" + bytes(range(256)) * 4)
    for origem in (mp4, mp3):
        r = enviar(origem, url, SEGREDO)
        assert r.ok and _sha(base / origem.name) == _sha(origem)


def test_retoma_de_onde_parou(servidor, tmp_path, monkeypatch):
    """Simula a rede caindo no meio: só os 2 primeiros pedaços chegaram. Um novo
    envio tem que RETOMAR (pular o que já chegou) e terminar byte-idêntico."""
    url, base = servidor
    monkeypatch.setattr(carteiro, "PEDACO", 4)  # 10 bytes -> 3 pedaços
    origem = tmp_path / "grande.bin"
    origem.write_bytes(bytes(range(10)))
    tamanho = origem.stat().st_size
    linha = carteiro._Linha(url)
    # "metade chegou": manda os pedaços 0 e 1 na mão; a rede 'cai' antes do 2
    with origem.open("rb") as f:
        for i in range(2):
            ok, _ = carteiro._postar(linha, "grande.bin", f.read(4), SEGREDO, i, 3, tamanho)
            assert ok
    assert not (base / "grande.bin").exists()  # ainda incompleto
    # o destino já confirma ter 2 pedaços
    assert carteiro._ja_recebidos(linha, "grande.bin", SEGREDO, 3, tamanho) == 2
    linha.fechar()
    # novo envio: retoma e fecha idêntico
    r = enviar(origem, url, SEGREDO)
    assert r.ok and _sha(base / "grande.bin") == _sha(origem)


def test_pedaco_repetido_nao_corrompe(tmp_path):
    """Reenvio de um pedaço já gravado (queda da rede com ACK perdido) é ignorado,
    sem duplicar bytes — e o arquivo final sai certinho."""
    from ekodide.caixa_postal import guardar_pedaco, progresso_de
    guardar_pedaco("g.bin", b"AAAA", 0, 3, tmp_path, 12)
    guardar_pedaco("g.bin", b"BBBB", 1, 3, tmp_path, 12)
    assert guardar_pedaco("g.bin", b"BBBB", 1, 3, tmp_path, 12) is None  # repetido
    assert progresso_de("g.bin", 3, tmp_path, 12) == 2
    final = guardar_pedaco("g.bin", b"CCCC", 2, 3, tmp_path, 12)
    assert final.read_bytes() == b"AAAABBBBCCCC"


def test_pedaco_fora_de_ordem_recusado(tmp_path):
    """Pular um pedaço deixaria um buraco no arquivo — tem que ser recusado."""
    from ekodide.caixa_postal import guardar_pedaco
    guardar_pedaco("g.bin", b"AAAA", 0, 3, tmp_path, 12)
    with pytest.raises(ValueError):
        guardar_pedaco("g.bin", b"CCCC", 2, 3, tmp_path, 12)  # pulou o pedaço 1


def test_conteudo_vai_cifrado_na_rede(servidor, tmp_path):
    """O que importa do cofre na prática: o conteúdo NÃO trafega em claro. Espiamos
    cada corpo que sai e confirmamos que o texto-segredo não aparece — mas o arquivo
    chega byte-idêntico mesmo assim."""
    url, base = servidor
    marca = b"SENHA-SUPER-SECRETA-1234567890"
    origem = tmp_path / "segredo.txt"
    origem.write_bytes(b"prefixo " + marca + b" sufixo")

    capturado = []
    original = carteiro._Linha.postar

    def espiao(self, caminho, corpo):
        capturado.append(corpo)
        return original(self, caminho, corpo)

    carteiro._Linha.postar = espiao
    try:
        r = enviar(origem, url, SEGREDO)
    finally:
        carteiro._Linha.postar = original

    assert r.ok
    assert (base / "segredo.txt").read_bytes() == origem.read_bytes()  # idêntico
    assert capturado and all(marca not in corpo for corpo in capturado)  # nada em claro


def test_segredo_errado_nao_grava(servidor, tmp_path):
    url, base = servidor
    origem = tmp_path / "x.txt"
    origem.write_bytes(b"oi")
    r = enviar(origem, url, "segredo-errado")
    assert not r.ok and not (base / "x.txt").exists()
