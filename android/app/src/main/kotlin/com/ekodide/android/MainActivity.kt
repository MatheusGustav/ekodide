package com.ekodide.android

import android.Manifest
import android.app.Activity
import android.content.ComponentName
import android.content.Context
import android.content.Intent
import android.content.pm.PackageManager
import android.net.Uri
import android.os.Build
import android.os.Bundle
import android.os.PowerManager
import android.provider.Settings
import android.text.method.ScrollingMovementMethod
import android.view.Gravity
import android.widget.Button
import android.widget.LinearLayout
import android.widget.ScrollView
import android.widget.TextView
import com.ekodide.android.core.Frase
import com.ekodide.android.server.Recebedor
import java.net.Inet4Address
import java.net.NetworkInterface
import java.util.Collections

/**
 * Painel do app: sobe o ServidorService (segundo plano de verdade) e mostra endereço +
 * frase. Os botões da Etapa 4.3 ajudam o serviço a SOBREVIVER nos OEMs:
 *   - Liberar bateria: tira o app do Doze (isenção de otimização de bateria);
 *   - Autostart: nos OEMs (MIUI/Xiaomi) o app precisa de "iniciar automaticamente"
 *     liberado na mão — abre a tela certa (com plano B nos ajustes do app).
 */
class MainActivity : Activity() {

    private lateinit var status: TextView

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)

        val prefs = getSharedPreferences("ekodide", Context.MODE_PRIVATE)
        val frase = prefs.getString("frase", null) ?: Frase.gerar().also {
            prefs.edit().putString("frase", it).apply()
        }

        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.TIRAMISU &&
            checkSelfPermission(Manifest.permission.POST_NOTIFICATIONS) != PackageManager.PERMISSION_GRANTED
        ) {
            requestPermissions(arrayOf(Manifest.permission.POST_NOTIFICATIONS), 1)
        }

        ServidorService.iniciar(this)

        status = TextView(this).apply {
            textSize = 15f
            setTextIsSelectable(true)
            movementMethod = ScrollingMovementMethod()
        }
        val btBateria = Button(this).apply {
            text = "Liberar bateria (não dormir)"
            setOnClickListener { pedirIsencaoBateria() }
        }
        val btAutostart = Button(this).apply {
            text = "Ligar no início (autostart)"
            setOnClickListener { abrirAutostart() }
        }

        val coluna = LinearLayout(this).apply {
            orientation = LinearLayout.VERTICAL
            gravity = Gravity.CENTER_HORIZONTAL
            setPadding(40, 56, 40, 56)
            addView(status)
            addView(btBateria)
            addView(btAutostart)
        }
        setContentView(ScrollView(this).apply { addView(coluna) })
        atualizarStatus(frase)
    }

    override fun onResume() {
        super.onResume()
        val frase = getSharedPreferences("ekodide", Context.MODE_PRIVATE).getString("frase", "?")!!
        atualizarStatus(frase) // reflete a bateria depois que o usuário volta dos ajustes
    }

    private fun atualizarStatus(frase: String) {
        val pm = getSystemService(PowerManager::class.java)
        val isento = pm.isIgnoringBatteryOptimizations(packageName)
        status.text = """
            Ekodide 🦜

            Servidor rodando em 2º plano ✅
            Bateria liberada: ${if (isento) "sim ✅" else "NÃO — toque o botão"}

            Aparelho:  ${(Build.MODEL ?: "celular")}
            Endereço:  http://${ipLocal()}:${Recebedor.PORTA}

            Frase (o segredo) — digite IGUAL no PC:

                $frase

            Pode fechar a tela: o serviço continua.
            Nos Xiaomi, ligue também o "autostart".
        """.trimIndent()
    }

    /** Pede pra tirar o app da otimização de bateria (Doze) — vital pra ficar de pé. */
    private fun pedirIsencaoBateria() {
        val pm = getSystemService(PowerManager::class.java)
        if (pm.isIgnoringBatteryOptimizations(packageName)) return
        try {
            startActivity(
                Intent(Settings.ACTION_REQUEST_IGNORE_BATTERY_OPTIMIZATIONS, Uri.parse("package:$packageName")),
            )
        } catch (_: Exception) {
            abrirAjustesDoApp()
        }
    }

    /** Abre a tela de autostart do OEM (MIUI primeiro), com plano B nos ajustes do app. */
    private fun abrirAutostart() {
        val miui = Intent().apply {
            component = ComponentName(
                "com.miui.securitycenter",
                "com.miui.permcenter.autostart.AutoStartManagementActivity",
            )
        }
        try {
            startActivity(miui)
        } catch (_: Exception) {
            abrirAjustesDoApp()
        }
    }

    private fun abrirAjustesDoApp() {
        try {
            startActivity(
                Intent(Settings.ACTION_APPLICATION_DETAILS_SETTINGS, Uri.parse("package:$packageName")),
            )
        } catch (_: Exception) {
        }
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
