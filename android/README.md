# Ekodide Android 🦜📱

App nativo **Kotlin** que põe o **celular no papel de recebedor/servidor passivo**: o
PC (admin) empurra e puxa arquivos do celular pela LAN, lacrados (HMAC) e cifrados
(AES-256-GCM), byte-idênticos — o celular fica parado, ouvindo. É a outra ponta do
core Python (`../ekodide`), falando o **mesmo protocolo no fio**.

> Decisões de fundo (linguagem Kotlin, Android-first, modelo passivo, seletor de
> pasta via SAF) estão no `../CLAUDE.md`, TODO #3.

## Por que app (e não site)

Pro PC "entrar" no celular, o celular tem que ser **servidor** (escutar/expor). Navegador
é cliente, não vira servidor → portal web não atende. Só app instalado resolve.

## Como compila e testa (sem SDK na máquina fraca)

Tudo roda no **GitHub Actions** (grátis, repo público) — o PC de 4 GB não precisa de
Android SDK:

- **`.github/workflows/android-build.yml`** — testes JVM + build do APK debug (sai como
  artefato pra baixar) a cada push em `android/**`.
- **`.github/workflows/android-instrumented.yml`** — testes no **emulador** (runtime real
  do Android), com KVM ligado no runner.

Baixe o APK na aba **Actions → run → Artifacts → `ekodide-debug-apk`**.

## Estrutura

```
android/
├── app/src/main/kotlin/com/ekodide/android/
│   ├── MainActivity.kt          # tela mínima (status); UI real vem depois
│   └── core/                    # núcleo de cifra — espelho byte-idêntico do Python
│       ├── CanonicalJson.kt     # json.dumps(sort_keys,separators,ensure_ascii=False) à mão
│       ├── Lacre.kt             # HMAC-SHA256 (assina/empacota)  ↔ lacre.py
│       ├── Hkdf.kt              # HKDF-SHA256 (RFC 5869)         ↔ derivação do cofre.py
│       └── Cofre.kt             # AES-256-GCM                    ↔ cofre.py
├── app/src/test/...             # testes JVM: vetores-ouro do Python + RFC 5869
└── app/src/androidTest/...      # mesmos vetores no emulador (provider real do Android)
```

## Byte-idêntico é sagrado

Os testes comparam o Kotlin contra **vetores gerados pelo código Python real**
(canonical JSON, HMAC, chave HKDF, blob AES-GCM). Mudou a cifra de um lado? O teste
do outro lado acende. Os vetores estão em `app/src/test/.../CryptoVectorsTest.kt`.

## Versões (mid-2026)

AGP 9.2.0 · Gradle 9.4.1 · Kotlin 2.4.0 · JDK 17 · compileSdk/targetSdk 36 · minSdk 29.
Catálogo em `gradle/libs.versions.toml` (bumpar = uma linha).

## Roadmap (resumido)

- [x] **Etapa 0** — scaffold + fábrica de APK no Actions (lane de emulador robusta).
- [x] **Etapa 1** — núcleo de cifra byte-idêntico: `core/CanonicalJson`, `Lacre`, `Hkdf`,
  `Cofre` (provado vs vetores do Python real + RFC 5869, no JVM e no emulador).
- [x] **Etapa 2** — servidor: `core/JsonParser`, `Lacre.desempacotar`, `core/CaixaPostal`
  (grava cercado + retomada), `server/Recebedor` (rotas `/receber` + `/progresso`) e
  `server/ServidorHttp` (porta 8778, ServerSocket cru, keep-alive). Provado por POST real
  no JVM e no emulador, inclusive recebendo um arquivo gerado pelo carteiro do Python.
- [ ] **Etapa 3** — `/listar` + `/buscar` (puxar) no Recebedor/ServidorHttp; cliente
  `Acervo` (leitura cercada, espelho do `acervo.py`); descoberta UDP (8779, `vizinhanca.py`);
  pareamento por frase (`frase.py`).
- [ ] **Etapa 4** — foreground service `connectedDevice` (passivo de verdade: tela apagada/boot),
  WifiLock HIGH_PERF, MulticastLock, BootReceiver, isenção de bateria. **A parte difícil.**
- [ ] **Etapa 5** — UI (status/pasta via SAF/frase), ícone, assinar APK pra sideload.

> **Como retomar:** o miolo está em `app/src/main/kotlin/com/ekodide/android/{core,server}`,
> espelhando os módulos Python homônimos em `../ekodide/`. Todo byte-exato é provado por
> teste contra vetores do Python (`app/src/test/.../CryptoVectorsTest.kt` e afins). O loop
> de trabalho é: escrever → push na branch `app` → ler o CI → corrigir. Os gotchas do CI
> de emulador estão comentados em `.github/workflows/android-instrumented.yml`.

> **Verdade dura (OEMs):** passivo 24/7 zero-config não existe em Xiaomi/Huawei/OnePlus —
> exige o usuário liberar autostart/bateria, e o lado PC tem que tolerar o celular sumir.
