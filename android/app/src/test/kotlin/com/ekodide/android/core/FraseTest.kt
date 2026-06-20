package com.ekodide.android.core

import org.junit.Assert.assertEquals
import org.junit.Assert.assertThrows
import org.junit.Assert.assertTrue
import org.junit.Test

class FraseTest {

    @Test
    fun lista_identica_ao_python_164_unicas_e_simples() {
        assertEquals(164, Frase.PALAVRAS.size)
        assertEquals(Frase.PALAVRAS.size, Frase.PALAVRAS.toSet().size) // sem duplicatas
        // todas minúsculas, sem espaço/acento (fáceis de ditar em qualquer teclado)
        assertTrue(Frase.PALAVRAS.all { it == it.lowercase() && it.matches(Regex("[a-z]+")) })
    }

    @Test
    fun gera_seis_palavras_da_lista_por_padrao() {
        val frase = Frase.gerar()
        val partes = frase.split("-")
        assertEquals(6, partes.size)
        assertTrue("toda palavra vem da lista", partes.all { it in Frase.PALAVRAS })
    }

    @Test
    fun respeita_quantidade_e_separador() {
        val frase = Frase.gerar(palavras = 4, separador = " ")
        val partes = frase.split(" ")
        assertEquals(4, partes.size)
        assertTrue(partes.all { it in Frase.PALAVRAS })
    }

    @Test
    fun recusa_frase_curta_demais() {
        assertThrows(IllegalArgumentException::class.java) { Frase.gerar(palavras = 3) }
    }

    @Test
    fun sorteia_diferente_a_cada_vez() {
        // 164^6 combinações: ver 8 frases iguais seria praticamente impossível.
        val frases = (1..8).map { Frase.gerar() }.toSet()
        assertTrue("as frases deviam variar", frases.size > 1)
    }
}
