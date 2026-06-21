package com.ekodide.android.server

import java.io.BufferedInputStream
import java.io.InputStream
import java.io.OutputStream
import java.net.InetAddress
import java.net.InetSocketAddress
import java.net.ServerSocket
import java.net.Socket
import kotlin.concurrent.thread

/**
 * A casca HTTP do recebedor: um servidor HTTP/1.1 sobre ServerSocket cru (zero
 * dependência), espelho do recebedor.py. Lê a requisição (keep-alive + Content-Length)
 * e delega ao Recebedor.tratar (já testado, sem sockets). A camada de socket é fina de
 * propósito — todo o juízo (lacre/cofre/caixa) está no núcleo.
 *
 * HTTP/1.1: mantém a conexão viva entre pedaços (o carteiro reusa a mesma porta), e
 * cada resposta manda Content-Length pra o cliente saber onde um corpo acaba.
 */
class ServidorHttp(
    private val base: java.io.File,
    private val segredo: String,
    private val porta: Int = Recebedor.PORTA,
    private val host: String? = null, // null = todas as interfaces (a LAN alcança)
    private val compartilhar: java.io.File? = null, // pasta exposta pro "puxar"; null = nada
) {
    // Teto do corpo: base64 incha ~33%, ~32 MB ≈ ~24 MB de arquivo real. Maior vai picado.
    private val limiteCorpo = 32 * 1024 * 1024

    private var server: ServerSocket? = null
    @Volatile private var rodando = false

    /** Porta de fato em uso (útil quando se passa porta=0 e o SO escolhe — testes). */
    val portaReal: Int get() = server?.localPort ?: porta

    /** Liga o servidor. Faz o bind de forma síncrona (portaReal já vale ao retornar). */
    fun iniciar() {
        // SO_REUSEADDR antes do bind (espelha allow_reuse_address do recebedor.py): evita
        // EADDRINUSE quando o socket anterior ainda está em TIME_WAIT (reabrir o app).
        val s = ServerSocket()
        s.reuseAddress = true
        val endereco = if (host != null) InetSocketAddress(InetAddress.getByName(host), porta)
        else InetSocketAddress(porta)
        s.bind(endereco, 50)
        server = s
        rodando = true
        thread(isDaemon = true, name = "ekodide-servidor") {
            while (rodando) {
                val cliente = try {
                    s.accept()
                } catch (e: Exception) {
                    if (rodando) continue else break
                }
                thread(isDaemon = true) { atender(cliente) }
            }
        }
    }

    fun parar() {
        rodando = false
        try { server?.close() } catch (_: Exception) {}
    }

    private fun atender(cliente: Socket) {
        cliente.use { sock ->
            val input = BufferedInputStream(sock.getInputStream())
            val output = sock.getOutputStream()
            while (rodando) {
                val cab = lerCabecalho(input) ?: break
                if (cab.contentLength < 0 || cab.contentLength > limiteCorpo) {
                    escrever(output, Recebedor.Resposta(
                        400, "corpo ausente ou grande demais".toByteArray(Charsets.UTF_8),
                        "text/plain; charset=utf-8",
                    ), fechar = true)
                    break
                }
                val corpo = ByteArray(cab.contentLength)
                if (!lerExato(input, corpo)) break // conexão caiu no meio do corpo
                val resp = Recebedor.tratar(cab.rota, corpo, segredo, base, compartilhar = compartilhar)
                escrever(output, resp, fechar = cab.fechar)
                if (cab.fechar) break
            }
        }
    }

    private data class Cabecalho(
        val metodo: String, val rota: String, val contentLength: Int, val fechar: Boolean,
    )

    /** Lê a linha de requisição + headers até a linha em branco. null = conexão fechada. */
    private fun lerCabecalho(input: InputStream): Cabecalho? {
        val linha = lerLinha(input) ?: return null
        if (linha.isEmpty()) return null
        val p = linha.split(" ")
        if (p.size < 2) return null
        var contentLength = 0
        var fechar = false
        while (true) {
            val h = lerLinha(input) ?: return null
            if (h.isEmpty()) break // linha em branco = fim dos headers
            val i = h.indexOf(':')
            if (i > 0) {
                val nome = h.substring(0, i).trim().lowercase()
                val valor = h.substring(i + 1).trim()
                when (nome) {
                    "content-length" -> contentLength = valor.toIntOrNull() ?: -1
                    "connection" -> fechar = valor.equals("close", ignoreCase = true)
                }
            }
        }
        return Cabecalho(p[0], p[1], contentLength, fechar)
    }

    private fun lerLinha(input: InputStream): String? {
        val sb = StringBuilder()
        while (true) {
            val b = input.read()
            if (b < 0) return if (sb.isEmpty()) null else sb.toString()
            if (b == '\n'.code) break
            if (b != '\r'.code) sb.append(b.toChar()) // headers são ASCII
        }
        return sb.toString()
    }

    private fun lerExato(input: InputStream, buf: ByteArray): Boolean {
        var lido = 0
        while (lido < buf.size) {
            val n = input.read(buf, lido, buf.size - lido)
            if (n < 0) return false
            lido += n
        }
        return true
    }

    private fun escrever(out: OutputStream, resp: Recebedor.Resposta, fechar: Boolean) {
        val cabec = buildString {
            append("HTTP/1.1 ").append(resp.status).append(' ').append(razao(resp.status)).append("\r\n")
            append("Content-Type: ").append(resp.contentType).append("\r\n")
            append("Content-Length: ").append(resp.corpo.size).append("\r\n")
            append("Connection: ").append(if (fechar) "close" else "keep-alive").append("\r\n")
            append("\r\n")
        }
        out.write(cabec.toByteArray(Charsets.ISO_8859_1))
        out.write(resp.corpo)
        out.flush()
    }

    private fun razao(c: Int): String = when (c) {
        200 -> "OK"; 400 -> "Bad Request"; 401 -> "Unauthorized"
        403 -> "Forbidden"; 404 -> "Not Found"; else -> "OK"
    }
}
