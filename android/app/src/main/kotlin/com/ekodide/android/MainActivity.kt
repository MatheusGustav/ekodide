package com.ekodide.android

import android.Manifest
import android.app.Activity
import android.content.ClipData
import android.content.ClipboardManager
import android.content.ComponentName
import android.content.Context
import android.content.Intent
import android.content.pm.PackageManager
import android.net.Uri
import android.os.Build
import android.os.Bundle
import android.os.PowerManager
import android.provider.Settings
import android.view.View
import android.widget.LinearLayout
import android.widget.ScrollView
import android.widget.Toast
import com.ekodide.android.core.Frase
import com.ekodide.android.server.Recebedor
import com.ekodide.android.ui.Estilo
import java.net.Inet4Address
import java.net.NetworkInterface
import java.util.Collections

/**
 * Painel do app + assistente (wizard) de 1ª execução, no visual "sentinela / console
 * cifrado" (ver ui/Estilo). As telas de permissão NÃO são réplicas: cada botão abre a
 * tela REAL do sistema (Intent); o texto diz o que fazer.
 */
class MainActivity : Activity() {

    private val prefs by lazy { getSharedPreferences("ekodide", Context.MODE_PRIVATE) }
    private lateinit var frase: String

    private var passos: List<Passo> = emptyList()
    private var passoAtual = 0

