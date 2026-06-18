"""A vizinhança do Ekodide: descobre quem está na rede SEM digitar IP.

Cada ponta que está escutando (`ekodide serve`) "grita" de tempos em tempos um
pacotinho UDP no broadcast da LAN: *"oi, sou o <nome>, atendo na porta <porta>"*.
Quem quer enviar só ESCUTA por alguns segundos e monta a lista de aparelhos.

O IP NÃO viaja no pacote — quem escuta lê o endereço do remetente (`recvfrom`).
Assim, se o IP mudar (DHCP), a descoberta continua certa: o nome resolve pro IP
de agora, não pro de ontem.

Continua zero-dependência (só `socket`/`json`/`threading`/`time`) e determinístico:
isto só anuncia presença e escuta — quem decide enviar é quem aciona. NÃO carrega
o segredo nem conteúdo; é só a plaquinha de "estou aqui".
"""
from __future__ import annotations

import json
import socket
import threading
import time

# Porta separada da transferência (8778): aqui só trafega o anúncio de presença.
PORTA_DESCOBERTA = 8779
# Marca pra ignorar pacote de outro programa que caia na mesma porta.
MARCA = "ekodide-vizinho-1"
# Pra onde o anúncio é jogado. 255.255.255.255 = broadcast do enlace local (a LAN).
BROADCAST = "255.255.255.255"


def _pacote(nome: str, porta: int) -> bytes:
    return json.dumps({"marca": MARCA, "nome": nome, "porta": porta}).encode("utf-8")


def anunciar(
    nome: str,
    porta: int,
    parar: threading.Event | None = None,
    intervalo: float = 2.0,
    enderecos: list[str] | None = None,
) -> threading.Event:
    """Fica gritando 'estou aqui' até `parar` ser acionado. Bloqueia — pra rodar
    junto do recebedor use `anunciar_em_thread`. Devolve o Event de parada.

    Por padrão grita no broadcast da LAN (pros outros aparelhos) E no 127.0.0.1
    (pra você conferir na mesma máquina — broadcast não faz loopback pra si mesmo)."""
    parar = parar or threading.Event()
    enderecos = enderecos if enderecos is not None else [BROADCAST, "127.0.0.1"]
    msg = _pacote(nome, porta)
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    s.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)
    try:
        while not parar.is_set():
            for endereco in enderecos:
                try:
                    s.sendto(msg, (endereco, PORTA_DESCOBERTA))
                except OSError:
                    pass  # rede caiu/sem enlace agora — tenta de novo no próximo ciclo
            parar.wait(intervalo)
    finally:
        s.close()
    return parar


def anunciar_em_thread(nome: str, porta: int, **kw) -> threading.Event:
    """Sobe o anúncio numa thread daemon e volta na hora. Acione o Event devolvido
    (`.set()`) pra parar de anunciar."""
    parar = threading.Event()
    alvo = lambda: anunciar(nome, porta, parar=parar, **kw)
    threading.Thread(target=alvo, daemon=True).start()
    return parar


def procurar(timeout: float = 2.5, porta: int = PORTA_DESCOBERTA) -> list[dict]:
    """Escuta os anúncios por `timeout` segundos e devolve os aparelhos vistos:
    lista de {"nome", "ip", "porta"}, ordenada por nome. Um aparelho só conta uma
    vez (o anúncio mais recente vence, caso a porta mude)."""
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    try:
        s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEPORT, 1)  # vários ouvintes no mesmo host
    except (AttributeError, OSError):
        pass
    s.bind(("", porta))
    s.settimeout(0.4)
    achados: dict[str, dict] = {}
    fim = time.monotonic() + timeout
    try:
        while time.monotonic() < fim:
            try:
                dados, remetente = s.recvfrom(2048)
            except socket.timeout:
                continue
            except OSError:
                break
            try:
                p = json.loads(dados)
            except ValueError:
                continue
            if not isinstance(p, dict) or p.get("marca") != MARCA:
                continue
            nome = p.get("nome")
            porta_aparelho = p.get("porta")
            if not isinstance(nome, str) or not isinstance(porta_aparelho, int):
                continue
            achados[nome] = {"nome": nome, "ip": remetente[0], "porta": porta_aparelho}
    finally:
        s.close()
    return sorted(achados.values(), key=lambda d: d["nome"])


def url_de(aparelho: dict) -> str:
    """Monta a URL de transferência ('http://IP:PORTA') a partir de um achado."""
    return f"http://{aparelho['ip']}:{aparelho['porta']}"
