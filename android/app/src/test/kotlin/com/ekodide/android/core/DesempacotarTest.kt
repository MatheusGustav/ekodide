package com.ekodide.android.core

import org.junit.Assert.assertEquals
import org.junit.Assert.assertThrows
import org.junit.Test

/**
 * Verificação do lacre (desempacotar) contra o envelope-ouro do Python e contra
 * adulterações. `agora` fixo em 1750000000 porque é o ts do vetor (senão a janela
 * de tempo recusaria por "antigo").
 */
class DesempacotarTest {

    private val secret = "casa-vento-rio-azul-pedra-lobo"
    private val ts = 1750000000L
    private val envelopeOuro =
        "{\"assinatura\":\"bcfde3b32600b77badfb2defca7a75768cc3aabb8d677233fcf9c815be2c72aa\"," +
            "\"carga\":{\"nome\":\"café.txt\",\"parte\":0,\"partes\":3,\"tamanho\":123,\"ts\":1750000000}}"

    @Test
    fun desempacota_envelope_do_python() {
        val carga = Lacre.desempacotar(envelopeOuro.toByteArray(Charsets.UTF_8), secret, agora = ts)
        assertEquals("café.txt", carga["nome"])
        assertEquals(0L, carga["parte"])
        assertEquals(3L, carga["partes"])
        assertEquals(123L, carga["tamanho"])
        assertEquals(ts, carga["ts"])
    }

    @Test
    fun recusa_assinatura_adulterada() {
        val ruim = envelopeOuro.replace("bcfde3", "0bcfde") // muda a assinatura
        assertThrows(TrancaInvalida::class.java) {
            Lacre.desempacotar(ruim.toByteArray(Charsets.UTF_8), secret, agora = ts)
        }
    }

    @Test
    fun recusa_carga_adulterada() {
        val ruim = envelopeOuro.replace("café.txt", "cafe.txt") // muda a carga, assinatura não bate
        assertThrows(TrancaInvalida::class.java) {
            Lacre.desempacotar(ruim.toByteArray(Charsets.UTF_8), secret, agora = ts)
        }
    }

    @Test
    fun recusa_segredo_errado() {
        assertThrows(TrancaInvalida::class.java) {
            Lacre.desempacotar(envelopeOuro.toByteArray(Charsets.UTF_8), "outro-segredo", agora = ts)
        }
    }

    @Test
    fun recusa_fora_da_janela_de_tempo() {
        assertThrows(TrancaInvalida::class.java) {
            Lacre.desempacotar(envelopeOuro.toByteArray(Charsets.UTF_8), secret, agora = ts + 301)
        }
    }

    @Test
    fun ida_e_volta_kotlin() {
        val carga = linkedMapOf<String, Any?>("nome" to "x.bin", "parte" to 2L, "partes" to 5L)
        val env = Lacre.empacotar(carga, secret) // ts = agora
        val volta = Lacre.desempacotar(env, secret) // dentro da janela
        assertEquals("x.bin", volta["nome"])
        assertEquals(2L, volta["parte"])
        assertEquals(5L, volta["partes"])
    }
}
