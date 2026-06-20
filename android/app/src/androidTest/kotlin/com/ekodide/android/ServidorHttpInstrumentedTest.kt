package com.ekodide.android

import androidx.test.ext.junit.runners.AndroidJUnit4
import com.ekodide.android.core.Cofre
import com.ekodide.android.core.Lacre
import com.ekodide.android.server.ServidorHttp
import org.junit.Assert.assertArrayEquals
import org.junit.Assert.assertEquals
import org.junit.Test
import org.junit.runner.RunWith
import java.io.File
import java.net.Socket
import java.util.Base64

/**
 * Prova que o servidor HTTP sobe e aceita um POST real no RUNTIME do Android (emulador):
 * ServerSocket binda, aceita conexão e grava o arquivo decifrado. Socket cru não esbarra
 * na política de cleartext do Android (que vale pra HttpURLConnection/OkHttp, não pra
 * socket puro) — e em uso real é o PC que conecta no celular, não o contrário.
 */
@RunWith(AndroidJUnit4::class)
class ServidorHttpInstrumentedTest {

    private val secret = "casa-vento-rio-azul-pedra-lobo"

    @Test
    fun servidor_aceita_post_real_no_android() {
        val base = java.nio.file.Files.createTempDirectory("ekodide-srv").toFile()
        val servidor = ServidorHttp(base, secret, porta = 0, host = "127.0.0.1")
        servidor.iniciar()
        try {
            val dados = "no aparelho 🦜".toByteArray(Charsets.UTF_8)
            val carga = linkedMapOf<String, Any?>(
                "nome" to "no_android.txt",
                "conteudo" to Base64.getEncoder().encodeToString(Cofre.cifrar(dados, secret)),
            )
            val corpo = Lacre.empacotar(carga, secret)
            Socket("127.0.0.1", servidor.portaReal).use { s ->
                val out = s.getOutputStream()
                out.write(
                    ("POST /receber HTTP/1.1\r\nContent-Length: ${corpo.size}\r\n" +
                        "Connection: close\r\n\r\n").toByteArray(Charsets.ISO_8859_1),
                )
                out.write(corpo)
                out.flush()
                val full = s.getInputStream().readBytes()
                val status = String(full, Charsets.ISO_8859_1).substringAfter(" ").substringBefore(" ").toInt()
                assertEquals(200, status)
            }
            assertArrayEquals(dados, File(base, "no_android.txt").readBytes())
        } finally {
            servidor.parar()
        }
    }
}
