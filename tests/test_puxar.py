"""O voo ao contrário: o admin PUXA da pasta compartilhada do outro (buscador ->
/buscar -> acervo), por HTTP de verdade. O papagaio repete sem errar nos dois
sentidos: o sha256 do que se puxa bate com o do original."""
import threading
from hashlib import sha256
from http.server import ThreadingHTTPServer

import pytest

from ekodide import buscador
from ekodide.recebedor import criar_handler

SEGREDO = "chave-de-teste"


def _sha(p):
    return sha256(p.read_bytes()).hexdigest()


@pytest.fixture()
def origem_servida(tmp_path):
    """Sobe um recebedor com uma pasta COMPARTILHADA (pra puxar). Devolve
    (url, pasta_compartilhada, pasta_destino_local)."""
    compartilhada = tmp_path / "compartilhado"
    compartilhada.mkdir()
    destino = tmp_path / "baixados"
    destino.mkdir()
    srv = ThreadingHTTPServer(
        ("127.0.0.1", 0),
        criar_handler(tmp_path.resolve(), SEGREDO, compartilhar=compartilhada.resolve()),
    )
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    host, porta = srv.server_address
    yield f"http://{host}:{porta}", compartilhada, destino
    srv.shutdown()


def test_listar_mostra_o_que_da_pra_puxar(origem_servida):
    url, compartilhada, _ = origem_servida
    (compartilhada / "a.txt").write_bytes(b"oi")
    (compartilhada / "Fotos").mkdir()
    (compartilhada / "Fotos" / "b.png").write_bytes(b"imagem")
    itens = buscador.listar(url, SEGREDO)
    assert {"nome": "a.txt", "tamanho": 2} in itens
    assert {"nome": "Fotos/b.png", "tamanho": 6} in itens


def test_puxa_arquivo_identico(origem_servida):
    url, compartilhada, destino = origem_servida
    (compartilhada / "doc.txt").write_bytes(b"papagaio \x00\x01\x02 binario")
    ok, info = buscador.puxar("doc.txt", url, SEGREDO, destino)
    assert ok
    assert _sha(destino / "doc.txt") == _sha(compartilhada / "doc.txt")


def test_puxa_de_subpasta(origem_servida):
    url, compartilhada, destino = origem_servida
    (compartilhada / "Fotos").mkdir()
    (compartilhada / "Fotos" / "b.png").write_bytes(b"conteudo-imagem")
    ok, _ = buscador.puxar("Fotos/b.png", url, SEGREDO, destino)
    assert ok and (destino / "Fotos" / "b.png").read_bytes() == b"conteudo-imagem"


def test_puxa_grande_picado_remonta_identico(origem_servida, monkeypatch):
    url, compartilhada, destino = origem_servida
    monkeypatch.setattr(buscador, "PEDACO", 4)  # 10 bytes -> 3 pedaços
    grande = compartilhada / "grande.bin"
    grande.write_bytes(bytes(range(10)))
    ok, _ = buscador.puxar("grande.bin", url, SEGREDO, destino)
    assert ok and _sha(destino / "grande.bin") == _sha(grande)


def test_conteudo_puxado_vai_cifrado_na_rede(origem_servida):
    """O que volta pelo /buscar não pode trafegar em claro — o cofre vale nos dois
    sentidos. Espiamos as respostas e confirmamos que a marca-segredo não aparece."""
    url, compartilhada, destino = origem_servida
    marca = b"SENHA-SUPER-SECRETA-1234567890"
    (compartilhada / "segredo.txt").write_bytes(b"prefixo " + marca + b" sufixo")

    capturado = []
    original = buscador._Linha.postar

    def espiao(self, caminho, corpo):
        status, bruto = original(self, caminho, corpo)
        capturado.append(bruto)
        return status, bruto

    buscador._Linha.postar = espiao
    try:
        ok, _ = buscador.puxar("segredo.txt", url, SEGREDO, destino)
    finally:
        buscador._Linha.postar = original

    assert ok
    assert (destino / "segredo.txt").read_bytes() == (compartilhada / "segredo.txt").read_bytes()
    assert capturado and all(marca not in corpo for corpo in capturado)  # nada em claro


def test_segredo_errado_nao_puxa(origem_servida):
    url, compartilhada, destino = origem_servida
    (compartilhada / "x.txt").write_bytes(b"oi")
    ok, _ = buscador.puxar("x.txt", url, "segredo-errado", destino, tamanho=2)
    assert not ok and not (destino / "x.txt").exists()


def test_travessia_recusada_pela_rede(origem_servida):
    """Pedir '../' não pode vazar arquivo de fora da pasta compartilhada."""
    url, _, destino = origem_servida
    ok, info = buscador.puxar("../../etc/passwd", url, SEGREDO, destino, tamanho=10)
    assert not ok


def test_arquivo_inexistente(origem_servida):
    url, _, destino = origem_servida
    ok, info = buscador.puxar("nao-existe.txt", url, SEGREDO, destino)
    assert not ok and "disponível" in info


def test_servidor_sem_compartilhar_recusa_buscar(tmp_path):
    """Sem --compartilhar, listar vem vazio e buscar é recusado (puxar desligado)."""
    srv = ThreadingHTTPServer(("127.0.0.1", 0), criar_handler(tmp_path.resolve(), SEGREDO))
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    host, porta = srv.server_address
    url = f"http://{host}:{porta}"
    try:
        assert buscador.listar(url, SEGREDO) == []
        ok, info = buscador.puxar("qualquer.txt", url, SEGREDO, tmp_path, tamanho=5)
        assert not ok
    finally:
        srv.shutdown()
