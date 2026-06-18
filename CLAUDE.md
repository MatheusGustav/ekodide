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
| `ekodide/vizinhanca.py` | descoberta na LAN (UDP broadcast 8779): anuncia presença / acha aparelhos pelo nome — IP vem do remetente, resolve DHCP |
| `ekodide/frase.py` | gera o segredo como frase-código digitável (pareamento out-of-band; a frase É o segredo) |
| `ekodide/cortina.py` | detecta o firewall (firewalld/ufw) e monta/roda o comando pra liberar as portas (lado que recebe) |
| `ekodide/config.py` | `~/.config/ekodide/config.json` (segredo + destinos + nome, cadeado 600) |
| `ekodide/cli.py` | comando `ekodide` (`send` / `serve` / `devices` / `pair` / `firewall` / `config`) |

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
   qualquer lugar, sem URL, e discoverable. É publish pra fora → **confirmar com o
   Matheus antes** de dar o `twine upload`.

   **Empacotamento PRONTO (deixado pronto em 2026-06-18, falta só o upload).** O que
   já foi conferido/feito:
   - Nome **"ekodide" livre** no PyPI (checado, deu 404 → ninguém pegou).
   - `pyproject.toml` turbinado: `classifiers`, `keywords` e `[project.urls]`
     (Homepage/Repository/Issues apontando pro GitHub) — pra ficar discoverable e
     com página decente.
   - `python -m build` gera `dist/ekodide-0.1.0.tar.gz` + `.whl` sem erro.
   - `twine check dist/*` → PASSED nos dois. Smoke test: wheel instala em venv limpo
     e o comando `ekodide` roda.
   - `pytest -q` → 27 passam.

   **Para publicar quando decidir** (build/twine NÃO estão no sistema; use venv
   descartável — `pipx` não existe nesta máquina):
   ```bash
   python3 -m venv .venv-build && .venv-build/bin/pip install -U build twine
   rm -rf build dist ekodide.egg-info
   .venv-build/bin/python -m build
   .venv-build/bin/twine check dist/*
   # ENSAIO opcional (conta/token SEPARADOS do PyPI real):
   .venv-build/bin/twine upload --repository testpypi dist/*
   # REAL (confirmar com o Matheus; pede o token pypi-... na hora):
   .venv-build/bin/twine upload dist/*
   ```
   PEGADINHA: cada versão é **imutável** — não dá pra reupar/editar a `0.1.0` depois
   (nem após deletar). Correção = bumpar `version` no `pyproject.toml` **e** no
   `ekodide/__init__.py` e subir `0.1.1`. Como o Matheus quer **refinar antes**, o
   próximo release sairá com número novo de qualquer jeito.
2. **Revisar instalação e conexões — ver se dá pra deixar mais cômodo.**
   - *Conexão:* ✅ **FEITO (2026-06-18).** Descoberta automática por **UDP broadcast**
     (`vizinhanca.py`, porta 8779) — não precisa mais digitar IP: `ekodide devices`
     lista, `send --para <nome>` resolve pelo nome (IP vem do remetente → imune a
     DHCP). E **pareamento** por frase-código (`frase.py` + `ekodide pair`): o segredo
     forte é gerado e ditado out-of-band (a frase É o segredo, nunca trafega). O
     `serve --host 0.0.0.0` já se anuncia sozinho. Escolhi broadcast caseiro em vez de
     mDNS/zeroconf pra manter o zero-dep.
   - *Firewall:* ✅ **FEITO (2026-06-18).** `cortina.py` + `ekodide firewall` detecta
     firewalld/ufw, diz quais portas (TCP 8778 + UDP 8779) faltam e abre com sudo
     (`--abrir`); o `serve` avisa na hora se a porta parece fechada. Não abre nada
     escondido (exige root → você autoriza). QR de verdade (imagem) ficou de fora
     (pesado pro zero-dep) — a frase-código cobre o "PIN".
   - *Instalação:* avaliar um **zipapp single-file** (`ekodide.pyz`, roda só com
     Python, sem pip/pipx — viável porque é zero-dep) pra portabilidade instantânea.
   - *Auto-start:* um **atalho/serviço** pro `ekodide serve` subir sozinho no PC (no
     celular já sobe via Termux:Boot).

## Notas de campo (provado em 2026-06-18)

- Transferência **nos dois sentidos** por Wi-Fi, firewall ligado, sha256 idêntico.
- No Android: roda no **Termux** e sobe sozinho no boot via **Termux:Boot** (ver
  `contrib/termux/`). Pegadinha FBE: após reboot, o auto-start só dispara **depois
  do 1º desbloqueio** (a pasta do Termux fica cifrada até lá).
- Firewall (Fedora): liberar a porta de entrada e **reiniciar o firewalld**
  (`systemctl restart firewalld`) — um `--reload` sozinho pode não aplicar.
