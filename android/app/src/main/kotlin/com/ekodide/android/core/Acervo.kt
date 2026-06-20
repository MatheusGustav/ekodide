package com.ekodide.android.core

import java.io.File
import java.io.RandomAccessFile

/**
 * O acervo: o lado de LEITURA que o "puxar" expõe. Espelho do acervo.py — e o oposto da
 * CaixaPostal (que GRAVA o que chega; aqui a gente LÊ pra entregar). Um ponto de leitura
 * é poder, então só se lê de DENTRO da pasta compartilhada, com a mesma cerca e um
 * cuidado a mais:
 *
 *   - travessia ('../') é descartada — nunca escapa da pasta;
 *   - symlink que aponta pra FORA da pasta é recusado (canonicalFile resolve o atalho,
 *     e o alvo real cai fora da cerca) — risco que o lado de escrita não corre;
 *   - os temporários de recebimento ('.parcial'/'.parcial.meta') NÃO entram na lista
 *     (são montagem em andamento, não arquivo pra compartilhar).
 *
 * Lógica pura (sem rede): recebe a pasta `base` e um nome relativo. Quem expõe isso pela
 * rede (HTTP) é o Recebedor (rotas /listar e /buscar).
 */
object Acervo {
    // Mesmo pedaço do carteiro/CaixaPostal: arquivo grande é lido/devolvido picado.
    const val PEDACO = 16 * 1024 * 1024

    data class Item(val nome: String, val tamanho: Long)

    private fun resolverDentro(nome: String, base: File): File {
        val baseCanon = base.canonicalFile
        val partes = nome.replace('\\', '/').split('/')
            .filter { it.isNotEmpty() && it != "." && it != ".." }
        require(partes.isNotEmpty()) { "nome de arquivo inválido" }
        // canonicalFile segue symlink de propósito: pega fuga por atalho.
        val alvo = File(baseCanon, partes.joinToString("/")).canonicalFile
        if (baseCanon != alvo && !dentroDe(baseCanon, alvo)) {
            throw IllegalArgumentException("fora da pasta compartilhada")
        }
        return alvo
    }

    private fun dentroDe(base: File, alvo: File): Boolean {
        var p: File? = alvo.parentFile
        while (p != null) {
            if (p == base) return true
            p = p.parentFile
        }
        return false
    }

    private fun eCompartilhavel(p: File): Boolean =
        p.isFile && !p.name.endsWith(".parcial") && !p.name.endsWith(".parcial.meta")

    /**
     * O que dá pra puxar: itens {nome relativo, tamanho}, ordenados por nome, recursivo
     * (preserva subpastas). Pasta inexistente ou não compartilhada (null) -> lista vazia:
     * nada fica exposto sem querer.
     */
    fun listar(base: File?): List<Item> {
        if (base == null || !base.isDirectory) return emptyList()
        val baseCanon = base.canonicalFile
        return baseCanon.walkTopDown()
            .filter { eCompartilhavel(it) }
            .map { Item(it.relativeTo(baseCanon).invariantSeparatorsPath, it.length()) }
            .sortedBy { it.nome }
            .toList()
    }

    /** Tamanho (bytes) de um arquivo compartilhado. Mesma cerca do `lerPedaco`. */
    fun tamanhoDe(nome: String, base: File): Long {
        val alvo = resolverDentro(nome, base)
        require(eCompartilhavel(alvo)) { "arquivo não disponível" }
        return alvo.length()
    }

    /**
     * Lê o pedaço `parte` (de `partes`), cada um de até PEDACO bytes (o último vem menor).
     * Arquivo que cabe num pedaço vai inteiro com parte=0, partes=1. Cerca de segurança:
     * nunca lê fora da pasta compartilhada.
     */
    fun lerPedaco(nome: String, base: File, parte: Int, partes: Int): ByteArray {
        require(partes >= 1 && parte >= 0 && parte < partes) { "índice de pedaço inválido" }
        val alvo = resolverDentro(nome, base)
        require(eCompartilhavel(alvo)) { "arquivo não disponível" }
        RandomAccessFile(alvo, "r").use { f ->
            val inicio = parte.toLong() * PEDACO
            f.seek(inicio)
            val restante = (f.length() - inicio).coerceAtLeast(0L)
            val n = minOf(PEDACO.toLong(), restante).toInt()
            val buf = ByteArray(n)
            f.readFully(buf)
            return buf
        }
    }
}
