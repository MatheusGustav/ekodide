# Ekodide 🦜

Envia e recebe arquivos pela rede, **lacrados** (HMAC) e **idênticos** — sem
dependências (só a biblioteca padrão do Python).

O nome é de um papagaio africano (*odídẹ*): **repete com perfeição** (o arquivo
chega cópia exata, sha256 idêntico) e **voa** (vai de um aparelho a outro pela
rede, sem cabo). É código determinístico — não tem IA dentro. Algo *aciona* o
Ekodide (um humano no terminal, um script, um agente); o trabalho é deste
maquinário fixo.

## Instalar

Precisa só de **Python** (é zero-dependência, então `pipx` é opcional):

```bash
# direto do GitHub, isolado e no PATH (recomendado):
pipx install git+https://github.com/MatheusGustav/ekodide.git

# sem pipx — pip basta (cai em ~/.local/bin):
pip install --user git+https://github.com/MatheusGustav/ekodide.git

# pra desenvolver localmente:
git clone https://github.com/MatheusGustav/ekodide.git
pip install -e ekodide
```

## A ideia central: sempre há 2 pontas

Toda transferência tem **quem recebe** e **quem envia**:

- **Quem RECEBE** deixa a caixa de correio aberta → `ekodide serve` (fica escutando).
- **Quem ENVIA** joga a carta → `ekodide send`.

### Início rápido (sem digitar IP nem inventar senha) ⭐

Quem recebe abre a caixa **na rede** (já se anuncia sozinho pros outros acharem):
```bash
ekodide serve --host 0.0.0.0
```

Pareie o segredo **uma vez** — num aparelho gere a frase-código, no outro digite a mesma:
```bash
# aparelho A:
ekodide pair                       # mostra algo como: ekodide pair casa-vento-rio-azul-pedra-lobo
# aparelho B (digite a MESMA frase que apareceu em A):
ekodide pair casa-vento-rio-azul-pedra-lobo
```
A frase **é** o segredo — passe pela tela/voz, ela nunca trafega pela rede.

Veja quem está disponível e envie **pelo nome** (o IP é descoberto sozinho, mesmo
que mude por DHCP):
```bash
ekodide devices                    # lista os aparelhos na rede
ekodide send foto.jpg --para celular-matheus
```

### Cadastrar um apelido fixo (escolhendo da rede)

Se preferir um apelido fixo (em vez de resolver pelo nome toda vez), cadastre **sem
digitar IP** — o Ekodide lista quem está na rede e você só **escolhe qual é**:
```bash
ekodide config destino celular
#  Procurando aparelhos na rede pra cadastrar 'celular'…
#    1) galaxy-do-mat     http://192.168.0.9:8778
#    2) notebook-sala     http://192.168.0.20:8778
#  Qual é o aparelho? [número]: 1
#  Destino 'celular' = http://192.168.0.9:8778
ekodide send foto.jpg --para celular             # daí em diante, só o apelido
```
Só aparece quem está com a **caixa aberta** (`ekodide serve`) — que é justamente quem
pode receber. Se a lista vier vazia, é sinal de abrir a caixa no outro aparelho.

### Configurar na mão (avançado / scripts)

```bash
ekodide config segredo "uma-chave-bem-secreta"   # IGUAL nos dois aparelhos
ekodide config destino pc 192.168.0.10           # IP cru (completa http+porta) ou URL inteira
ekodide config nome   meu-pc                     # como apareço no 'devices'
ekodide config show                              # confere (segredo mascarado)
```

## Os comandos

### `send` — enviar
```bash
ekodide send arquivo.pdf --para celular        # um arquivo
ekodide send ~/projeto    --para pc            # uma PASTA inteira (com subpastas)
ekodide send video.mp4    --para celular       # arquivo grande? pica e remonta sozinho
ekodide send foto.jpg --para pc -m "print do erro"   # -m: etiqueta pro histórico
ekodide send foto.jpg --para pc --descobrir          # acha o IP na rede (ignora a config)
```
`--para` usa o **apelido** do destino. Se ele estiver na config, usa o IP de lá;
senão (ou com `--descobrir`), acha o aparelho **pelo nome na rede**. O caminho é
como no git: relativo à pasta atual.

### `devices` — quem está na rede
```bash
ekodide devices              # lista os aparelhos Ekodide que estão com a caixa aberta
ekodide devices --tempo 4    # escuta por mais tempo (padrão: 2.5s)
```

### `pair` — combinar o segredo (sem inventar/digitar chave aleatória)
```bash
ekodide pair                 # GERA uma frase-código, guarda e mostra pra ditar no outro
ekodide pair casa-vento-rio-azul-pedra-lobo   # RECEBE a frase ditada pelo outro aparelho
ekodide pair --palavras 8    # frase mais longa (mais forte) ao gerar
```

