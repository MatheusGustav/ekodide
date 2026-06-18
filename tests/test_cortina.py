"""A cortina (firewall): monta o comando certo por sistema e lista as portas certas.
Não testamos rodar sudo de verdade — só a lógica que decide o quê mostrar."""
from ekodide import cortina


def test_portas_sao_transferencia_tcp_e_descoberta_udp():
    ps = cortina.portas()
    assert (8778, "tcp") in ps
    assert (cortina.PORTA_DESCOBERTA, "udp") in ps


def test_porta_de_transferencia_custom():
    ps = cortina.portas(9000)
    assert (9000, "tcp") in ps


def test_comandos_firewalld():
    cmds = cortina.comandos(cortina.portas(), sistema="firewalld")
    junto = " ".join(cmds)
    assert "firewall-cmd" in junto
    assert "--add-port=8778/tcp" in junto and "--add-port=8779/udp" in junto
    assert any("restart firewalld" in c for c in cmds)


def test_comandos_ufw():
    cmds = cortina.comandos(cortina.portas(), sistema="ufw")
    assert "sudo ufw allow 8778/tcp" in cmds
    assert "sudo ufw allow 8779/udp" in cmds


def test_comandos_desconhecido_e_none():
    assert cortina.comandos(cortina.portas(), sistema="nada-disso") is None


def test_portas_liberadas_desconhecido_da_none():
    estado = cortina.portas_liberadas(cortina.portas(), sistema="desconhecido")
    # firewall desconhecido: não dá pra consultar, cada porta vem como None
    assert set(estado) == {"8778/tcp", "8779/udp"}
    assert all(v is None for v in estado.values())
