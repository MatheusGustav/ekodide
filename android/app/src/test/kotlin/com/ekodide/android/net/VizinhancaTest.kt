package com.ekodide.android.net

import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
import org.junit.Assert.assertTrue
import org.junit.Test
import java.net.DatagramPacket
import java.net.DatagramSocket
import java.net.InetAddress

class VizinhancaTest {

    // Porta de teste fora da padrão (8779) pra não colidir com um serviço real na máquina.
    private val portaTeste = 18779

    private fun enviarBruto(texto: String, porta: Int) {
        DatagramSocket().use { s ->
            val b = texto.toByteArray(Charsets.UTF_8)
            s.send(DatagramPacket(b, b.size, InetAddress.getByName("127.0.0.1"), porta))
        }
    }

    @Test
    fun anuncio_e_descoberta_se_encontram() {
        val parada = Vizinhanca.anunciarEmThread(
            "celular-do-mat", 8778,
            intervaloMs = 150, enderecos = listOf("127.0.0.1"), portaDestino = portaTeste,
        )
        try {
            val achados = Vizinhanca.procurar(timeoutMs = 1500, porta = portaTeste)
            val meu = achados.firstOrNull { it.nome == "celular-do-mat" }
            assertTrue("devia achar o anúncio do celular", meu != null)
            assertEquals(8778, meu!!.porta)
            assertEquals("127.0.0.1", meu.ip)
            assertEquals("http://127.0.0.1:8778", Vizinhanca.urlDe(meu))
        } finally {
            parada.parar()
        }
    }

    @Test
    fun ignora_pacote_sem_marca_ou_lixo() {
        // dispara dois pacotes inválidos um tiquinho depois que o ouvinte sobe
        Thread {
            Thread.sleep(200)
            enviarBruto("isto não é json", portaTeste)
            enviarBruto("""{"marca":"outro-programa","nome":"intruso","porta":1}""", portaTeste)
        }.also { it.isDaemon = true }.start()

        val achados = Vizinhanca.procurar(timeoutMs = 900, porta = portaTeste)
        assertFalse(achados.any { it.nome == "intruso" })
    }

    @Test
    fun ultimo_anuncio_vence_porta_atualizada() {
        // mesmo nome, portas diferentes: o mais recente (8779) deve vencer o (8778)
        Thread {
            Thread.sleep(150)
            enviarBruto("""{"marca":"ekodide-vizinho-1","nome":"x","porta":8778}""", portaTeste)
            Thread.sleep(150)
            enviarBruto("""{"marca":"ekodide-vizinho-1","nome":"x","porta":8779}""", portaTeste)
        }.also { it.isDaemon = true }.start()

        val achados = Vizinhanca.procurar(timeoutMs = 1200, porta = portaTeste)
        val x = achados.firstOrNull { it.nome == "x" }
        assertTrue(x != null)
        assertEquals(8779, x!!.porta)
    }
}
