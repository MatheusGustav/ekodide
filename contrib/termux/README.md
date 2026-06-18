# Rodar o Ekodide no Android (via Termux) sem virar trabalho manual

Enquanto não existe o app nativo, dá pra deixar o **recebedor do Ekodide subindo
sozinho** no celular usando o Termux — sem abrir nada na mão, sem descobrir IP toda
vez. Receita testada pra rede de casa (mesmo Wi-Fi).

## 1. No celular (uma vez)

```bash
# pré-requisitos no Termux
pkg install python                     # se ainda não tiver
pip install git+https://github.com/MatheusGustav/ekodide.git
termux-setup-storage                   # libera ~/storage/downloads

# guarda segredo e o endereço do PC na config (cadeado 600)
ekodide config segredo "<a-mesma-chave-do-PC>"
ekodide config destino pc http://<IP-DO-SEU-PC>:8778   # ex.: 192.168.0.10
```

## 2. Auto-start no boot

1. Instale o app **Termux:Boot** (F-Droid) e **abra ele uma vez** (é o que arma o gatilho).
2. Copie o script pra pasta de boot do Termux:
   ```bash
   mkdir -p ~/.termux/boot
   cp start-ekodide-serve.sh ~/.termux/boot/
   chmod +x ~/.termux/boot/start-ekodide-serve.sh
   ```
3. Reinicie o celular uma vez pra conferir que o recebedor subiu sozinho.

## 3. Tirar o "manual" de vez (2 ajustes fora do Termux)

- **Bateria:** Ajustes → Apps → Termux → bateria → **sem restrição** (senão o
  Android mata o processo dormindo).
- **IP fixo:** no roteador, reserve um IP pro celular (DHCP estático). Aí o
  endereço nunca muda e você nunca mais "descobre IP".

## Do PC pro celular

No PC, aponte o destino `celular` pro IP fixo do telefone e use normalmente:

```bash
ekodide config destino celular http://<IP-FIXO-DO-CELULAR>:8778
ekodide send foto.png --para celular
```

> Lembre de liberar a porta de entrada no firewall do PC quando for o PC a receber:
> `sudo firewall-cmd --add-port=8778/tcp`

## Limites honestos

Continua sendo Termux: depende do app instalado e do ajuste de bateria; é um
**tapa-buraco** bom, não a solução final. O destino é um **app Android nativo do
Ekodide** (só o endpoint de transferência), que sobe sozinho e não depende de
Termux nenhum.