### `firewall` — liberar a entrada (no lado que recebe)
```bash
ekodide firewall             # detecta o firewall, diz o que falta e mostra o comando
ekodide firewall --abrir     # executa pra liberar (você autoriza)
```
Sabe lidar com **Linux** (firewalld/ufw — por porta, pede sudo), **Windows** (netsh —
por porta, precisa de um Prompt de Administrador) e **macOS** (Application Firewall —
é por **aplicativo**, libera o Python; e costuma vir desligado, aí nem precisa).

### `serve` — receber (abrir a caixa)
```bash
ekodide serve                      # escuta e grava o que chegar (padrão: ~/Downloads)
ekodide serve --host 0.0.0.0       # abre na LAN (pra receber de outro aparelho)
ekodide serve --dir ~/Recebidos    # escolhe a pasta destino
```
Deixe rodando num terminal; `Ctrl+C` para parar.

### `config` — ajustar
```bash
ekodide config show                          # ver segredo (mascarado) e destinos
ekodide config destino pc http://IP:8778     # cadastrar/atualizar um destino
ekodide config segredo "a-chave"             # trocar o segredo
```
A config fica em `~/.config/ekodide/config.json` (cadeado `600`, porque tem o segredo).

## Receitas

**📤 PC → celular** (com o celular já escutando):
```bash
# no PC:
ekodide send relatorio.pdf --para celular
```

**📥 celular → PC** (abra a caixa do PC primeiro):
```bash
# no PC (deixe rodando):
ekodide serve --host 0.0.0.0
# no outro aparelho:
ekodide send foto.jpg --para pc
```

## 3 pegadinhas

1. **A caixa precisa estar aberta:** o lado que recebe tem que estar com
   `ekodide serve` no ar.
2. **Mesmo segredo nos dois lados** — é a chave do cadeado.
3. **Firewall:** quem recebe precisa liberar **TCP 8778** (transferência) e **UDP 8779**
   (descoberta). O jeito fácil: **`ekodide firewall --abrir`** (detecta firewalld/ufw e
   roda com sudo). Na mão (Fedora): `sudo firewall-cmd --add-port=8778/tcp
   --add-port=8779/udp --permanent && sudo systemctl restart firewalld`. Sintoma de
   porta fechada: `No route to host` no envio (ou ninguém aparece no `devices`).

## Usar como biblioteca

```python
from pathlib import Path
from ekodide import enviar, servir

r = enviar(Path("foto.png"), "http://192.168.0.10:8778", segredo="...")
print(r.ok, r.destino)

# na outra ponta:
servir(Path("~/Downloads").expanduser(), segredo="...", host="0.0.0.0")
```

## Android

Em breve via **app nativo** (o celular como ponta passiva que o PC comanda).
Em desenvolvimento.

## Como é por dentro

| cômodo | papel |
|---|---|
| `lacre.py` | fechadura HMAC — o segredo nunca trafega |
| `cofre.py` | cifra o conteúdo (AES-256-GCM) — embaralhado na rede, idêntico no destino |
| `carteiro.py` | envia arquivo/pasta; arquivo grande vai **picado** em pedaços |
| `caixa_postal.py` | grava cercado (sem travessia, sem sobrescrever) e remonta os pedaços |
| `recebedor.py` | servidor HTTP leve que escuta e grava |
| `vizinhanca.py` | descoberta na LAN: anuncia presença e acha aparelhos pelo nome (sem IP) |
| `frase.py` | gera o segredo como frase-código digitável (pareamento out-of-band) |
| `cortina.py` | detecta o firewall e monta/roda o comando pra liberar as portas |
| `config.py` | lê/grava `~/.config/ekodide/config.json` (segredo + destinos + nome) |
| `cli.py` | o comando `ekodide` (send/serve/devices/pair/firewall/config) |

## Segurança (honesto)

Duas camadas, ambas chaveadas pelo segredo que as pontas compartilham (a frase-código
do pareamento — nunca trafega):

- **Lacre (HMAC-SHA256):** prova *quem* mandou, que ninguém mexeu no caminho, e que a
  mensagem é recente (janela de 5 min).
- **Cofre (AES-256-GCM):** **cifra o conteúdo** — na rede passa só embaralhado; só
  remetente e destinatário leem. O arquivo gravado fica byte-idêntico ao original.

Ainda é **mesma rede (Wi-Fi)** por foco, não por limite de cifra. O que falta pra
"rua" (internet) é endereçamento/NAT, não proteção do conteúdo.

## Licença

MIT — veja [LICENSE](LICENSE).
