# Ekodide — guia do projeto 🦜

Peça **solta** que envia e recebe arquivos pela rede, **lacrados** (HMAC) e **cifrados**
(AES-256-GCM), chegando **byte-idênticos**. Quase tudo é biblioteca padrão do Python —
a única dependência dura é a `cryptography` (a cifra); o SDK do MCP é extra opcional
(`ekodide[agente]`, a tomada). Determinística — sem IA dentro; algo
*aciona* (humano, script, agente), o trabalho é do maquinário fixo.

Repo: https://github.com/MatheusGustav/ekodide · Licença: MIT · (extraído do projeto Orogbô)

## Arquitetura (cômodos)

| arquivo | papel |
|---|---|
| `ekodide/lacre.py` | fechadura HMAC — o segredo NUNCA trafega (assina/verifica + janela de tempo) |
| `ekodide/cofre.py` | cifra o CONTEÚDO (AES-256-GCM, chave via HKDF do segredo) — embaralha na rede, entrega byte-idêntico; depende de `cryptography` |
| `ekodide/carteiro.py` | ENVIA arquivo/pasta; grande vai **picado**; **retoma** de onde parou + **keep-alive** (conexão reusada); devolve `EnvioResultado` neutro |
| `ekodide/caixa_postal.py` | grava cercado (sem travessia/sobrescrita) e remonta pedaços (anota progresso no `.parcial.meta`) — pura, recebe a pasta `base` |
| `ekodide/acervo.py` | LÊ cercado a pasta COMPARTILHADA pro "puxar" (sem `../`, sem fuga por symlink) — espelho de leitura do caixa_postal; pura |
| `ekodide/buscador.py` | PUXA arquivo de outra ponta (`/listar` + `/buscar`); decifra e grava reusando a caixa postal — espelho do carteiro. Tem também o `espiar`: mesma viagem, mas os bytes ficam SÓ na memória (olhar ≠ puxar), com `limite` pra não trazer o arquivo inteiro |
| `ekodide/recebedor.py` | servidor HTTP leve (HTTP/1.1) que escuta, decifra e grava; rota `/progresso` pra retomada; `/listar` + `/buscar` expõem a pasta compartilhada (puxar) |
| `ekodide/vizinhanca.py` | descoberta na LAN (UDP broadcast 8779): anuncia presença / acha aparelhos pelo nome — IP vem do remetente, resolve DHCP |
| `ekodide/frase.py` | sorteia o segredo como código curto com verificador (pareamento out-of-band; o código É o segredo; QR/traço/caixa são só roupas) |
| `ekodide/cortina.py` | detecta o firewall (firewalld/ufw) e monta/roda o comando pra liberar as portas (lado que recebe) |
| `ekodide/config.py` | `~/.config/ekodide/config.json` (segredo + destinos + nome, cadeado 600) |
| `ekodide/cli.py` | comando `ekodide` (`send` / `serve` / `list` / `pull` / `devices` / `pair` / `firewall` / `config` / `mcp`) |
| `ekodide/tomada.py` | a TOMADA MCP: expõe 5 ferramentas (enviar/listar/puxar/espiar/aparelhos) pra qualquer agente de IA. Casca fina sobre as peças de sempre; **extra opcional** (`ekodide[agente]`) |

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
- **A tomada MCP é ENCAIXE, não cérebro** (decidido 2026-08-10 pelo Matheus Gustav).
  O Ekodide vira ferramenta plugável em qualquer agente de IA — mas continua sem IA
  dentro: `tomada.py` só resolve destino/segredo pela config, chama a peça de sempre
  e traduz o resultado neutro numa frase. Duas travas: **nada de `print`** (no stdio
  o stdout É o canal do protocolo — recado pra humano vai em stderr) e **ferramenta
  não estoura** (toda falha vira texto de volta; agente não trata traceback). O SDK
  do MCP entra como **extra opcional** (`ekodide[agente]`) pra não pesar em quem só
  quer mandar arquivo. Ele fala a API 2.0 (`mcp.server.MCPServer`) — a `fastmcp` da
  1.x não existe mais nesse caminho.
