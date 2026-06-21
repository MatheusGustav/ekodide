package com.ekodide.android

import android.Manifest
import android.app.Activity
import android.content.Context
import android.content.pm.PackageManager
import android.os.Build
import android.os.Bundle
import android.text.method.ScrollingMovementMethod
import android.view.Gravity
import android.widget.LinearLayout
import android.widget.TextView
import com.ekodide.android.core.Frase
import com.ekodide.android.server.Recebedor
import java.net.Inet4Address
import java.net.NetworkInterface
import java.util.Collections

/**
 * Tela do app: sobe o ServidorService (foreground, segundo plano de verdade) e mostra o
 * endereço (IP:porta) + a frase-código (o segredo) pra digitar no PC. A partir da Etapa 4
 * o servidor NÃO vive mais na Activity — vive no serviço, que sobrevive à tela apagada e
 * (próximas tarefas) ao boot. Aqui é só o painel.
 */
class MainActivity : Activity() {

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)

        // Garante a frase já aqui (pra mostrar na hora); o serviço lê a mesma pref.
        val prefs = getSharedPreferences("ekodide", Context.MODE_PRIVATE)
        val frase = prefs.getString("frase", null) ?: Frase.gerar().also {
            prefs.edit().putString("frase", it).apply()
        }

        // Notificação é obrigatória pro foreground service aparecer (Android 13+ pede ok).
        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.TIRAMISU &&
            checkSelfPermission(Manifest.permission.POST_NOTIFICATIONS) != PackageManager.PERMISSION_GRANTED
        ) {
            requestPermissions(arrayOf(Manifest.permission.POST_NOTIFICATIONS), 1)
        }

        // Sobe o serviço passivo (idempotente: se já está rodando, não duplica).
        ServidorService.iniciar(this)

        val ip = ipLocal()
        val texto = """
            Ekodide 🦜

            Servidor rodando em 2º plano ✅
            (segue de pé com a tela apagada)

            Aparelho:  ${(Build.MODEL ?: "celular")}
            Endereço:  http://$ip:${Recebedor.PORTA}

            Frase (o segredo) — digite IGUAL no PC:

                $frase

            Recebidos e pasta compartilhada ficam em
            Android/data/com.ekodide.android/files/.

            Pode fechar esta tela: o serviço continua.
            Subir no boot e isenção de bateria vêm a seguir.
        """.trimIndent()

        val tv = TextView(this).apply {
            text = texto
            textSize = 15f
            setTextIsSelectable(true)
            movementMethod = ScrollingMovementMethod()
        }
        val layout = LinearLayout(this).apply {
            orientation = LinearLayout.VERTICAL
            gravity = Gravity.CENTER
            setPadding(40, 56, 40, 56)
            addView(tv)
        }
        setContentView(layout)
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
