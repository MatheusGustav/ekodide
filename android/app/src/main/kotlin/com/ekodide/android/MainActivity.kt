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
import android.view.View
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
 * Painel do app + assistente (wizard) de primeira execução.
 *
 * Etapa 5 (LAYOUT primeiro, estilo depois): na 1ª vez, um assistente guia UMA permissão
 * por tela (notificação → bateria → autostart → pasta), pulando sozinho as que já estão
 * ok. Depois disso, abre direto na HOME (status + IP + frase). As telas de permissão NÃO
 * são réplicas falsas: cada botão abre a tela REAL do Android/MIUI (Intent) e o texto diz
 * o que tocar.
 *
 * NOTA: o seletor de pasta aqui só CAPTURA e persiste a escolha (tree uri SAF). Fazer o
 * servidor LER dessa pasta (content:// -> Acervo) é a tarefa seguinte, separada por mexer
 * no core já provado.
 */
class MainActivity : Activity() {

    private val prefs by lazy { getSharedPreferences("ekodide", Context.MODE_PRIVATE) }
    private lateinit var frase: String

    private var passos: List<Passo> = emptyList()
    private var passoAtual = 0

    private data class Passo(
        val titulo: String,
        val texto: String,
        val rotulo: String?,            // texto do botão de ação (null = sem ação, só seguir)
        val acao: (() -> Unit)?,        // o que o botão faz (abre a tela real do sistema)
        val opcional: Boolean,          // mostra [Pular]
        val aoAvancar: (() -> Unit)? = null,
    )

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        frase = prefs.getString("frase", null) ?: Frase.gerar().also {
            prefs.edit().putString("frase", it).apply()
        }
        ServidorService.iniciar(this)

        if (prefs.getBoolean("setup_done", false)) mostrarHome() else iniciarWizard()
    }

    override fun onResume() {
        super.onResume()
        if (prefs.getBoolean("setup_done", false)) mostrarHome()
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
            "Bem-vindo ao Ekodide 🦜",
            "Seu celular vira um cofre que recebe e compartilha arquivos com o PC pela rede " +
                "local — lacrado e cifrado. Vamos liberar umas coisinhas pra ele ficar de pé sozinho.",
            null, null, false,
        )
        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.TIRAMISU &&
            checkSelfPermission(Manifest.permission.POST_NOTIFICATIONS) != PackageManager.PERMISSION_GRANTED
        ) {
            l += Passo(
                "Notificação", "O Ekodide mantém um aviso fixo enquanto está ouvindo. Toque em permitir.",
                "Permitir notificação",
                { requestPermissions(arrayOf(Manifest.permission.POST_NOTIFICATIONS), REQ_NOTIF) },
                true,
            )
        }
        val pm = getSystemService(PowerManager::class.java)
        if (!pm.isIgnoringBatteryOptimizations(packageName)) {
            l += Passo(
                "Bateria", "Pra ele não dormir, abra os ajustes e escolha \"Sem restrição\".",
                "Abrir ajustes de bateria", { pedirIsencaoBateria() }, true,
            )
        }
        if (!prefs.getBoolean("autostart_done", false)) {
            l += Passo(
                "Iniciar sozinho (Xiaomi)",
                "Nos Xiaomi, ligue o \"autostart\" pro app voltar depois de reiniciar. " +
                    "Faça isso e toque em Avançar.",
                "Abrir autostart", { abrirAutostart() }, true,
                aoAvancar = { prefs.edit().putBoolean("autostart_done", true).apply() },
            )
        }
        l += Passo(
            "Pasta compartilhada",
            "Escolha a pasta que o PC pode puxar (rolo da câmera, Downloads…). " +
                "Pode pular e definir depois. (A leitura dessa pasta entra na próxima versão.)",
            "Escolher pasta", { escolherPasta() }, true,
        )
        return l
    }

    private fun renderPasso() {
        val p = passos[passoAtual]
        val titulo = TextView(this).apply {
            text = "Passo ${passoAtual + 1} de ${passos.size}\n\n${p.titulo}"
            textSize = 20f
            gravity = Gravity.CENTER
        }
        val corpo = TextView(this).apply {
            text = "\n${p.texto}\n"
            textSize = 16f
        }
        val coluna = LinearLayout(this).apply {
            orientation = LinearLayout.VERTICAL
            setPadding(48, 64, 48, 48)
            addView(titulo)
            addView(corpo)
        }
        if (p.rotulo != null) {
            coluna.addView(Button(this).apply {
                text = p.rotulo
                setOnClickListener { p.acao?.invoke() }
            })
        }
        // pasta escolhida (feedback no passo de pasta)
        if (p.titulo.startsWith("Pasta")) {
            coluna.addView(TextView(this).apply {
                text = "\nEscolhida: ${pastaEscolhida()}"
                textSize = 14f
            })
        }
        val navegacao = LinearLayout(this).apply {
            orientation = LinearLayout.HORIZONTAL
            gravity = Gravity.CENTER
            setPadding(0, 48, 0, 0)
            if (p.opcional) addView(Button(context).apply {
                text = "Pular"; setOnClickListener { avancar() }
            })
            addView(Button(context).apply {
                text = if (passoAtual == passos.size - 1) "Concluir" else "Avançar"
                setOnClickListener { p.aoAvancar?.invoke(); avancar() }
            })
        }
        coluna.addView(navegacao)
        pintar(coluna)
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
        val status = TextView(this).apply {
            textSize = 15f
            setTextIsSelectable(true)
            movementMethod = ScrollingMovementMethod()
            text = """
                Ekodide 🦜

                Servidor rodando em 2º plano ✅
                Bateria liberada: ${if (isento) "sim ✅" else "NÃO ⚠️"}

                Aparelho:  ${(Build.MODEL ?: "celular")}
                Endereço:  http://${ipLocal()}:${Recebedor.PORTA}
                Pasta:     ${pastaEscolhida()}

                Frase (o segredo) — digite IGUAL no PC:

                    $frase

                Pode fechar a tela: o serviço continua.
            """.trimIndent()
        }
        val coluna = LinearLayout(this).apply {
            orientation = LinearLayout.VERTICAL
            setPadding(48, 64, 48, 48)
            addView(status)
            addView(Button(context).apply {
                text = "Refazer ajustes"
                setOnClickListener { iniciarWizard() }
            })
            addView(Button(context).apply {
                text = "Escolher pasta compartilhada"
                setOnClickListener { escolherPasta() }
            })
        }
        pintar(coluna)
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
                // re-renderiza a tela atual pra mostrar a pasta escolhida
                if (prefs.getBoolean("setup_done", false)) mostrarHome() else renderPasso()
            }
        }
    }

    /** Nome amigável da pasta escolhida (último segmento do tree uri), ou "(nenhuma)". */
    private fun pastaEscolhida(): String {
        val s = prefs.getString("pasta_uri", null) ?: return "(nenhuma)"
        val dec = Uri.decode(s)
        return dec.substringAfterLast(':', dec.substringAfterLast('/', "(escolhida)"))
    }

    // ---------- util ----------

    private fun pintar(view: View) {
        setContentView(ScrollView(this).apply { addView(view) })
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
        return "??? (conecte no Wi-Fi)"
    }

    companion object {
        private const val REQ_NOTIF = 1
        private const val REQ_PASTA = 2
    }
}
