package com.ekodide.android

import android.app.Notification
import android.app.NotificationChannel
import android.app.NotificationManager
import android.app.Service
import android.content.Context
import android.content.Intent
import android.content.pm.ServiceInfo
import android.net.Uri
import android.net.wifi.WifiManager
import android.os.Build
import android.os.IBinder
import com.ekodide.android.core.Frase
import com.ekodide.android.net.Vizinhanca
import com.ekodide.android.server.FonteArquivo
import com.ekodide.android.server.FonteCompartilhada
import com.ekodide.android.server.Recebedor
import com.ekodide.android.server.ServidorHttp
import java.io.File

/**
 * O coração da Etapa 4: um foreground service tipo `connectedDevice` que mantém o
 * servidor passivo (ServidorHttp) e o anúncio (Vizinhanca) DE PÉ mesmo com a tela
 * apagada / app fora da frente. Sem ele, o Android mata o processo em segundo plano e o
 * PC perde o celular.
 *
 * Por que `connectedDevice` (e não `dataSync`): não tem teto de 6h e pode subir no boot —
 * é o tipo certo pra "ficar ouvindo um aparelho da LAN". Segura dois locks:
 *   - WifiLock HIGH_PERF: o Wi-Fi não dorme com a tela apagada (continua alcançável);
 *   - MulticastLock: deixa RECEBER broadcast UDP (a descoberta) no Android.
 *
 * O passivo 24/7 zero-config não existe em alguns OEMs (Xiaomi/Huawei): ainda pode ser
 * preciso o usuário liberar autostart/bateria — isso é UI/permissão (tarefas seguintes).
 */
class ServidorService : Service() {

    private var servidor: ServidorHttp? = null
    private var anuncio: Vizinhanca.Parada? = null
    private var wifiLock: WifiManager.WifiLock? = null
    private var multicastLock: WifiManager.MulticastLock? = null

    override fun onBind(intent: Intent?): IBinder? = null

    override fun onStartCommand(intent: Intent?, flags: Int, startId: Int): Int {
        when {
            // Pasta mudou: derruba e religa só o servidor pra reler a fonte (sem mexer
            // nos locks/notificação que já estão de pé).
            intent?.action == ACAO_RECONFIGURAR -> reiniciarServidor()
            servidor == null -> ligar()
        }
        // START_STICKY: se o sistema matar, recria o serviço quando puder.
        return START_STICKY
    }

    private fun ligar() {
        // Locks: manter o Wi-Fi acordado (tela apagada) e poder receber broadcast.
        val wm = applicationContext.getSystemService(Context.WIFI_SERVICE) as WifiManager
        if (wifiLock == null) {
            wifiLock = wm.createWifiLock(WifiManager.WIFI_MODE_FULL_HIGH_PERF, "ekodide:wifi").apply {
                setReferenceCounted(false); acquire()
            }
        }
        if (multicastLock == null) {
            multicastLock = wm.createMulticastLock("ekodide:multicast").apply {
                setReferenceCounted(false); acquire()
            }
        }
        subirForeground()
        ligarServidor()
    }

    /** (re)cria o servidor + anúncio, relendo a frase e a fonte compartilhada das prefs. */
    private fun ligarServidor() {
        val prefs = getSharedPreferences("ekodide", Context.MODE_PRIVATE)
        val frase = prefs.getString("frase", null) ?: Frase.gerar().also {
            prefs.edit().putString("frase", it).apply()
        }
        val nome = (Build.MODEL ?: "celular").replace(" ", "-").lowercase()
        val raiz = getExternalFilesDir(null) ?: filesDir
        val recebidos = File(raiz, "recebidos").apply { mkdirs() }
        val compartilhado = File(raiz, "compartilhado").apply { mkdirs() }
        File(compartilhado, "ola-do-celular.txt").let {
            if (!it.exists()) it.writeText("Oi do Ekodide no celular! 🦜\n")
        }

        // Fonte do "puxar": a pasta escolhida pelo usuário (SAF) se houver; senão a pasta
        // interna de demonstração. A leitura SAF é por content:// (FonteSaf).
        val pastaUri = prefs.getString("pasta_uri", null)
        val fonte: FonteCompartilhada = if (pastaUri != null) {
            FonteSaf(applicationContext, Uri.parse(pastaUri))
        } else {
            FonteArquivo(compartilhado)
        }

        // Bind do ServerSocket fora da thread principal.
        Thread {
            try {
                val s = ServidorHttp(recebidos, frase, compartilhar = fonte)
                s.iniciar()
                servidor = s
                anuncio = Vizinhanca.anunciarEmThread(
                    nome, Recebedor.PORTA, enderecos = listOf(Vizinhanca.BROADCAST),
                )
            } catch (_: Exception) {
                // porta ocupada/sem rede: o START_STICKY tenta de novo
            }
        }.also { it.isDaemon = true }.start()
    }

    private fun reiniciarServidor() {
        anuncio?.parar(); anuncio = null
        servidor?.parar(); servidor = null
        ligarServidor()
    }

    private fun subirForeground() {
        val canalId = "ekodide-servidor"
        val nm = getSystemService(NotificationManager::class.java)
        if (nm.getNotificationChannel(canalId) == null) {
            nm.createNotificationChannel(
                NotificationChannel(canalId, "Ekodide servidor", NotificationManager.IMPORTANCE_LOW),
            )
        }
        val notif: Notification = Notification.Builder(this, canalId)
            .setContentTitle("Ekodide 🦜 ouvindo")
            .setContentText("Recebendo e compartilhando na porta ${Recebedor.PORTA}")
            .setSmallIcon(android.R.drawable.stat_sys_upload)
            .setOngoing(true)
            .build()
        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.Q) {
            startForeground(NOTIF_ID, notif, ServiceInfo.FOREGROUND_SERVICE_TYPE_CONNECTED_DEVICE)
        } else {
            startForeground(NOTIF_ID, notif)
        }
    }

    override fun onDestroy() {
        anuncio?.parar()
        servidor?.parar()
        try { multicastLock?.release() } catch (_: Exception) {}
        try { wifiLock?.release() } catch (_: Exception) {}
        super.onDestroy()
    }

    companion object {
        private const val NOTIF_ID = 1
        private const val ACAO_RECONFIGURAR = "com.ekodide.android.RECONFIGURAR"

        /** Sobe o serviço em foreground (do app ou do BootReceiver). */
        fun iniciar(ctx: Context) {
            ctx.startForegroundService(Intent(ctx, ServidorService::class.java))
        }

        /** Religa só o servidor pra aplicar uma pasta recém-escolhida (sem reiniciar tudo). */
        fun reconfigurar(ctx: Context) {
            ctx.startForegroundService(
                Intent(ctx, ServidorService::class.java).setAction(ACAO_RECONFIGURAR),
            )
        }
    }
}
