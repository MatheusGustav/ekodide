package com.ekodide.android.net

import com.ekodide.android.core.CanonicalJson
import com.ekodide.android.core.JsonParser
import java.net.DatagramPacket
import java.net.DatagramSocket
import java.net.InetAddress
import java.net.InetSocketAddress
import java.net.SocketTimeoutException
import kotlin.concurrent.thread

/**
 * A vizinhança: descobre quem está na rede SEM digitar IP. Espelho do vizinhanca.py.
 *
 * O celular (recebedor passivo) fica "gritando" de tempos em tempos um pacotinho UDP no
 * broadcast da LAN: *"oi, sou o <nome>, atendo na porta <porta>"*. O PC só ESCUTA por
 * alguns segundos e monta a lista. O IP NÃO viaja no pacote — quem escuta lê o endereço
 * do remetente; assim, se o IP mudar (DHCP), o nome resolve pro IP de agora.
 *
 * O pacote é só JSON parseado (sem HMAC, sem segredo, sem conteúdo) — a plaquinha de
 * "estou aqui". Por isso não precisa ser byte-idêntico ao Python: basta JSON válido com
 * marca/nome/porta, que os dois lados leem com o JsonParser.
 *
 * NOTA Android: ENVIAR (anunciar) não exige nada especial; RECEBER broadcast no Wi-Fi
 * pede MulticastLock — isso entra com o foreground service (Etapa 4).
 */
object Vizinhanca {
    // Porta separada da transferência (8778): aqui só trafega o anúncio de presença.
    const val PORTA_DESCOBERTA = 8779
    // Marca pra ignorar pacote de outro programa que caia na mesma porta.
    const val MARCA = "ekodide-vizinho-1"
    // 255.255.255.255 = broadcast do enlace local (a LAN).
    const val BROADCAST = "255.255.255.255"

    data class Vizinho(val nome: String, val ip: String, val porta: Int)

    /** Sinal de parada (espelha o threading.Event do Python): para de anunciar com `parar()`. */
    class Parada {
        @Volatile private var ativo = true
        private val trava = Object()
        val parado: Boolean get() = !ativo

        fun parar() {
            synchronized(trava) { ativo = false; trava.notifyAll() }
        }

        /** Dorme até `ms` OU até alguém chamar `parar()` (o que vier primeiro). */
        fun aguardar(ms: Long) {
            synchronized(trava) { if (ativo) trava.wait(ms) }
        }
    }

    private fun pacote(nome: String, porta: Int): ByteArray =
        CanonicalJson.encode(mapOf("marca" to MARCA, "nome" to nome, "porta" to porta))
            .toByteArray(Charsets.UTF_8)

    /**
     * Fica gritando "estou aqui" até `parada` ser acionada. BLOQUEIA — pra rodar junto do
     * servidor use `anunciarEmThread`. Por padrão grita no broadcast da LAN (pros outros)
     * E no 127.0.0.1 (pra conferir na mesma máquina — broadcast não faz loopback pra si).
     */
    fun anunciar(
        nome: String,
        porta: Int,
        parada: Parada = Parada(),
        intervaloMs: Long = 2000L,
        enderecos: List<String> = listOf(BROADCAST, "127.0.0.1"),
        portaDestino: Int = PORTA_DESCOBERTA,
    ): Parada {
        val msg = pacote(nome, porta)
        val s = DatagramSocket()
        s.broadcast = true
        try {
            while (!parada.parado) {
                for (endereco in enderecos) {
                    try {
                        val pkt = DatagramPacket(
                            msg, msg.size, InetAddress.getByName(endereco), portaDestino,
                        )
                        s.send(pkt)
                    } catch (_: Exception) {
                        // rede caiu/sem enlace agora — tenta de novo no próximo ciclo
                    }
                }
                parada.aguardar(intervaloMs)
            }
        } finally {
            s.close()
        }
        return parada
    }

    /** Sobe o anúncio numa thread daemon e volta na hora. Pare com `.parar()` no retorno. */
    fun anunciarEmThread(
        nome: String,
        porta: Int,
        intervaloMs: Long = 2000L,
        enderecos: List<String> = listOf(BROADCAST, "127.0.0.1"),
        portaDestino: Int = PORTA_DESCOBERTA,
    ): Parada {
        val parada = Parada()
        thread(isDaemon = true, name = "ekodide-vizinhanca") {
            anunciar(nome, porta, parada, intervaloMs, enderecos, portaDestino)
        }
        return parada
    }

    /**
     * Escuta os anúncios por `timeoutMs` e devolve os aparelhos vistos: {nome, ip, porta},
     * ordenado por nome. Um aparelho só conta uma vez (o anúncio mais recente vence).
     */
    fun procurar(timeoutMs: Long = 2500L, porta: Int = PORTA_DESCOBERTA): List<Vizinho> {
        val s = DatagramSocket(null)
        s.reuseAddress = true
        s.bind(InetSocketAddress(porta))
        s.soTimeout = 400
        val achados = LinkedHashMap<String, Vizinho>()
        val fim = System.nanoTime() + timeoutMs * 1_000_000
        val buf = ByteArray(2048)
        try {
            while (System.nanoTime() < fim) {
                val pkt = DatagramPacket(buf, buf.size)
                try {
                    s.receive(pkt)
                } catch (_: SocketTimeoutException) {
                    continue
                } catch (_: Exception) {
                    break
                }
                val texto = String(pkt.data, pkt.offset, pkt.length, Charsets.UTF_8)
                val p = try { JsonParser.parse(texto) } catch (_: Exception) { continue }
                if (p !is Map<*, *> || p["marca"] != MARCA) continue
                val nome = p["nome"] as? String ?: continue
                val portaAp = (p["porta"] as? Long)?.toInt() ?: continue
                val ip = pkt.address?.hostAddress ?: continue
                achados[nome] = Vizinho(nome, ip, portaAp)
            }
        } finally {
            s.close()
        }
        return achados.values.sortedBy { it.nome }
    }

    /** Monta a URL de transferência ('http://IP:PORTA') a partir de um achado. */
    fun urlDe(v: Vizinho): String = "http://${v.ip}:${v.porta}"
}