    private data class Passo(
        val titulo: String,
        val texto: String,
        val rotulo: String?,
        val acao: (() -> Unit)?,
        val opcional: Boolean,
        val aoAvancar: (() -> Unit)? = null,
    )

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        frase = prefs.getString("frase", null) ?: Frase.gerar().also {
            prefs.edit().putString("frase", it).apply()
        }
        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.TIRAMISU &&
            checkSelfPermission(Manifest.permission.POST_NOTIFICATIONS) != PackageManager.PERMISSION_GRANTED
        ) {
            requestPermissions(arrayOf(Manifest.permission.POST_NOTIFICATIONS), REQ_NOTIF)
        }
        ServidorService.iniciar(this)

        if (prefs.getBoolean("setup_done", false)) mostrarHome() else iniciarWizard()
    }

    override fun onResume() {
        super.onResume()
        if (prefs.getBoolean("setup_done", false)) mostrarHome()
    }

    private fun pintar(coluna: LinearLayout) {
        setContentView(ScrollView(this).apply {
            setBackgroundColor(Estilo.TINTA)
            isFillViewport = true
            addView(coluna)
        })
    }

    // ---------- Wizard ----------

    private fun iniciarWizard() {
        passos = montarPassos()
        passoAtual = 0
        if (passos.isEmpty()) finalizarWizard() else renderPasso()
    }

    private fun montarPassos(): List<Passo> {
        val l = mutableListOf<Passo>()
        l += Passo(
            "Bem-vindo ao Ekodide",
            "Este aparelho passa a funcionar como um ponto seguro para enviar e receber " +
                "arquivos com o seu computador pela rede local — tudo autenticado e cifrado de " +
                "ponta a ponta. Em poucos passos, ele estará pronto para operar de forma autônoma.",
            null, null, false,
        )
        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.TIRAMISU &&
            checkSelfPermission(Manifest.permission.POST_NOTIFICATIONS) != PackageManager.PERMISSION_GRANTED
        ) {
            l += Passo(
                "Notificações",
                "Enquanto estiver ativo, o Ekodide mantém um aviso permanente na barra de " +
                    "notificações — é ele que permite o funcionamento contínuo em segundo plano. " +
                    "Conceda a permissão para prosseguir.",
                "Permitir notificações",
                { requestPermissions(arrayOf(Manifest.permission.POST_NOTIFICATIONS), REQ_NOTIF) },
                true,
            )
        }
        val pm = getSystemService(PowerManager::class.java)
        if (!pm.isIgnoringBatteryOptimizations(packageName)) {
            l += Passo(
                "Energia",
                "Para que o aplicativo permaneça disponível mesmo com a tela desligada, abra as " +
                    "configurações de energia e defina o consumo como “Sem restrição”.",
                "Abrir configurações de energia", { pedirIsencaoBateria() }, true,
            )
        }
        if (!prefs.getBoolean("autostart_done", false)) {
            l += Passo(
                "Inicialização automática",
                "Para que o Ekodide volte a funcionar sozinho depois que o aparelho for " +
                    "reiniciado, habilite a inicialização automática do aplicativo nas " +
                    "configurações do seu dispositivo. Ative a opção e toque em Continuar.",
                "Abrir configurações", { abrirAutostart() }, true,
                aoAvancar = { prefs.edit().putBoolean("autostart_done", true).apply() },
            )
        }
        l += Passo(
            "Pasta compartilhada",
            "Escolha a pasta que ficará acessível ao computador — por exemplo, a galeria de " +
                "imagens ou a pasta de downloads. Esta etapa é opcional e pode ser ajustada a " +
                "qualquer momento.",
            "Selecionar pasta", { escolherPasta() }, true,
        )
        return l
    }

    private fun renderPasso() {
        val p = passos[passoAtual]
        val ultimo = passoAtual == passos.size - 1
        val raiz = Estilo.raiz(this)

        raiz.addView(Estilo.header(this, true))
        raiz.addView(Estilo.espaco(this, 32f))

        val contador = "passo %02d / %02d".format(passoAtual + 1, passos.size)
        raiz.addView(Estilo.eyebrow(this, contador, Estilo.NEVOA))
        raiz.addView(Estilo.progresso(this, passoAtual, passos.size).also {
            Estilo.margem(it, this, topo = 12f)
        })
        raiz.addView(Estilo.espaco(this, 28f))

        raiz.addView(Estilo.titulo(this, p.titulo))
        raiz.addView(Estilo.corpo(this, p.texto).also { Estilo.margem(it, this, topo = 14f) })

        if (p.titulo.startsWith("Pasta")) {
            raiz.addView(Estilo.dado(this, "pasta selecionada", pastaEscolhida()).also {
                Estilo.margem(it, this, topo = 20f)
            })
        }

        raiz.addView(Estilo.espaco(this, 36f))

        // Ação do passo (abre a tela real) = primário; senão o Continuar é o primário.
        if (p.rotulo != null && p.acao != null) {
            raiz.addView(Estilo.botaoPrimario(this, p.rotulo, p.acao))
            raiz.addView(Estilo.botaoFantasma(this, if (ultimo) "Concluir" else "Continuar") {
                p.aoAvancar?.invoke(); avancar()
            }.also { Estilo.margem(it, this, topo = 12f) })
        } else {
            raiz.addView(Estilo.botaoPrimario(this, if (ultimo) "Concluir" else "Continuar") {
                p.aoAvancar?.invoke(); avancar()
            })
        }
        if (p.opcional) {
            raiz.addView(Estilo.botaoTexto(this, "Pular esta etapa") { avancar() }.also {
                Estilo.margem(it, this, topo = 6f)
            })
        }
        pintar(raiz)
    }

    private fun avancar() {
        passoAtual++
        if (passoAtual >= passos.size) finalizarWizard() else renderPasso()
    }

    private fun finalizarWizard() {
        prefs.edit().putBoolean("setup_done", true).apply()
        mostrarHome()
    }

    // ---------- Home ----------

    private fun mostrarHome() {
        val pm = getSystemService(PowerManager::class.java)
        val isento = pm.isIgnoringBatteryOptimizations(packageName)
        val raiz = Estilo.raiz(this)

        raiz.addView(Estilo.header(this, true))
        raiz.addView(Estilo.espaco(this, 28f))

        // Selo de pareamento — o herói da tela.
        raiz.addView(Estilo.selo(this, frase) { copiarFrase() })
        raiz.addView(Estilo.espaco(this, 16f))

        raiz.addView(Estilo.dado(this, "endereço na rede", "http://${ipLocal()}:${Recebedor.PORTA}"))
        raiz.addView(Estilo.espaco(this, 12f))

        // Pasta + ação de trocar.
        val cartaoPasta = Estilo.painel(this).apply {
            addView(Estilo.eyebrow(this@MainActivity, "pasta compartilhada", Estilo.NEVOA))
            addView(Estilo.valorMono(this@MainActivity, pastaEscolhida()).also {
                Estilo.margem(it, this@MainActivity, topo = 6f, baixo = 10f)
            })
            addView(Estilo.botaoTexto(this@MainActivity, "Trocar pasta", Estilo.MASK) { escolherPasta() })
        }
        raiz.addView(cartaoPasta)
        raiz.addView(Estilo.espaco(this, 12f))

        raiz.addView(Estilo.dado(this, "energia", if (isento) "Liberada" else "Com restrição"))
        raiz.addView(Estilo.espaco(this, 28f))

        raiz.addView(Estilo.corpo(this, "Pode fechar esta tela — o serviço permanece ativo em segundo plano."))
        raiz.addView(Estilo.espaco(this, 20f))
        raiz.addView(Estilo.botaoFantasma(this, "Refazer configuração") { iniciarWizard() })

        pintar(raiz)
    }

    private fun copiarFrase() {
        val cb = getSystemService(ClipboardManager::class.java)
        cb.setPrimaryClip(ClipData.newPlainText("frase Ekodide", frase))
        Toast.makeText(this, "Frase copiada", Toast.LENGTH_SHORT).show()
    }

    // ---------- Ações (abrem telas REAIS do sistema) ----------

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

    private fun escolherPasta() {
        try {
            startActivityForResult(Intent(Intent.ACTION_OPEN_DOCUMENT_TREE), REQ_PASTA)
        } catch (_: Exception) {
        }
    }

    @Deprecated("clássico, mas vale no android.app.Activity")
    override fun onActivityResult(requestCode: Int, resultCode: Int, data: Intent?) {
        super.onActivityResult(requestCode, resultCode, data)
        if (requestCode == REQ_PASTA && resultCode == RESULT_OK) {
            data?.data?.let { uri ->
                try {
                    contentResolver.takePersistableUriPermission(uri, Intent.FLAG_GRANT_READ_URI_PERMISSION)
                } catch (_: Exception) {
                }
                prefs.edit().putString("pasta_uri", uri.toString()).apply()
                ServidorService.reconfigurar(this) // aplica a nova pasta na hora
                if (prefs.getBoolean("setup_done", false)) mostrarHome() else renderPasso()
            }
        }
    }

    /** Nome amigável da pasta escolhida (último segmento do tree uri), ou "não definida". */
    private fun pastaEscolhida(): String {
        val s = prefs.getString("pasta_uri", null) ?: return "não definida"
        val dec = Uri.decode(s)
        return dec.substringAfterLast(':', dec.substringAfterLast('/', "selecionada"))
    }

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
        return "sem Wi-Fi"
    }

    companion object {
        private const val REQ_NOTIF = 1
        private const val REQ_PASTA = 2
    }
}
