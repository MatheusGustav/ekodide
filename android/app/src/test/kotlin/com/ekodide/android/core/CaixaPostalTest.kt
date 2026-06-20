package com.ekodide.android.core

import org.junit.Assert.assertArrayEquals
import org.junit.Assert.assertEquals
import org.junit.Assert.assertNull
import org.junit.Assert.assertThrows
import org.junit.Assert.assertTrue
import org.junit.Test
import java.io.File
import java.nio.file.Files

class CaixaPostalTest {

    private fun tempBase(): File = Files.createTempDirectory("ekodide-caixa").toFile()

    @Test
    fun guarda_arquivo_simples() {
        val base = tempBase()
        val alvo = CaixaPostal.guardar("foto.png", byteArrayOf(1, 2, 3), base)
        assertArrayEquals(byteArrayOf(1, 2, 3), alvo.readBytes())
        assertEquals(File(base, "foto.png").canonicalPath, alvo.canonicalPath)
    }

    @Test
    fun nao_sobrescreve_ganha_sufixo() {
        val base = tempBase()
        CaixaPostal.guardar("foto.png", byteArrayOf(1), base)
        val segundo = CaixaPostal.guardar("foto.png", byteArrayOf(2), base)
        assertEquals("foto (1).png", segundo.name)
        assertArrayEquals(byteArrayOf(1), File(base, "foto.png").readBytes())
    }

    @Test
    fun recria_subpastas() {
        val base = tempBase()
        val alvo = CaixaPostal.guardar("Fotos/sub/img.jpg", byteArrayOf(9), base)
        assertTrue(alvo.exists())
        assertEquals(File(base, "Fotos/sub/img.jpg").canonicalPath, alvo.canonicalPath)
    }

    @Test
    fun bloqueia_travessia_de_caminho() {
        val base = tempBase()
        assertThrows(IllegalArgumentException::class.java) {
            CaixaPostal.guardar("../fora.txt", byteArrayOf(0), base)
        }
        // '..' no meio também é descartado -> grava dentro, não escapa
        val alvo = CaixaPostal.guardar("a/../b.txt", byteArrayOf(7), base)
        assertEquals(File(base, "b.txt").canonicalPath, alvo.canonicalPath)
    }

    @Test
    fun remonta_picado_e_retoma() {
        val base = tempBase()
        val nome = "grande.bin"
        val p0 = byteArrayOf(10, 11, 12)
        val p1 = byteArrayOf(20, 21)
        val p2 = byteArrayOf(30)
        val tamanho = (p0.size + p1.size + p2.size).toLong()

        assertNull(CaixaPostal.guardarPedaco(nome, p0, 0, 3, base, tamanho))
        assertEquals(1, CaixaPostal.progressoDe(nome, 3, base, tamanho))

        // idempotência: reenviar o pedaço 0 não avança nem corrompe
        assertNull(CaixaPostal.guardarPedaco(nome, p0, 0, 3, base, tamanho))
        assertEquals(1, CaixaPostal.progressoDe(nome, 3, base, tamanho))

        // fora de ordem (pular o 1) é recusado
        assertThrows(IllegalArgumentException::class.java) {
            CaixaPostal.guardarPedaco(nome, p2, 2, 3, base, tamanho)
        }

        assertNull(CaixaPostal.guardarPedaco(nome, p1, 1, 3, base, tamanho))
        val alvo = CaixaPostal.guardarPedaco(nome, p2, 2, 3, base, tamanho)!!
        assertArrayEquals(p0 + p1 + p2, alvo.readBytes())
        assertEquals("grande.bin", alvo.name)
        // limpou os temporários
        assertTrue(!File(base, "$nome.parcial").exists())
        assertTrue(!File(base, "$nome.parcial.meta").exists())
    }

    @Test
    fun progresso_zera_se_o_tamanho_nao_bate() {
        val base = tempBase()
        val nome = "x.bin"
        CaixaPostal.guardarPedaco(nome, byteArrayOf(1, 2), 0, 3, base, 6)
        // outro arquivo de mesmo nome (tamanho diferente) -> recomeça do zero
        assertEquals(0, CaixaPostal.progressoDe(nome, 3, base, 999))
    }
}
