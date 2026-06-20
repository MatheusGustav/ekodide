package com.ekodide.android.server

import com.ekodide.android.core.Cofre
import com.ekodide.android.core.Lacre
import org.junit.Assert.assertArrayEquals
import org.junit.Assert.assertEquals
import org.junit.Test
import java.io.BufferedInputStream
import java.io.File
import java.io.InputStream
import java.net.Socket
import java.nio.file.Files
import java.util.Base64

/**
 * Testa a casca HTTP de verdade: sobe o ServerSocket em loopback e faz POSTs reais
 * por socket cru (ServerSocket/Socket funcionam no JVM, então roda na lane rápida).
 */
class ServidorHttpTest {

    private val secret = "casa-vento-rio-azul-pedra-lobo"
    private fun tempBase(): File = Files.createTempDirectory("ek-srv").toFile()

    private fun corpoReceber(nome: String, dados: ByteArray): ByteArray {
        val carga = linkedMapOf<String, Any?>(
            "nome" to nome,
            "conteudo" to Base64.getEncoder().encodeToString(Cofre.cifrar(dados, secret)),
        )
        return Lacre.empacotar(carga, secret)
    }

    @Test
    fun recebe_post_real_via_socket() {
        val base = tempBase()
        val servidor = ServidorHttp(base, secret, porta = 0, host = "127.0.0.1")
        servidor.iniciar()
        try {
            val dados = "arquivo via socket 🦜 byte-idêntico".toByteArray(Charsets.UTF_8)
            val corpo = corpoReceber("recebido.txt", dados)
            Socket("127.0.0.1", servidor.portaReal).use { s ->
                val out = s.getOutputStream()
                out.write(
                    ("POST /receber HTTP/1.1\r\nHost: localhost\r\n" +
                        "Content-Type: application/json\r\nContent-Length: ${corpo.size}\r\n" +
                        "Connection: close\r\n\r\n").toByteArray(Charsets.ISO_8859_1),
                )
                out.write(corpo)
                out.flush()
                val full = s.getInputStream().readBytes()
                val texto = String(full, Charsets.ISO_8859_1)
                val status = texto.substringAfter(" ").substringBefore(" ").toInt()
                assertEquals(200, status)
                val sep = texto.indexOf("\r\n\r\n")
                val volta = Lacre.desempacotar(full.copyOfRange(sep + 4, full.size), secret)
                assertEquals(true, volta["ok"])
            }
            assertArrayEquals(dados, File(base, "recebido.txt").readBytes())
        } finally {
            servidor.parar()
        }
    }

    @Test
    fun keep_alive_duas_requisicoes_na_mesma_conexao() {
        val base = tempBase()
        val servidor = ServidorHttp(base, secret, porta = 0, host = "127.0.0.1")
        servidor.iniciar()
        try {
            Socket("127.0.0.1", servidor.portaReal).use { s ->
                val out = s.getOutputStream()
                val inp = BufferedInputStream(s.getInputStream())
                for (idx in 0..1) {
                    val dados = "pedaco-$idx".toByteArray(Charsets.UTF_8)
                    val corpo = corpoReceber("f$idx.txt", dados)
                    // SEM Connection: close -> a conexão é reusada (keep-alive)
                    out.write(
                        ("POST /receber HTTP/1.1\r\nContent-Length: ${corpo.size}\r\n\r\n")
                            .toByteArray(Charsets.ISO_8859_1),
                    )
                    out.write(corpo)
                    out.flush()
                    val (status, _) = lerResposta(inp)
                    assertEquals(200, status)
                }
            }
            assertArrayEquals("pedaco-0".toByteArray(), File(base, "f0.txt").readBytes())
            assertArrayEquals("pedaco-1".toByteArray(), File(base, "f1.txt").readBytes())
        } finally {
            servidor.parar()
        }
    }

    /** Lê UMA resposta HTTP do stream pelo Content-Length (pra reusar a conexão). */
    private fun lerResposta(inp: InputStream): Pair<Int, ByteArray> {
        fun linha(): String {
            val sb = StringBuilder()
            while (true) {
                val b = inp.read()
                if (b < 0 || b == '\n'.code) break
                if (b != '\r'.code) sb.append(b.toChar())
            }
            return sb.toString()
        }
        val status = linha().substringAfter(" ").substringBefore(" ").toInt()
        var len = 0
        while (true) {
            val h = linha()
            if (h.isEmpty()) break
            val i = h.indexOf(':')
            if (i > 0 && h.substring(0, i).trim().equals("content-length", true)) {
                len = h.substring(i + 1).trim().toInt()
            }
        }
        val corpo = ByteArray(len)
        var lido = 0
        while (lido < len) {
            val n = inp.read(corpo, lido, len - lido)
            if (n < 0) break
            lido += n
        }
        return Pair(status, corpo)
    }
}
