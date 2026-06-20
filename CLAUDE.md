# Ekodide — guia do projeto 🦜

Peça **solta** que envia e recebe arquivos pela rede, **lacrados** (HMAC) e **cifrados**
(AES-256-GCM), chegando **byte-idênticos**. Quase tudo é biblioteca padrão do Python —
a única dependência é a `cryptography` (a cifra). Determinística — sem IA dentro; algo
*aciona* (humano, script, agente), o trabalho é do maquinário fixo.

Repo: https://github.com/MatheusGustav/ekodide · Licença: MIT · (extraído do projeto Orogbô)

## Arquitetura (cômodos)

| arquivo | papel |
|---|---|
| `ekodide/lacre.py` | fechadura HMAC — o segredo NUNCA trafega (assina/verifica + janela de tempo) |
| `ekodide/cofre.py` | cifra o CONTEÚDO (AES-256-GCM, chave via HKDF do segredo) — embaralha na rede, entrega byte-idêntico; depende de `cryptography` |
| `ekodide/carteiro.py` | ENVIA arquivo/pasta; grande vai **picado**; **retoma** de onde parou + **keep-alive** (conexão reusada); devolve `EnvioResultado` neutro |
| `ekodide/caixa_postal.py` | grava cercado (sem travessia/sobrescrita) e remonta pedaços (anota progresso no `.parcial.meta`) — pura, recebe a pasta `base` |
| `ekodide/recebedor.py` | servidor HTTP leve (HTTP/1.1) que escuta, decifra e grava; rota `/progresso` pra retomada |
| `ekodide/vizinhanca.py` | descoberta na LAN (UDP broadcast 8779): anuncia presença / acha aparelhos pelo nome — IP vem do remetente, resolve DHCP |
| `ekodide/frase.py` | gera o segredo como frase-código digitável (pareamento out-of-band; a frase É o segredo) |
| `ekodide/cortina.py` | detecta o firewall (firewalld/ufw) e monta/roda o comando pra liberar as portas (lado que recebe) |
| `ekodide/config.py` | `~/.config/ekodide/config.json` (segredo + destinos + nome, cadeado 600) |
| `ekodide/cli.py` | comando `ekodide` (`send` / `serve` / `devices` / `pair` / `firewall` / `config`) |

Modelo mental: **2 pontas** — quem RECEBE roda `serve` (caixa aberta), quem ENVIA
roda `send`. Uso completo no [README](README.md).

## Decisões travadas (não reabrir sem motivo)

- **Zero dependências é PREFERÊNCIA, não regra** (corrigido 2026-06-20 pelo Matheus
  Gustav — o "decisão travada" foi o Claude que endureceu). Prefere-se stdlib (leve,
  instala fácil), MAS dá pra somar dependência se houver motivo real — desde que seja a
  **melhor possível, gratuita e sem API paga**. Hoje a única é a `cryptography` (cifra).
  Não adicionar lib à toa.
- **Conteúdo CIFRADO** (decidido 2026-06-20). O lacre prova autenticidade/integridade/
  recência; o **cofre** (AES-256-GCM, chave HKDF do segredo das pontas) esconde o
  conteúdo — na rede passa só embaralhado, o arquivo gravado fica byte-idêntico
  (decifrar = inverso exato). A cifra é só no **seam da rede** (carteiro cifra /
  recebedor decifra); a caixa postal continua pura (texto-claro).
- **Mesma rede (Wi-Fi)** por foco, não por limite de cifra. O que falta pra "rua"
  (internet) é endereçamento/NAT, não proteção do conteúdo.
