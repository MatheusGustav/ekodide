"""A cortina (de fogo) do Ekodide: tira o atrito do firewall, sem mágica perigosa.

O lado que RECEBE precisa de duas portas abertas: a de transferência (TCP 8778) e
a da descoberta (UDP 8779). Abrir porta exige root — e abrir caladinho seria furo
de segurança. Então aqui a gente NÃO abre escondido: detecta o firewall, mostra o
comando exato já montado e, se você mandar, roda com `sudo` (você digita a senha).

Só stdlib (`shutil`, `subprocess`) — segue zero-dependência. É consulta + comando
pronto; quem autoriza é você.
"""
from __future__ import annotations

import shutil
import subprocess

from .vizinhanca import PORTA_DESCOBERTA

PORTA_TRANSFERENCIA = 8778


def portas(transferencia: int = PORTA_TRANSFERENCIA) -> list[tuple[int, str]]:
    """As portas que o lado que recebe precisa: transferência (TCP) e descoberta (UDP)."""
    return [(transferencia, "tcp"), (PORTA_DESCOBERTA, "udp")]


def _tem(programa: str) -> bool:
    return shutil.which(programa) is not None


def _rodar(args: list[str], timeout: float = 3.0) -> subprocess.CompletedProcess | None:
    try:
        return subprocess.run(args, capture_output=True, text=True, timeout=timeout)
    except (OSError, subprocess.SubprocessError):
        return None


def detectar() -> str | None:
    """Qual firewall está no comando aqui: 'firewalld', 'ufw' ou None (nenhum/desconhecido)."""
    if _tem("firewall-cmd"):
        r = _rodar(["firewall-cmd", "--state"])
        if r is not None and r.returncode == 0 and "running" in r.stdout:
            return "firewalld"
    if _tem("ufw"):
        return "ufw"  # checar se está ativo pede root; basta saber que é o firewall da casa
    return None


def portas_liberadas(portas_alvo: list[tuple[int, str]], sistema: str | None = None) -> dict[str, bool | None]:
    """Diz se cada porta já está liberada. dict 'porta/proto' -> True/False/None
    (None = não dá pra consultar sem root, ou firewall desconhecido). Só o firewalld
    responde sem root (`--query-port`)."""
    sistema = sistema if sistema is not None else detectar()
    estado: dict[str, bool | None] = {}
    for porta, proto in portas_alvo:
        chave = f"{porta}/{proto}"
        if sistema == "firewalld":
            r = _rodar(["firewall-cmd", f"--query-port={chave}"])
            estado[chave] = bool(r and r.returncode == 0 and "yes" in r.stdout) if r else None
        else:
            estado[chave] = None
    return estado


def comandos(portas_alvo: list[tuple[int, str]], sistema: str | None = None) -> list[str] | None:
    """Os comandos exatos pra liberar as portas no firewall detectado. None se não
    sei qual é (aí o CLI mostra as duas receitas comuns como referência)."""
    sistema = sistema if sistema is not None else detectar()
    chaves = [f"{porta}/{proto}" for porta, proto in portas_alvo]
    if sistema == "firewalld":
        add = " ".join(f"--add-port={c}" for c in chaves)
        return [f"sudo firewall-cmd {add} --permanent", "sudo systemctl restart firewalld"]
    if sistema == "ufw":
        return [f"sudo ufw allow {c}" for c in chaves]
    return None


def liberar(portas_alvo: list[tuple[int, str]], sistema: str | None = None) -> int:
    """Roda os comandos de abertura (pede sudo). Devolve o código de saída (0 = ok)."""
    cmds = comandos(portas_alvo, sistema)
    if not cmds:
        return 1
    for c in cmds:
        if subprocess.run(c, shell=True).returncode != 0:
            return 1
    return 0
