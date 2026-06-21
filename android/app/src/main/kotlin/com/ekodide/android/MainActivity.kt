package com.ekodide.android

import android.app.Activity
import android.os.Build
import android.os.Bundle
import android.text.method.ScrollingMovementMethod
import android.view.Gravity
import android.widget.LinearLayout
import android.widget.TextView
import com.ekodide.android.core.Frase
import com.ekodide.android.net.Vizinhanca
import com.ekodide.android.server.Recebedor
import com.ekodide.android.server.ServidorHttp
import java.io.File
import java.net.Inet4Address
import java.net.NetworkInterface
import java.util.Collections

/**
 * Pontezinha testável (antes da Etapa 4): ao abrir o app, LIGA o servidor passivo
 * (ServidorHttp) e o anúncio na rede (Vizinhanca), mostra o IP/porta e a frase-código
 * (o segredo) pra digitar no PC. Sem foreground service ainda — roda enquanto a tela
 * está aberta; ficar de pé com a tela apagada/no boot é a Etapa 4. Serve só pra você
 * testar PC↔celular de verdade (empurrar e puxar) a partir deste APK.
 */
class MainActivity : Activity() {

    private var servidor: ServidorHttp? = null
    private var anuncio: Vizinhanca.Parada? = null

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)

        // Segredo estável entre aberturas: gera a frase uma vez e guarda.
        val prefs = getSharedPreferences("ekodide", MODE_PRIVATE)
        val frase = prefs.getString("frase", null) ?: Frase.gerar().also {
            prefs.edit().putString("frase", it).apply()
        }
        val nome = (Build.MODEL ?: "celular").replace(" ", "-").lowercase()

        // Pastas: o que CHEGA cai em 'recebidos'; 'compartilhado' é o que o PC pode PUXAR.
        // (O seletor de pasta de verdade, via SAF, é a Etapa 5.)
        val raiz = getExternalFilesDir(null) ?: filesDir
        val recebidos = File(raiz, "recebidos").apply { mkdirs() }
        val compartilhado = File(raiz, "compartilhado").apply { mkdirs() }
        File(compartilhado, "ola-do-celular.txt").let {
            if (!it.exists()) it.writeText("Oi do Ekodide no celular! 🦜\n")
        }

        val tv = TextView(this).apply {
            text = "Ekodide 🦜\n\nLigando o servidor…"
            textSize = 15f
            setTextIsSelectable(true) // pra copiar a frase
            movementMethod = ScrollingMovementMethod()
        }
        val layout = LinearLayout(this).apply {
            orientation = LinearLayout.VERTICAL
            gravity = Gravity.CENTER
            setPadding(40, 56, 40, 56)
            addView(tv)
        }
        setContentView(layout)

        // Bind do ServerSocket fora da thread principal (evita NetworkOnMainThreadException).
        Thread {
            val status = try {
                val s = ServidorHttp(recebidos, frase, compartilhar = compartilhado)
                s.iniciar()
                servidor = s
                anuncio = Vizinhanca.anunciarEmThread(
                    nome, Recebedor.PORTA, enderecos = listOf(Vizinhanca.BROADCAST),
                )
                "Servidor LIGADO ✅"
            } catch (e: Exception) {
                "Falhou ao ligar: ${e.message}"
            }
            val ip = ipLocal()
            val texto = """
                Ekodide 🦜

                $status

                Aparelho:  $nome
                Endereço:  http://$ip:${Recebedor.PORTA}

                Frase (o segredo) — digite IGUAL no PC:

                    $frase

                Recebidos →  ${recebidos.absolutePath}
                Compartilhado (dá pra puxar) →  ${compartilhado.name}/  (tem 1 arquivo de teste)

                Deixe esta tela aberta. Rodar de tela apagada
                e no boot vem na próxima etapa.
            """.trimIndent()
            runOnUiThread { tv.text = texto }
        }.also { it.isDaemon = true }.start()
    }

    override fun onDestroy() {
        anuncio?.parar()
        servidor?.parar()
        super.onDestroy()
    }

    /** Primeiro IPv4 de LAN (site-local) de uma interface ativa — o endereço do Wi-Fi. */
    private fun ipLocal(): String {
        try {
            for (intf in Collections.list(NetworkInterface.getNetworkInterfaces())) {
                if (!intf.isUp || intf.isLoopback) continue
                for (addr in Collections.list(intf.inetAddresses)) {
                    if (addr is Inet4Address && !addr.isLoopbackAddress && addr.isSiteLocalAddress) {
                        return addr.hostAddress ?: continue
                    }
                }
            }
        } catch (_: Exception) {
        }
        return "??? (conecte no Wi-Fi)"
    }
}