- Segurança é **código determinístico** (lacre + cofre), não confiada a modelo.
- **Byte-idêntico é sagrado.** Nada no caminho padrão do `send` pode mudar os bytes
  entregues (é por isso que "preparar vídeo" fica fora — ver TODO #4).

## Como rodar / testar

```bash
pipx install git+https://github.com/MatheusGustav/ekodide.git   # ou pip install --user ...
pytest -q   # 60 testes: lacre, cofre, caixa, voo (envio+cifra+retomada), config, cli, etc.
```

## TODO / próximos passos (atualizado 2026-06-20)

1. **Publicar no PyPI.** Hoje instala via GitHub (`pipx install git+https://...`).
   Publicar deixa virar `pipx install ekodide` / `pip install ekodide`, sem URL, e
   discoverable. É publish pra fora → **confirmar com o Matheus antes** do `twine upload`.
   - **Versão:** a `0.1.0` atual é a **primeira versão usável** e **nunca foi publicada**
     — então sai como `0.1.0` mesmo (não precisa bumpar; só se bate no PyPI já existindo).
   - **ATENÇÃO — o empacotamento de 2026-06-18 ficou DEFASADO.** De lá pra cá o código
     mudou muito (cifra, retomada, keep-alive) e ganhou **dependência** (`cryptography`).
     O `dist/` antigo foi apagado. **Tem que rebuildar do zero** antes de subir.
   - Nome **"ekodide"** estava livre no PyPI em 2026-06-18 (404). **Reconferir** antes.
   - `pyproject.toml` já tem `classifiers`, `keywords`, `[project.urls]` e a
     `dependencies = ["cryptography>=42"]`.
   - **Rebuildar e publicar** (build/twine NÃO estão no sistema; venv descartável):
     ```bash
     python3 -m venv .venv-build && .venv-build/bin/pip install -U build twine
     rm -rf build dist ekodide.egg-info
     .venv-build/bin/python -m build
     .venv-build/bin/twine check dist/*
     # ENSAIO opcional (conta/token SEPARADOS): twine upload --repository testpypi dist/*
     # REAL (confirmar com o Matheus; pede o token pypi-... na hora):
     .venv-build/bin/twine upload dist/*
     ```
   - PEGADINHA: depois de publicada, **cada versão é imutável** — correção = bumpar
     `version` no `pyproject.toml` **e** no `ekodide/__init__.py` e subir nova.

2. **Instalação/conexão mais cômoda.**
   - *Conexão:* ✅ **FEITO (2026-06-18).** Descoberta por **UDP broadcast**
     (`vizinhanca.py`, porta 8779): `ekodide devices` lista, `send --para <nome>` resolve
     pelo nome (IP vem do remetente → imune a DHCP). **Pareamento** por frase-código
     (`frase.py` + `ekodide pair`): o segredo é gerado e ditado out-of-band. Broadcast
     caseiro em vez de mDNS/zeroconf.
   - *Firewall:* ✅ **FEITO (2026-06-18).** `cortina.py` + `ekodide firewall` detecta e
     abre as portas (TCP 8778 + UDP 8779) com `--abrir`. Cobre Linux (firewalld/ufw),
     Windows (netsh) e macOS (App Firewall, por app). Conferido contra docs oficiais.
   - *Velocidade/robustez:* ✅ **FEITO (2026-06-20).** Envio reusa UMA conexão
     (keep-alive, HTTP/1.1), pedaço de 16 MB, e **retoma de onde parou** se a rede cair
     (rota `/progresso` + `.parcial.meta`, recebimento idempotente).
   - *Instalação:* o **zipapp single-file** (`ekodide.pyz`) ficou mais difícil agora que
     há a dep nativa `cryptography` (não embute fácil num .pyz). Reavaliar.
   - *Auto-start:* um **atalho/serviço** pro `ekodide serve` subir sozinho no PC.

3. **App nativo no celular (PENDENTE).** Objetivo: o **admin (PC) dirige tudo** — puxa
   e injeta arquivo no celular — com o **celular PASSIVO**.
   - **Por que app:** pro PC "entrar" no celular, o celular tem que ser **servidor**
     (escutar/expor). Navegador é cliente, não vira servidor → portal web NÃO atende.
     Auto-instalar de fora é proibido pelo SO. Só **app instalado** resolve.
   - **Tentativa revertida:** portal web (`serve --web`) implementado e **revertido**
     (commit `482ddc9` desfez `9f4cd2f`) — deixava o celular ativo, o oposto do desejo.
   - **Termux:** o caminho via Termux foi **removido (2026-06-20)** — vai dar lugar ao
     app nativo. (Os scripts em `contrib/termux/` saíram do repo.)
   - **ANDROID PRIMEIRO, iOS fica fora por ora (concluído 2026-06-20).** O iPhone
     **não suporta o modelo passivo** que o Matheus quer: o iOS mata/suspende app que
     tenta ficar "ouvindo" sozinho em segundo plano e a App Store rejeita servidor 24/7
     — na prática só rodaria com o app aberto na tela, o oposto de "passivo". Logo NÃO
     vale esforço cross-platform (Flutter/KMP) atrás do iOS; iPhone segue por PC↔PC. O
     valor central (PC↔Android e PC↔PC) não depende do iOS.
   - **Esforço estimado:** versão crua (recebe + dá pra puxar + roda em segundo plano +
     pareia) ~1–2 semanas de trabalho focado; polida/loja, mais. Não é fim de semana,
     nem meses. A parte difícil é o Android (segundo plano/bateria, permissão de
     arquivos, gerar/assinar APK), não o protocolo (lacre/cofre já existem).
   - **Linguagem: EM ABERTO** — Matheus ainda não decidiu (não cravar nada aqui).
   - **Quando for fazer:** app Android no papel de recebedor/servidor; outra stack
     (não é Python puro).

4. **Preparar vídeo MP4 — CONTINUA FORA DE ESCOPO (reconfirmado 2026-06-20).**
   - **Caso real:** um `.mp4` de gravador (fragmentado) chega cópia perfeita, mas a
     Galeria mostra 00:00 e o WhatsApp recusa. **Cópia perfeita de vídeo torto continua
     torto** — o conserto é remux `+faststart` / reencode, na origem.
   - **Por que fica fora:** "tratar" o vídeo **muda os bytes** (quebra o "byte-idêntico",
     pilar sagrado) e precisa de **ffmpeg**. NÃO entra no caminho padrão do `send`.
   - **Se um dia:** ferramenta **opt-in e separada** (`ekodide video --faststart <arq>`),
     que avisa que gera arquivo novo (sha diferente, de propósito) e só roda com ffmpeg
     no PATH. Núcleo intocado.

## Notas de campo

- **2026-06-20:** mp4/mp3 chegam byte-idênticos (teste automatizado, inclusive picado);
  retomada após queda; keep-alive + pedaço 16 MB; **cifra AES-256-GCM** provada em
  laboratório (teste que espiona a rede: conteúdo não vai em claro) **e** PC↔PC em 2
  processos reais (sha idêntico). 60 testes passando.
- **2026-06-18:** transferência nos dois sentidos por Wi-Fi, firewall ligado, sha256
  idêntico.
- Firewall (Fedora): liberar a porta e **reiniciar o firewalld**
  (`systemctl restart firewalld`) — um `--reload` sozinho pode não aplicar.

## Pra mim (Claude) — máquina do Matheus

- PC **fraquinho (4 GB de RAM)**: **NÃO** rodar testes de transferência de **vários GB**
  aqui (já travou a máquina 2x lendo arquivo inteiro pra RAM). O Ekodide é leve (processa
  em pedaços), mas teste que faz `read_bytes()` do arquivo todo estoura. Use arquivos
  modestos + hash em streaming. `/tmp` é tmpfs pequeno (~368 MB) — trabalhar em `~/.cache`.
