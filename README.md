# Ekodide 🦜

Envia e recebe arquivos pela rede, **lacrados** (HMAC) e **idênticos** — sem
dependências (só a biblioteca padrão do Python).

O nome é de um papagaio africano (*odídẹ*): **repete com perfeição** (o arquivo
chega cópia exata, sha256 idêntico) e **voa** (vai de um aparelho a outro pela
rede, sem cabo). É código determinístico — não tem IA dentro. Algo *aciona* o
Ekodide (um humano no terminal, um script, um agente); o trabalho é deste
maquinário fixo.

## Instalar

```bash
pipx install ~/Documentos/projetos/ekodide      # comando isolado no PATH
# ou, pra desenvolver:
pip install -e ~/Documentos/projetos/ekodide
```

## Usar (linha de comando, tipo git)

```bash
# config (uma vez por máquina): a mesma chave nas duas pontas
ekodide config segredo "uma-chave-bem-secreta"
ekodide config destino pc      http://192.168.0.10:8778
ekodide config destino celular http://192.168.0.9:8777

# na ponta que RECEBE (deixe rodando):
ekodide serve --host 0.0.0.0            # escuta na LAN; grava em ~/Downloads

# na ponta que ENVIA (de qualquer pasta):
ekodide send foto.png --para pc -m "print do erro"
ekodide send ~/Downloads/fotos --para celular     # pasta inteira
```

## Usar (como biblioteca)

```python
from pathlib import Path
from ekodide import enviar, servir

r = enviar(Path("foto.png"), "http://192.168.0.10:8778", segredo="...")
print(r.ok, r.destino)

# na outra ponta:
servir(Path("~/Downloads").expanduser(), segredo="...", host="0.0.0.0")
```

## Como é por dentro

| cômodo | papel |
|---|---|
| `lacre.py` | fechadura HMAC — o segredo nunca trafega |
| `carteiro.py` | envia arquivo/pasta; arquivo grande vai **picado** em pedaços |
| `caixa_postal.py` | grava cercado (sem travessia, sem sobrescrever) e remonta os pedaços |
| `recebedor.py` | servidor HTTP leve que escuta e grava |
| `cli.py` | o comando `ekodide` (send/serve/config) |

## Segurança (honesto)

Mesma rede (Wi-Fi) por enquanto. O lacre garante autenticidade, integridade e
recência (janela de 5 min), mas **não cifra** o conteúdo — sem TLS, os bytes
trafegam visíveis na LAN. Internet/"rua" pediria somar TLS + nonce.
