package com.ekodide.android.server

import org.junit.Assert.assertArrayEquals
import org.junit.Assert.assertEquals
import org.junit.Assert.assertThrows
import org.junit.Assert.assertTrue
import org.junit.Test
import java.io.File
import java.nio.file.Files

class FonteAbertaTest {

    private fun raizFake(): File {
        // Uma "raiz de armazenamento" de mentira: DCIM/Camera, DCIM/Screenshots,
        // Download e a reservada Android/data.
        val raiz = Files.createTempDirectory("ekodide-aberta").toFile()
        File(raiz, "DCIM/Camera").mkdirs()
        File(raiz, "DCIM/Screenshots").mkdirs()
        File(raiz, "Download").mkdirs()
        File(raiz, "Android/data/com.outro.app").mkdirs()
        File(raiz, "DCIM/Camera/foto.jpg").writeBytes(byteArrayOf(1, 2, 3))
        File(raiz, "DCIM/Screenshots/print.png").writeBytes(byteArrayOf(9, 8))
        File(raiz, "Download/doc.pdf").writeBytes(byteArrayOf(7))
        File(raiz, "Download/baixando.parcial").writeBytes(byteArrayOf(0))
        File(raiz, "Android/data/com.outro.app/segredo.txt").writeBytes(byteArrayOf(66))
        return raiz
    }

    @Test
    fun vista_rasa_separa_arquivos_e_pastas() {
        val vista = FonteAberta(raizFake()).listar("DCIM")
        assertTrue(vista.itens.isEmpty()) // DCIM só tem subpastas
        assertEquals(listOf("Camera", "Screenshots"), vista.pastas)

        val camera = FonteAberta(raizFake()).listar("DCIM/Camera")
        assertEquals(listOf("foto.jpg"), camera.itens.map { it.nome })
        assertEquals(listOf(3L), camera.itens.map { it.tamanho })
        assertTrue(camera.pastas.isEmpty())
    }

    @Test
    fun raiz_vazia_e_a_propria_raiz_e_nao_varre_fundo() {
        val vista = FonteAberta(raizFake()).listar("")
        // Rasa: mostra as pastas do topo, NÃO os arquivos lá no fundo.
        assertEquals(listOf("Android", "DCIM", "Download"), vista.pastas)
        assertTrue(vista.itens.isEmpty())
    }

    @Test
    fun temporarios_de_recebimento_ficam_de_fora() {
        val vista = FonteAberta(raizFake()).listar("Download")
        assertEquals(listOf("doc.pdf"), vista.itens.map { it.nome })
    }

    @Test
    fun pasta_reservada_e_recusada_em_qualquer_caixa() {
        val fonte = FonteAberta(raizFake())
        assertThrows(IllegalArgumentException::class.java) { fonte.listar("Android/data") }
        assertThrows(IllegalArgumentException::class.java) { fonte.listar("android/DATA/com.outro.app") }
        assertThrows(IllegalArgumentException::class.java) {
            fonte.lerPedaco("Android/data/com.outro.app", "segredo.txt", 0, 1)
        }
    }

    @Test
    fun travessia_e_descartada_nao_escapa_da_raiz() {
        val raiz = raizFake()
        val forasteiro = File(raiz.parentFile, "fora-${raiz.name}.txt").apply { writeBytes(byteArrayOf(5)) }
        try {
            // '..' é descartado (vira caminho dentro da raiz), nunca sobe.
            val vista = FonteAberta(raiz).listar("../")
            assertEquals(listOf("Android", "DCIM", "Download"), vista.pastas)
            assertThrows(IllegalArgumentException::class.java) {
                FonteAberta(raiz).lerPedaco("", "../${forasteiro.name}", 0, 1)
            }
        } finally {
            forasteiro.delete()
        }
    }

    @Test
    fun symlink_apontando_pra_fora_e_recusado() {
        val raiz = raizFake()
        val fora = Files.createTempDirectory("ekodide-fora").toFile()
        try {
            Files.createSymbolicLink(File(raiz, "atalho").toPath(), fora.toPath())
        } catch (_: Exception) {
            return // sistema de arquivos sem symlink: nada a testar aqui
        }
        assertThrows(IllegalArgumentException::class.java) { FonteAberta(raiz).listar("atalho") }
    }

    @Test
    fun pasta_inexistente_da_erro_claro() {
        assertThrows(IllegalArgumentException::class.java) { FonteAberta(raizFake()).listar("Nada/Aqui") }
    }

    @Test
    fun ler_pedaco_entrega_byte_identico() {
        assertArrayEquals(
            byteArrayOf(9, 8),
            FonteAberta(raizFake()).lerPedaco("DCIM/Screenshots", "print.png", 0, 1),
        )
    }
}
