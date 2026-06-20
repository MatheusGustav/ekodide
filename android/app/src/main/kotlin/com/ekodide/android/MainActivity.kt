package com.ekodide.android

import android.app.Activity
import android.os.Bundle
import android.view.Gravity
import android.widget.LinearLayout
import android.widget.TextView

/**
 * Tela mínima da Etapa 0: só prova que o APK builda no Actions, instala e abre.
 * A UI de verdade (status do servidor, escolher pasta, frase de pareamento) vem
 * nas próximas etapas. O valor real do app está no núcleo (cifra) e no servidor.
 */
class MainActivity : Activity() {
    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)

        val texto = TextView(this).apply {
            text = "Ekodide 🦜\n\nFábrica de APK no ar.\nPróximo: servidor passivo."
            textSize = 18f
            gravity = Gravity.CENTER
        }
        val raiz = LinearLayout(this).apply {
            orientation = LinearLayout.VERTICAL
            gravity = Gravity.CENTER
            setPadding(48, 48, 48, 48)
            addView(texto)
        }
        setContentView(raiz)
    }
}
