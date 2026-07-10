package com.ekodide.android.server

import com.ekodide.android.core.Cofre
import com.ekodide.android.core.Lacre
import org.junit.Assert.assertArrayEquals
import org.junit.Assert.assertEquals
import org.junit.Assert.assertTrue
import org.junit.Test
import java.io.File
import java.nio.file.Files
import java.util.Base64

class RecebedorTest {

    private val secret = "casa-vento-rio-azul-pedra-lobo"
    private fun tempBase(): File = Files.createTempDirectory("ekodide-receb").toFile()

    private fun hexToBytes(s: String) = s.chunked(2).map { it.toInt(16).toByte() }.toByteArray()

    /** Monta um corpo /receber (cifra + lacra) como o carteiro faria. */
    private fun corpoReceber(
        nome: String, dados: ByteArray,
        parte: Int? = null, partes: Int? = null, tamanho: Long? = null,
    ): ByteArray {
        val carga = linkedMapOf<String, Any?>(
            "nome" to nome,
            "conteudo" to Base64.getEncoder().encodeToString(Cofre.cifrar(dados, secret)),
        )
        if (partes != null) {
            carga["parte"] = parte; carga["partes"] = partes; carga["tamanho"] = tamanho
        }
        return Lacre.empacotar(carga, secret)
    }

    @Test
    fun recebe_arquivo_inteiro_do_python() {
        // Vetor ponta-a-ponta GERADO pelo carteiro/cofre do Python (nonce fixo).
        val env =
            "{\"assinatura\":\"40e171abe0e8e53db4fff934b79db39d1e2081470d2e179c3a4fb9aaacf8222e\"," +
                "\"carga\":{\"conteudo\":\"AAAAAAAAAAAAAAAA6b4qP1vNuN+2KfnjuHE7Tuz9ddcaUvZve5cIHTRvb1xE1O44NhVNg6GTygYL957/HlA=\"," +
                "\"nome\":\"pasta/sub/arquivo bin.dat\",\"ts\":1750000000}}"
        val esperado =
            hexToBytes("636f6e746575646f2064652074657374652000012062696e6172696f20ff2066696d")

        val base = tempBase()
        val resp = Recebedor.tratar("/receber", env.toByteArray(Charsets.UTF_8), secret, base, agora = 1750000000L)

        assertEquals(200, resp.status)
        val gravado = File(base, "pasta/sub/arquivo bin.dat")
        assertTrue(gravado.exists())
        assertArrayEquals(esperado, gravado.readBytes())
    }

    @Test
    fun recebe_picado_remonta_e_progresso() {
        val base = tempBase()
        val nome = "video.mp4"
        val p0 = ByteArray(100) { it.toByte() }
        val p1 = ByteArray(40) { (it + 7).toByte() }
        val total = (p0.size + p1.size).toLong()

        val r0 = Recebedor.tratar("/receber", corpoReceber(nome, p0, 0, 2, total), secret, base)
        assertEquals(200, r0.status)

        // /progresso deve dizer que já tem 1 pedaço
        val prog = Recebedor.tratar(
            "/progresso",
            Lacre.empacotar(linkedMapOf<String, Any?>("nome" to nome, "partes" to 2, "tamanho" to total), secret),
            secret, base,
        )
        assertEquals(1L, Lacre.desempacotar(prog.corpo, secret)["recebidos"])

        val r1 = Recebedor.tratar("/receber", corpoReceber(nome, p1, 1, 2, total), secret, base)
        assertEquals(200, r1.status)
        assertArrayEquals(p0 + p1, File(base, nome).readBytes())
    }

    @Test
    fun rejeita_segredo_errado_com_401() {
        val base = tempBase()
        val corpoComOutroSegredo = run {
            val carga = linkedMapOf<String, Any?>("nome" to "x", "conteudo" to "AAAA")
            Lacre.empacotar(carga, "segredo-do-atacante")
        }
        val resp = Recebedor.tratar("/receber", corpoComOutroSegredo, secret, base)
        assertEquals(401, resp.status)
    }

    @Test
    fun rota_desconhecida_404() {
        val base = tempBase()
        val corpo = Lacre.empacotar(linkedMapOf<String, Any?>("oi" to "mundo"), secret)
        assertEquals(404, Recebedor.tratar("/inexistente", corpo, secret, base).status)
    }

    /** Corpo de /buscar (só lacrado: o pedido não leva conteúdo). */
    private fun corpoBuscar(nome: String, parte: Int, partes: Int): ByteArray =
        Lacre.empacotar(
            linkedMapOf<String, Any?>("nome" to nome, "parte" to parte, "partes" to partes), secret,
        )

    @Test
    fun listar_devolve_a_pasta_compartilhada() {
        val base = tempBase()
        val compart = tempBase()
        File(compart, "Fotos").mkdirs()
        File(compart, "Fotos/a.png").writeBytes(byteArrayOf(1, 2))
        File(compart, "b.txt").writeBytes(byteArrayOf(9))

        val corpo = Lacre.empacotar(linkedMapOf<String, Any?>(), secret)
        val resp = Recebedor.tratar("/listar", corpo, secret, base, compartilhar = FonteArquivo(compart))
        assertEquals(200, resp.status)

        @Suppress("UNCHECKED_CAST")
        val itens = Lacre.desempacotar(resp.corpo, secret)["itens"] as List<Map<String, Any?>>
        assertEquals(listOf("Fotos/a.png", "b.txt"), itens.map { it["nome"] })
        assertEquals(listOf(2L, 1L), itens.map { it["tamanho"] })
    }

