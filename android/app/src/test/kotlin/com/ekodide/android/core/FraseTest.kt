package com.ekodide.android.core

import org.junit.Assert.assertEquals
import org.junit.Assert.assertThrows
import org.junit.Assert.assertTrue
import org.junit.Test

class FraseTest {

    @Test
    fun alfabeto_31_simbolos_sem_confundiveis() {
        assertEquals(31, Frase.ALFABETO.length)
        assertEquals(31, Frase.ALFABETO.toSet().size)
        // 0/O e 1/I/L ficam FORA de propósito (parecidos demais numa tela/voz)
        assertTrue("0O1IL".none { it in Frase.ALFABETO })
    }

    @Test
    fun gera_canonico_11_caracteres_do_alfabeto() {
        val c = Frase.gerar()
        assertEquals(11, c.length)
        assertEquals(Frase.TAMANHO, c.length)
        assertTrue(c.all { it in Frase.ALFABETO })
        assertEquals(c, Frase.validar(c)) // o que sai do sorteio já é canônico
    }

    @Test
    fun sorteia_diferente_a_cada_vez() {
        // 31^10 combinações: ver 8 códigos iguais seria praticamente impossível
        assertTrue((1..8).map { Frase.gerar() }.toSet().size > 1)
    }

    @Test
    fun formatar_veste_e_validar_tira_a_roupa() {
        val c = Frase.gerar()
        val vestido = Frase.formatar(c)
        assertEquals("${c.take(5)}-${c.substring(5, 10)}-${c[10]}", vestido)
        assertEquals(c, Frase.validar(vestido))                        // com traço
        assertEquals(c, Frase.validar(vestido.lowercase()))            // caixa baixa
        assertEquals(c, Frase.validar(" " + vestido.replace('-', ' '))) // espaço na vez do traço
    }

    @Test
    fun vetores_ouro_do_verificador_identicos_ao_python() {
        // os MESMOS vetores do test_frase.py — mudou a conta de um lado, o outro acende
        assertEquals('2', Frase.verificador("2222222222"))
        assertEquals('H', Frase.verificador("K7TP3XQ9FM")) // o exemplo do plano
        assertEquals('9', Frase.verificador("ZZZZZZZZZZ"))
        assertEquals('P', Frase.verificador("23456789AB"))
        assertEquals("K7TP3XQ9FMH", Frase.validar("K7TP3-XQ9FM-H"))
    }

    @Test
    fun typo_de_um_caractere_eh_acusado_sempre() {
        val c = Frase.gerar()
        for (i in c.indices) for (outro in Frase.ALFABETO) {
            if (outro == c[i]) continue
            val errado = c.substring(0, i) + outro + c.substring(i + 1)
            assertThrows(IllegalArgumentException::class.java) { Frase.validar(errado) }
        }
    }

    @Test
    fun troca_de_vizinhos_eh_acusada() {
        val c = "K7TP3XQ9FMH"
        for (i in 0 until c.length - 1) {
            if (c[i] == c[i + 1]) continue
            val trocado = c.substring(0, i) + c[i + 1] + c[i] + c.substring(i + 2)
            assertThrows(IllegalArgumentException::class.java) { Frase.validar(trocado) }
        }
    }

    @Test
    fun tamanho_errado_e_confundivel_recusados_com_mensagem() {
        val curto = assertThrows(IllegalArgumentException::class.java) { Frase.validar("K7TP3") }
        assertTrue(curto.message!!.contains("11"))
        // 'O' nunca existe num código de verdade: é erro de leitura, e a mensagem ensina
        val confuso = assertThrows(IllegalArgumentException::class.java) {
            Frase.validar("K7TPO-XQ9FM-H")
        }
        assertTrue(confuso.message!!.contains("0/O"))
    }

    @Test
    fun qr_payload_ida_e_volta() {
        val c = Frase.gerar()
        assertEquals("ekodide-pair-1:$c", Frase.qrPayload(c))
        assertEquals(c, Frase.deQrPayload(Frase.qrPayload(c)))
    }

    @Test
    fun qr_alheio_ou_torto_recusado() {
        // QR de wifi/boleto/cardápio: sem o prefixo da casa, recusa sem adivinhar
        assertThrows(IllegalArgumentException::class.java) {
            Frase.deQrPayload("WIFI:T:WPA;S:casa;P:12345678;;")
        }
        // versão desconhecida do payload também não passa
        assertThrows(IllegalArgumentException::class.java) {
            Frase.deQrPayload("ekodide-pair-2:" + Frase.gerar())
        }
        // prefixo certo com código corrompido: o verificador acusa
        assertThrows(IllegalArgumentException::class.java) {
            Frase.deQrPayload("ekodide-pair-1:AAAAAAAAAAA")
        }
    }

    @Test
    fun frase_antiga_de_palavras_recusada() {
        // o formato velho (6 palavras) não passa como pareamento novo; segredo antigo
        // JÁ GRAVADO segue valendo (é só string na pref — ninguém revalida)
        assertThrows(IllegalArgumentException::class.java) {
            Frase.validar("casa-vento-rio-azul-pedra-lobo")
        }
    }
}
