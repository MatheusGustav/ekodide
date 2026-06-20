package com.ekodide.android.core

import org.junit.Assert.assertArrayEquals
import org.junit.Assert.assertEquals
import org.junit.Assert.assertThrows
import org.junit.Assert.assertTrue
import org.junit.Test
import java.io.File
import java.nio.file.Files

class AcervoTest {

    private fun tempBase(): File = Files.createTempDirectory("ekodide-acervo").toFile()

    private fun escrever(base: File, nome: String, bytes: ByteArray): File {
        val alvo = File(base, nome)
        alvo.parentFile?.mkdirs()
        alvo.writeBytes(bytes)
        return alvo
    }

    @Test
    fun listar_vazio_quando_null_ou_inexistente() {
        assertTrue(Acervo.listar(null).isEmpty())
        assertTrue(Acervo.listar(File("/nao/existe/mesmo")).isEmpty())
    }

    @Test
    fun listar_recursivo_ordenado_sem_temporarios() {
        val base = tempBase()
        escrever(base, "b.txt", byteArrayOf(1))
        escrever(base, "Fotos/a.png", byteArrayOf(2, 2))
        escrever(base, "Fotos/sub/c.bin", byteArrayOf(3, 3, 3))
        // temporários de recebimento NÃO aparecem
        escrever(base, "grande.bin.parcial", byteArrayOf(9))
        escrever(base, "grande.bin.parcial.meta", byteArrayOf(9))

        val itens = Acervo.listar(base)
        assertEquals(listOf("Fotos/a.png", "Fotos/sub/c.bin", "b.txt"), itens.map { it.nome })
        assertEquals(listOf(2L, 3L, 1L), itens.map { it.tamanho })
    }

    @Test
    fun ler_arquivo_inteiro_e_tamanho() {
        val base = tempBase()
        escrever(base, "x.bin", byteArrayOf(10, 20, 30))
        assertEquals(3L, Acervo.tamanhoDe("x.bin", base))
        assertArrayEquals(byteArrayOf(10, 20, 30), Acervo.lerPedaco("x.bin", base, 0, 1))
    }

    @Test
    fun ler_picado_remonta_o_arquivo() {
        val base = tempBase()
        // arquivo maior que um pedaço, lido em 2 partes (PEDACO + resto)
        val grande = ByteArray(Acervo.PEDACO + 5) { (it % 256).toByte() }
        escrever(base, "g.bin", grande)
        val p0 = Acervo.lerPedaco("g.bin", base, 0, 2)
        val p1 = Acervo.lerPedaco("g.bin", base, 1, 2)
        assertEquals(Acervo.PEDACO, p0.size)
        assertEquals(5, p1.size)
        assertArrayEquals(grande, p0 + p1)
    }

    @Test
    fun indice_de_pedaco_invalido_lanca() {
        val base = tempBase()
        escrever(base, "x.bin", byteArrayOf(1))
        assertThrows(IllegalArgumentException::class.java) { Acervo.lerPedaco("x.bin", base, 0, 0) }
        assertThrows(IllegalArgumentException::class.java) { Acervo.lerPedaco("x.bin", base, 2, 2) }
    }

    @Test
    fun arquivo_inexistente_ou_temporario_recusado() {
        val base = tempBase()
        escrever(base, "y.bin.parcial", byteArrayOf(1))
        assertThrows(IllegalArgumentException::class.java) { Acervo.tamanhoDe("sumido.txt", base) }
        // o temporário existe no disco, mas não é compartilhável
        assertThrows(IllegalArgumentException::class.java) { Acervo.tamanhoDe("y.bin.parcial", base) }
    }

    @Test
    fun travessia_e_nome_vazio_nao_escapam() {
        val base = tempBase()
        // '..' é DESCARTADO (igual ao acervo.py): "../x" vira base/x, não escapa.
        escrever(base, "x.txt", byteArrayOf(7, 7, 7))
        assertEquals(3L, Acervo.tamanhoDe("../x.txt", base))
        // nome que fica vazio depois de filtrar é inválido
        assertThrows(IllegalArgumentException::class.java) { Acervo.tamanhoDe("..", base) }
    }

    @Test
    fun symlink_apontando_pra_fora_e_recusado() {
        val base = tempBase()
        val fora = tempBase()
        val segredo = escrever(fora, "segredo.txt", byteArrayOf(42))
        // atalho DENTRO da base apontando pro arquivo de FORA
        Files.createSymbolicLink(File(base, "atalho.txt").toPath(), segredo.toPath())
        assertThrows(IllegalArgumentException::class.java) { Acervo.tamanhoDe("atalho.txt", base) }
        assertThrows(IllegalArgumentException::class.java) { Acervo.lerPedaco("atalho.txt", base, 0, 1) }
    }
}
