# Ekodide — guia do projeto 🦜

Peça **solta** que envia e recebe arquivos pela rede, lacrados (HMAC) e idênticos.
Só biblioteca padrão do Python (**zero dependências**). Determinística — sem IA
dentro; algo *aciona* (humano, script, agente), o trabalho é do maquinário fixo.

Repo: https://github.com/MatheusGustav/ekodide · Licença: MIT · (extraído do projeto Orogbô)

## Arquitetura (cômodos)

| arquivo | papel |
|---|---|
| `ekodide/lacre.py` | fechadura HMAC — o segredo NUNCA trafega (assina/verifica + janela de tempo) |
| `ekodide/carteiro.py` | ENVIA arquivo/pasta; arquivo grande vai **picado**; devolve `EnvioResultado` neutro |
| `ekodide/caixa_postal.py` | grava cercado (sem travessia/sobrescrita) e remonta pedaços — pura, recebe a pasta `base` |
| `ekodide/recebedor.py` | servidor HTTP leve que escuta e grava |
| `ekodide/config.py` | `~/.config/ekodide/config.json` (segredo + destinos, cadeado 600) |
| `ekodide/cli.py` | comando `ekodide` (`send` / `serve` / `config`) |

Modelo mental: **2 pontas** — quem RECEBE roda `serve` (caixa aberta), quem ENVIA
roda `send`. Uso completo no [README](README.md).

## Decisões travadas (não reabrir sem motivo)

- **Zero dependências de propósito** (só stdlib): leve, instala em qualquer lugar,
  roda no Termux sem dor, dá pra empacotar como arquivo único. Não adicionar libs
  sem necessidade real.
- **Mesma rede (Wi-Fi)** por enquanto. O lacre garante autenticidade/integridade/
  recência, mas **NÃO cifra** — internet/"rua" pediria somar TLS + nonce (fora de escopo).
- Segurança é **código determinístico** (lacre), não confiada a modelo.

## Como rodar / testar

```bash
pipx install git+https://github.com/MatheusGustav/ekodide.git   # ou pip install --user ...
pytest -q                                                       # testes (lacre, caixa, voo, config, cli)
```

## TODO / próximos passos (anotado 2026-06-18)

1. **Publicar no PyPI.** Hoje instala via GitHub (`pipx install git+https://...`).
   Publicar no PyPI deixa virar `pipx install ekodide` / `pip install ekodide` em
   qualquer lugar, sem URL, e discoverable. Precisa: conta PyPI + token; conferir
   se o nome **"ekodide"** está livre; `python -m build` + `twine upload`. É publish
   pra fora → confirmar com o Matheus antes.
2. **Revisar instalação e conexões — ver se dá pra deixar mais cômodo.**
   - *Instalação:* avaliar um **zipapp single-file** (`ekodide.pyz`, roda só com
     Python, sem pip/pipx — viável porque é zero-dep) pra portabilidade instantânea.
   - *Conexão (hoje ainda meio manual):* IP fixo (reserva DHCP no roteador) ou
     **descoberta automática (mDNS/zeroconf)** pra não digitar IP; um **atalho/
     serviço** pro `ekodide serve` subir sozinho no PC (no celular já sobe via
     Termux:Boot); rever firewall (a porta de entrada precisa ser liberada à mão).
   - Objetivo: do "instala pipx, depois ekodide, configura IP na mão" para algo
     mais plug-and-play.

## Notas de campo (provado em 2026-06-18)

- Transferência **nos dois sentidos** por Wi-Fi, firewall ligado, sha256 idêntico.
- No Android: roda no **Termux** e sobe sozinho no boot via **Termux:Boot** (ver
  `contrib/termux/`). Pegadinha FBE: após reboot, o auto-start só dispara **depois
  do 1º desbloqueio** (a pasta do Termux fica cifrada até lá).
- Firewall (Fedora): liberar a porta de entrada e **reiniciar o firewalld**
  (`systemctl restart firewalld`) — um `--reload` sozinho pode não aplicar.
