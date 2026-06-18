#!/data/data/com.termux/files/usr/bin/sh
# Ekodide via Termux:Boot — sobe o recebedor SOZINHO quando o celular liga.
#
# Coloque este arquivo em  ~/.termux/boot/  dentro do Termux e dê +x:
#     mkdir -p ~/.termux/boot
#     cp start-ekodide-serve.sh ~/.termux/boot/
#     chmod +x ~/.termux/boot/start-ekodide-serve.sh
#
# Requer (uma vez):
#   - app Termux:Boot instalado (F-Droid) e aberto ao menos uma vez
#   - termux-setup-storage  (pra gravar em ~/storage/downloads)
#   - pip install git+https://github.com/MatheusGustav/ekodide.git
#   - ekodide config segredo "<a-mesma-chave-do-PC>"
#   - ekodide config destino pc http://<IP-DO-SEU-PC>:8778   (ex.: 192.168.0.10)
#
# O segredo e a pasta destino saem da config (~/.config/ekodide/config.json);
# por isso o script é curtinho.

termux-wake-lock                 # impede o Android de adormecer o processo
exec ekodide serve --host 0.0.0.0   # escuta na LAN; grava onde a config mandar