    @Test
    fun listar_vazio_quando_nada_compartilhado() {
        val base = tempBase()
        val corpo = Lacre.empacotar(linkedMapOf<String, Any?>(), secret)
        val resp = Recebedor.tratar("/listar", corpo, secret, base) // sem compartilhar
        assertEquals(200, resp.status)
        @Suppress("UNCHECKED_CAST")
        val itens = Lacre.desempacotar(resp.corpo, secret)["itens"] as List<Map<String, Any?>>
        assertTrue(itens.isEmpty())
    }

    @Test
    fun buscar_entrega_pedaco_cifrado_que_decifra_identico() {
        val base = tempBase()
        val compart = tempBase()
        val dados = ByteArray(200) { (it * 3).toByte() }
        File(compart, "arq.bin").writeBytes(dados)

        val resp = Recebedor.tratar("/buscar", corpoBuscar("arq.bin", 0, 1), secret, base, compartilhar = FonteArquivo(compart))
        assertEquals(200, resp.status)

        val carga = Lacre.desempacotar(resp.corpo, secret)
        assertEquals("arq.bin", carga["nome"])
        assertEquals(0L, carga["parte"])
        assertEquals(1L, carga["partes"])
        // na rede veio cifrado; decifrar tem que devolver byte-idêntico
        val aberto = Cofre.decifrar(Base64.getDecoder().decode(carga["conteudo"] as String), secret)
        assertArrayEquals(dados, aberto)
    }

    @Test
    fun buscar_sem_compartilhar_da_403() {
        val base = tempBase()
        val resp = Recebedor.tratar("/buscar", corpoBuscar("x", 0, 1), secret, base) // sem compartilhar
        assertEquals(403, resp.status)
    }

    @Test
    fun buscar_arquivo_inexistente_da_400() {
        val base = tempBase()
        val compart = tempBase()
        val resp = Recebedor.tratar("/buscar", corpoBuscar("sumido.txt", 0, 1), secret, base, compartilhar = FonteArquivo(compart))
        assertEquals(400, resp.status)
    }

    // ---------- navegação por pastas (campo `pasta` + FonteAberta) ----------

    /** Uma raiz de armazenamento de mentira, com uma foto em DCIM/Camera. */
    private fun raizNavegavel(): File {
        val raiz = tempBase()
        File(raiz, "DCIM/Camera").mkdirs()
        File(raiz, "DCIM/Camera/foto.jpg").writeBytes(byteArrayOf(4, 5, 6))
        return raiz
    }

    @Test
    fun listar_com_pasta_devolve_vista_rasa() {
        val base = tempBase()
        val raiz = raizNavegavel()
        val corpo = Lacre.empacotar(linkedMapOf<String, Any?>("pasta" to "DCIM"), secret)
        val resp = Recebedor.tratar("/listar", corpo, secret, base, aberto = FonteAberta(raiz))
        assertEquals(200, resp.status)
        val carga = Lacre.desempacotar(resp.corpo, secret)
        @Suppress("UNCHECKED_CAST")
        assertEquals(listOf("Camera"), carga["pastas"] as List<String>)
        @Suppress("UNCHECKED_CAST")
        assertTrue((carga["itens"] as List<*>).isEmpty())
    }

    @Test
    fun listar_com_pasta_sem_navegacao_da_403() {
        val base = tempBase()
        val corpo = Lacre.empacotar(linkedMapOf<String, Any?>("pasta" to "DCIM"), secret)
        val resp = Recebedor.tratar("/listar", corpo, secret, base) // sem `aberto`
        assertEquals(403, resp.status)
    }

    @Test
    fun listar_com_pasta_invalida_da_400() {
        val base = tempBase()
        val corpo = Lacre.empacotar(linkedMapOf<String, Any?>("pasta" to "Nao/Existe"), secret)
        val resp = Recebedor.tratar("/listar", corpo, secret, base, aberto = FonteAberta(raizNavegavel()))
        assertEquals(400, resp.status)
    }

    @Test
    fun buscar_com_pasta_entrega_o_arquivo_da_pasta_pedida() {
        val base = tempBase()
        val raiz = raizNavegavel()
        val corpo = Lacre.empacotar(
            linkedMapOf<String, Any?>(
                "nome" to "foto.jpg", "parte" to 0, "partes" to 1, "pasta" to "DCIM/Camera",
            ),
            secret,
        )
        // sem `compartilhar` de propósito: a navegação não depende da pasta SAF
        val resp = Recebedor.tratar("/buscar", corpo, secret, base, aberto = FonteAberta(raiz))
        assertEquals(200, resp.status)
        val carga = Lacre.desempacotar(resp.corpo, secret)
        val aberto = Cofre.decifrar(Base64.getDecoder().decode(carga["conteudo"] as String), secret)
        assertArrayEquals(byteArrayOf(4, 5, 6), aberto)
    }

    @Test
    fun buscar_com_pasta_sem_navegacao_da_403() {
        val base = tempBase()
        val corpo = Lacre.empacotar(
            linkedMapOf<String, Any?>(
                "nome" to "foto.jpg", "parte" to 0, "partes" to 1, "pasta" to "DCIM/Camera",
            ),
            secret,
        )
        // mesmo com uma pasta SAF compartilhada, `pasta` exige a navegação liberada
        val resp = Recebedor.tratar("/buscar", corpo, secret, base, compartilhar = FonteArquivo(tempBase()))
        assertEquals(403, resp.status)
    }
}
