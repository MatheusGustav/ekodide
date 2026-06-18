"""A cortina (de fogo) do Ekodide: tira o atrito do firewall, sem mágica perigosa.

O lado que RECEBE precisa deixar entrar a transferência (TCP 8778) e a descoberta
(UDP 8779). Abrir isso exige poder de administrador — e abrir caladinho seria furo
de segurança. Então aqui a gente NÃO abre escondido: detecta o firewall, mostra o
comando exato já montado e, se você mandar, executa (você autoriza: senha do sudo
no Linux/Mac, prompt de Administrador no Windows).

Cada sistema é diferente — e isto importa pra não prometer o que não cumpre:
  - Linux (firewalld/ufw): abre POR PORTA.
  - Windows (netsh advfirewall): abre POR PORTA (precisa de Administrador).
  - macOS (Application Firewall): é POR APLICATIVO, não por porta — e vem DESLIGADO
    de fábrica. Desligado: nada a fazer. Ligado: liberamos o programa (o Python),
    não a porta.

Só stdlib (`platform`, `shutil`, `subprocess`, `sys`) — segue zero-dependência.
"""
from __future__ import annotations

import platform
import shutil
import subprocess
import sys

from .vizinhanca import PORTA_DESCOBERTA

PORTA_TRANSFERENCIA = 8778
_MACOS_FW = "/usr/libexec/ApplicationFirewall/socketfilterfw"


def portas(transferencia: int = PORTA_TRANSFERENCIA) -> list[tuple[int, str]]:
    """As portas que o lado que recebe precisa: transferência (TCP) e descoberta (UDP)."""
    return [(transferencia, "tcp"), (PORTA_DESCOBERTA, "udp")]


def _tem(programa: str) -> bool:
    return shutil.which(programa) is not None


def _rodar(args: list[str], timeout: float = 4.0) -> subprocess.CompletedProcess | None:
    try:
        return subprocess.run(args, capture_output=True, text=True, timeout=timeout)
    except (OSError, subprocess.SubprocessError):
        return None


def por_aplicativo(sistema: str | None = None) -> bool:
    """O macOS libera por APP, não por porta — muda a conversa toda. Quem chama usa
    isto pra falar a língua certa (programa, não porta)."""
    return (sistema if sistema is not None else detectar()) == "macos"


def detectar() -> str | None:
    """Qual firewall manda aqui: 'firewalld'/'ufw' (Linux), 'netsh' (Windows),
    'macos' (Application Firewall) ou None (nenhum reconhecido)."""
    so = platform.system()
    if so == "Windows":
        return "netsh"  # o Firewall do Windows está sempre presente; o netsh fala com ele
    if so == "Darwin":
        return "macos" if _tem("socketfilterfw") or _existe(_MACOS_FW) else None
    # Linux
    if _tem("firewall-cmd"):
        r = _rodar(["firewall-cmd", "--state"])
        if r is not None and r.returncode == 0 and "running" in r.stdout:
            return "firewalld"
    if _tem("ufw"):
        return "ufw"
    return None


def _existe(caminho: str) -> bool:
    try:
        import os
        return os.path.exists(caminho)
    except OSError:
        return False


def estado_macos() -> bool | None:
    """O firewall do Mac está LIGADO? True/False, ou None se não der pra saber.
    Desligado = nada bloqueia (não precisa abrir nada)."""
    r = _rodar([_MACOS_FW, "--getglobalstate"])
    if r is None or r.returncode != 0:
        return None
    saida = r.stdout.lower()
    if "disabled" in saida or "state = 0" in saida:
        return False
    if "enabled" in saida or "state = 1" in saida or "state = 2" in saida:
        return True
    return None


def portas_liberadas(portas_alvo: list[tuple[int, str]], sistema: str | None = None) -> dict[str, bool | None]:
    """Diz se cada porta já passa. dict 'porta/proto' -> True/False/None (None = não
    dá pra consultar). No Mac (por app) a chave vira 'app' e reflete o firewall: se
    está desligado, tudo passa (True)."""
    sistema = sistema if sistema is not None else detectar()
    if sistema == "macos":
        ligado = estado_macos()
        # desligado -> nada bloqueia (True); ligado -> não sei do app por aqui (None)
        return {"app (Python)": (False if ligado else True) if ligado is not None else None}
    estado: dict[str, bool | None] = {}
    for porta, proto in portas_alvo:
        chave = f"{porta}/{proto}"
        if sistema == "firewalld":
            r = _rodar(["firewall-cmd", f"--query-port={chave}"])
            estado[chave] = bool(r and r.returncode == 0 and "yes" in r.stdout) if r else None
        elif sistema == "netsh":
            r = _rodar(["netsh", "advfirewall", "firewall", "show", "rule",
                        f"name=Ekodide {chave}"])
            # netsh sai 0 se a regra existe; !=0 (sem match) se não existe
            estado[chave] = (r.returncode == 0) if r is not None else None
        else:
            estado[chave] = None
    return estado


def comandos(portas_alvo: list[tuple[int, str]], sistema: str | None = None) -> list[str] | None:
    """Os comandos exatos pra liberar, no firewall detectado. None se desconhecido
    (aí o CLI mostra as receitas comuns como referência). No Mac, libera o PROGRAMA
    (o Python que roda o Ekodide), não portas."""
    sistema = sistema if sistema is not None else detectar()
    chaves = [f"{porta}/{proto}" for porta, proto in portas_alvo]
    if sistema == "firewalld":
        add = " ".join(f"--add-port={c}" for c in chaves)
        return [f"sudo firewall-cmd {add} --permanent", "sudo systemctl restart firewalld"]
    if sistema == "ufw":
        return [f"sudo ufw allow {c}" for c in chaves]
    if sistema == "netsh":  # Windows: por porta, precisa de Administrador
        return [
            f'netsh advfirewall firewall add rule name="Ekodide {porta}/{proto}" '
            f"dir=in action=allow protocol={proto.upper()} localport={porta}"
            for porta, proto in portas_alvo
        ]
    if sistema == "macos":  # por APP: libera o Python que está rodando o Ekodide
        py = sys.executable or "python3"
        return [
            f'sudo {_MACOS_FW} --add "{py}"',
            f'sudo {_MACOS_FW} --unblockapp "{py}"',
            f"sudo pkill -HUP socketfilterfw",  # recarrega o firewall
        ]
    return None


def liberar(portas_alvo: list[tuple[int, str]], sistema: str | None = None) -> int:
    """Executa os comandos de abertura. Devolve o código de saída (0 = ok). No
    Windows sem Administrador o netsh falha (retorno != 0) — o CLI orienta a abrir
    um prompt elevado."""
    cmds = comandos(portas_alvo, sistema)
    if not cmds:
        return 1
    for c in cmds:
        if subprocess.run(c, shell=True).returncode != 0:
            return 1
    return 0
