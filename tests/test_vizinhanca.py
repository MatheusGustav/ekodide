"""A vizinhança: um anúncio jogado na rede é visto por quem procura, com o IP
lido do remetente (não do pacote). Testes no loopback, sem depender de broadcast."""
import threading

from ekodide import vizinhanca


def test_anuncio_e_descoberta_loopback():
    # anuncia direto pro loopback (sem broadcast, pra rodar em qualquer sandbox)
    parar = vizinhanca.anunciar_em_thread(
        "aparelho-teste", 8778, intervalo=0.2, enderecos=["127.0.0.1"]
    )
    try:
        achados = vizinhanca.procurar(timeout=1.5)
    finally:
        parar.set()

    nomes = {a["nome"]: a for a in achados}
    assert "aparelho-teste" in nomes
    ap = nomes["aparelho-teste"]
    assert ap["porta"] == 8778
    assert ap["ip"] == "127.0.0.1"  # veio do remetente do pacote
    assert vizinhanca.url_de(ap) == "http://127.0.0.1:8778"


def test_nada_na_rede_devolve_lista_vazia():
    assert vizinhanca.procurar(timeout=0.5) == []


def test_ignora_pacote_estranho():
    import json
    import socket

    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    pronto = threading.Event()

    def ruido():
        pronto.wait(0.3)
        for _ in range(5):
            s.sendto(b"isto-nao-e-ekodide", ("127.0.0.1", vizinhanca.PORTA_DESCOBERTA))
            s.sendto(json.dumps({"marca": "outra-coisa"}).encode(),
                     ("127.0.0.1", vizinhanca.PORTA_DESCOBERTA))
            pronto.wait(0.1)

    t = threading.Thread(target=ruido, daemon=True)
    t.start()
    pronto.set()
    try:
        assert vizinhanca.procurar(timeout=0.8) == []  # lixo é descartado
    finally:
        s.close()