- **Puxar arquivo (em construção, 2026-06-20).** O admin pode PUXAR de outra ponta
  (rotas `/listar` + `/buscar` no recebedor; cliente `buscador.py`; leitura cercada em
  `acervo.py`). Exposição é **opt-in**: `serve --compartilhar <pasta>`, DESLIGADO por
  padrão — nada vaza sem apontar a pasta. **Política de pastas é do app, não do
  protocolo:** o core só recebe um caminho + a cerca de segurança (sem `../`); decidir
  onde cada tipo de arquivo cai/aparece é do app Android, nunca do Python.

## Como rodar / testar

```bash
pipx install ekodide   # do PyPI; a pasta local em modo editável: pip install -e .
pytest -q   # 113 testes: lacre, cofre, caixa, acervo, voo (envio+cifra+retomada), puxar/espiar, config, cli, tomada, etc.
            # os da tomada PULAM sozinhos sem o extra: pip install -e '.[agente]'
```

## TODO / próximos passos (atualizado 2026-08-12)

1. **Publicar no PyPI.** ✅ **FEITO.** `pip install ekodide` / `pipx install ekodide`
   funcionam, sem URL nenhuma. Publicado é publish pra fora → **confirmar com o Matheus
   antes** de todo `twine upload` novo.
   - **Versões no ar:** `0.1.0` (21/06/2026, a primeira usável), `0.1.1` (11/08/2026,
     que somou o `espiar` — ver `buscador.py`), `0.2.0` (11/08/2026, a tomada MCP) e
     `0.3.0` (13/08/2026, o pareamento por código curto + QR — TODO #5; o `pair` de
     texto livre morreu aqui) e `0.4.0` (13/08/2026, a navegação por pastas —
     `list/pull --pasta`). Quem depende do `espiar` pede `ekodide>=0.1.1`; quem quer
     a tomada instala o extra `ekodide[agente]>=0.2`; o QR no terminal é
     `ekodide[qr]>=0.3`; o `--pasta` pede `>=0.4`.
   - **Credencial:** o token fica em `~/.pypirc` (`[pypi]`, `username = __token__`),
     nunca no repo. O `twine upload` o pega sozinho, sem pedir login.
   - **Antes de subir, rebuildar do zero** (`rm -rf build dist ekodide.egg-info`): dist
     velho carrega código velho, e ninguém percebe até alguém instalar.
   - **A próxima versão** (build/twine NÃO estão no sistema; venv descartável, fora do
     repo pra não virar lixo — a máquina é magra e `/tmp` é tmpfs pequeno):
     ```bash
     # bumpar a version no pyproject.toml E no ekodide/__init__.py (os dois!)
     python3 -m venv ~/.cache/ekodide-build
     ~/.cache/ekodide-build/bin/pip install -U build twine
     rm -rf build dist ekodide.egg-info
     ~/.cache/ekodide-build/bin/python -m build
     ~/.cache/ekodide-build/bin/twine check dist/*
     # confere que a peça nova entrou MESMO no pacote antes de subir:
     ~/.cache/ekodide-build/bin/pip install dist/*.whl
     ~/.cache/ekodide-build/bin/python -c "import ekodide; print(ekodide.__version__)"
     # REAL (confirmar com o Matheus; o token sai do ~/.pypirc sozinho):
     ~/.cache/ekodide-build/bin/twine upload dist/*
     rm -rf ~/.cache/ekodide-build dist build ekodide.egg-info   # sem lixo
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
   - **Linguagem: Kotlin** (decidido 2026-06-20 pelo Matheus Gustav). O APK é escrito
     em Kotlin nativo.
   - **Seletor de pasta (Kotlin/app):** o `--compartilhar <pasta>` do core (do "puxar")
     vira o seletor de pastas do Android (SAF) — o usuário ESCOLHE uma pasta que já
     existe (rolo da câmera, Downloads, ou uma dedicada), sem copiar nada pra lugar novo.
     É assim que o app aponta a pasta exposta pro "puxar".
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

5. **Pareamento por QR + código curto — ✅ FEITO (planejado 2026-08-12, executado
   e provado no aparelho real em 2026-08-13; no ar na `0.3.0`/`0.4.0`).** QR e código são só ROUPAS pro mesmo
   segredo — protocolo, portas, lacre e cofre não mudaram. **Quem sorteia é SEMPRE a
   máquina**: senha escolhida por humano fica de fora DE PROPÓSITO — quem está no
   mesmo Wi-Fi captura um pacote lacrado e testa senhas contra o HMAC offline, sem
   limite; senha humana cai em dicionário, sorteio não. O sentido virou: **o PC
   mostra (QR + código), o celular escaneia ou digita e ADOTA** (alinhado com o
   item 3 — admin dirige, celular passivo). Out-of-band como sempre.
   - **Etapa A ✅ — o código curto.** 10 caracteres sorteados + 1 verificador
     (`K7TP3-XQ9FM-H`). Alfabeto de **31 símbolos** — maiúsculas + dígitos sem os
     confundíveis 0/O e 1/I/L; o plano dizia "32", mas a própria lista de exclusões
     dá 31, e 31 primo faz o verificador (soma ponderada mod 31) acusar GARANTIDO
     erro de 1 caractere e troca de vizinhos. ~49,5 bits (vs ~44 das palavras) num
     terço do tamanho. Forma CANÔNICA = maiúscula sem traço (traço/caixa são roupa;
     `validar` tira e devolve o canônico — é ELE que se grava nas duas pontas).
     `frase.py` e `Frase.kt` mudaram JUNTOS, com vetores-ouro idênticos nos testes
     dos dois lados. Segredo já pareado continua valendo (ninguém revalida config).
   - **Etapa B ✅ — o app ADOTA (metade digitada).** Home ganhou "Parear com o
     computador"; a tela valida com mensagem clara, grava a pref `frase` (canônico)
     e religa via `ServidorService.reconfigurar` (relê as prefs sem derrubar locks).
     Selo fala as duas línguas (código vestido / frase antiga com "·").
   - **Etapa C ✅ — a CLI unificada.** `ekodide pair` = entrada estilo login: mostra
     o atual (somar aparelho) ou sorteia (`--novo` aposenta o antigo); QR no
     terminal + código embaixo; prompt aceita código de outra tela. `pair <texto>`
     livre MORREU. Payload versionado `ekodide-pair-1:` (helpers em `frase.py`,
     espelhados no `Frase.kt`). Extra `ekodide[qr]` = `qrcode>=8` (dependência ZERO).
   - **Etapa D ✅ — o scanner no app.** `Escaneio.kt`: CameraX + ZXing core (3.5.3 /
     1.4.2 — ML Kit fora, régua do gratuito), com **LifecycleOwner manual**
     (LifecycleRegistry) pra Activity da casa seguir crua. Decodifica o plano Y e
     tenta INVERTIDO (QR de terminal escuro). CAMERA pedida na hora; QR alheio é
     recusado pelo prefixo e o scanner segue. Desagua no MESMO `adotarCodigo` do
     digitado. CI verde (unit + emulador) na branch `pareamento-qr`.
   - **Etapa E ✅ — ponta a ponta provado (2026-08-13).** fedora↔Redmi pareado por
     QR DE VERDADE (câmera do app → QR no terminal, `pair --novo` aposentou o
     segredo do lubuntu). Com o segredo novo: `send` chegou lacrado; `--pasta` sem
     o "acesso a todos os arquivos" levou o 403 explícito (o desenho); concedido,
     `list --pasta DCIM/…` navegou e `pull` trouxe um mp4 de 4,4 MB decifrado.
     README e `pair --help` atualizados.
   - **Nota de segurança que apressou isso:** o lubuntu foi DOADO (2026-08-12) e o
     segredo antigo pode ter ido junto na config dele. O primeiro `ekodide pair
     --novo` sorteia código novo e mata o velho. (O destino `lubuntu` saiu da config
     do fedora em 2026-08-12.)
   - **Digitar CONTINUA existindo** — é o fallback do scanner e o único caminho
     PC↔PC (PC não escaneia tela de outro PC).

## Notas de campo

- **2026-08-13:** a **navegação por pastas** (commit `5ca5ab2` de 10/07, que morava
  órfão na branch `app`) entrou na main por cherry-pick: campo `pasta` no
  `/listar`/`/buscar`, `list/pull --pasta` na CLI, `FonteAberta` no app (atrás do
  "acesso a todos os arquivos"; sem ele, 403 explícito — PC servindo recusa sempre).
  A branch `app` foi apagada depois do CI verde. Publicado no PyPI na `0.4.0`.
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
