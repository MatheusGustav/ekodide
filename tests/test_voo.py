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


def test_segredo_errado_nao_grava(servidor, tmp_path):
    url, base = servidor
    origem = tmp_path / "x.txt"
    origem.write_bytes(b"oi")
    r = enviar(origem, url, "segredo-errado")
    assert not r.ok and not (base / "x.txt").exists()
