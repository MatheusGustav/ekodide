package com.ekodide.android

import android.content.Context
import android.net.Uri
import android.provider.DocumentsContract
import com.ekodide.android.core.Acervo
import com.ekodide.android.server.FonteCompartilhada

/**
 * Fonte compartilhada apontando pra uma pasta escolhida pelo usuário via SAF (o seletor
 * do Android). Lê por `content://` com DocumentsContract — zero dependência nova.
 *
 * A cerca de segurança é inerente: a árvore concedida (treeUri) É o limite — o SAF não
 * deixa sair dela; e ao resolver um nome relativo a gente descarta '.'/'..'/vazio e só
 * desce de pasta em pasta casando pelo nome exibido. Espelha o papel do Acervo, mas sobre
 * documentos do Android em vez de arquivos comuns.
 */
class FonteSaf(private val context: Context, private val treeUri: Uri) : FonteCompartilhada {

    private val cr get() = context.contentResolver
    private val rootId: String = DocumentsContract.getTreeDocumentId(treeUri)

    override fun listar(): List<Acervo.Item> {
        val out = mutableListOf<Acervo.Item>()
        listarRec(rootId, "", out)
        return out.sortedBy { it.nome }
    }

    private fun listarRec(parentId: String, prefixo: String, out: MutableList<Acervo.Item>) {
        val children = DocumentsContract.buildChildDocumentsUriUsingTree(treeUri, parentId)
        cr.query(
            children,
            arrayOf(
                DocumentsContract.Document.COLUMN_DOCUMENT_ID,
                DocumentsContract.Document.COLUMN_DISPLAY_NAME,
                DocumentsContract.Document.COLUMN_MIME_TYPE,
                DocumentsContract.Document.COLUMN_SIZE,
            ),
            null, null, null,
        )?.use { c ->
            while (c.moveToNext()) {
                val id = c.getString(0)
                val nome = c.getString(1)
                val mime = c.getString(2)
                val tam = if (c.isNull(3)) 0L else c.getLong(3)
                val rel = if (prefixo.isEmpty()) nome else "$prefixo/$nome"
                if (mime == DocumentsContract.Document.MIME_TYPE_DIR) {
                    listarRec(id, rel, out)
                } else {
                    out.add(Acervo.Item(rel, tam))
                }
            }
        }
    }

    override fun lerPedaco(nome: String, parte: Int, partes: Int): ByteArray {
        require(partes >= 1 && parte >= 0 && parte < partes) { "índice de pedaço inválido" }
        val docId = resolver(nome) ?: throw IllegalArgumentException("arquivo não disponível")
        val uri = DocumentsContract.buildDocumentUriUsingTree(treeUri, docId)
        (cr.openInputStream(uri) ?: throw IllegalArgumentException("não abriu o arquivo")).use { ins ->
            var pular = parte.toLong() * Acervo.PEDACO
            while (pular > 0) {
                val s = ins.skip(pular)
                if (s <= 0) break
                pular -= s
            }
            val buf = ByteArray(Acervo.PEDACO)
            var lido = 0
            while (lido < buf.size) {
                val n = ins.read(buf, lido, buf.size - lido)
                if (n < 0) break
                lido += n
            }
            return if (lido == buf.size) buf else buf.copyOf(lido)
        }
    }

    /** Caminho relativo -> documentId do arquivo (descartando '.'/'..'); null se sumiu/escapou. */
    private fun resolver(nome: String): String? {
        val partes = nome.replace('\\', '/').split('/')
            .filter { it.isNotEmpty() && it != "." && it != ".." }
        if (partes.isEmpty()) return null
        var parentId = rootId
        for ((i, seg) in partes.withIndex()) {
            val achado = acharFilho(parentId, seg) ?: return null
            val ultimo = i == partes.size - 1
            if (ultimo) return if (!achado.second) achado.first else null // último tem que ser arquivo
            if (!achado.second) return null                                // do meio tem que ser pasta
            parentId = achado.first
        }
        return null
    }

    /** (docId, ehPasta) do filho com aquele nome exibido, ou null. */
    private fun acharFilho(parentId: String, nome: String): Pair<String, Boolean>? {
        val children = DocumentsContract.buildChildDocumentsUriUsingTree(treeUri, parentId)
        cr.query(
            children,
            arrayOf(
                DocumentsContract.Document.COLUMN_DOCUMENT_ID,
                DocumentsContract.Document.COLUMN_DISPLAY_NAME,
                DocumentsContract.Document.COLUMN_MIME_TYPE,
            ),
            null, null, null,
        )?.use { c ->
            while (c.moveToNext()) {
                if (c.getString(1) == nome) {
                    val ehPasta = c.getString(2) == DocumentsContract.Document.MIME_TYPE_DIR
                    return Pair(c.getString(0), ehPasta)
                }
            }
        }
        return null
    }
}
