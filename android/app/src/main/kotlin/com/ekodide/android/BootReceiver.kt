package com.ekodide.android

import android.content.BroadcastReceiver
import android.content.Context
import android.content.Intent

/**
 * Sobe o ServidorService quando o celular liga — pro servidor passivo voltar sozinho
 * depois de reiniciar, sem o usuário abrir o app. BOOT_COMPLETED é uma das exceções que
 * permitem iniciar um foreground service a partir do background.
 *
 * Nos OEMs (MIUI/Xiaomi) o BOOT_COMPLETED só é entregue se o "autostart" estiver liberado
 * — por isso o botão de autostart na MainActivity (Etapa 4.3).
 */
class BootReceiver : BroadcastReceiver() {
    override fun onReceive(context: Context, intent: Intent) {
        if (intent.action == Intent.ACTION_BOOT_COMPLETED) {
            ServidorService.iniciar(context.applicationContext)
        }
    }
}
