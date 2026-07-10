package com.ekodide.android.server

import com.ekodide.android.core.Acervo
import java.io.File

/**
 * O mapa aberto do "puxar": com o acesso total a arquivos concedido, o admin (PC)
 * NAVEGA pelo armazenamento — pede qualquer pasta ('DCIM/Screenshots') em vez de ficar
 * preso à única pasta escolhida no SAF. É o que tira a fricção de "trocar pasta no
 * aparelho a cada uso": quem escolhe a pasta passa a ser quem puxa.
 *
 * Poder maior, mesma disciplina de cerca do Acervo — e duas contenções próprias:
 *   - a VISTA é rasa (um nível por vez): listar a raiz não varre o armazenamento
 *     inteiro; navegar é descer pasta a pasta, como um 'ls';
 *   - pastas PROIBIDAS em código (Android/data, Android/obb) são recusadas mesmo
 *     que o sistema deixasse — dado de app alheio não é assunto do correio.
 *
 * Lógica pura (recebe a raiz por parâmetro): testável no JVM, sem Android.
 */
class FonteAberta(private val raiz: File) {

    /** Um nível da árvore: arquivos puxáveis + nomes das subpastas (pra descer). */
    data class Vista(val itens: List<Acervo.Item>, val pastas: List<String>)

    /** Vista rasa da `pasta` (relativa à raiz; "" = a própria raiz). */
    fun listar(pasta: String): Vista {
        val base = resolverPasta(pasta)
        val filhos = base.listFiles() ?: emptyArray()
        val itens = filhos
            .filter { it.isFile && !it.name.endsWith(".parcial") && !it.name.endsWith(".parcial.meta") }
            .map { Acervo.Item(it.name, it.length()) }
            .sortedBy { it.nome }
        val pastas = filhos.filter { it.isDirectory }.map { it.name }.sorted()
        return Vista(itens, pastas)
    }

    /** Um pedaço do arquivo `nome` DENTRO de `pasta` — a cerca do Acervo continua valendo. */
    fun lerPedaco(pasta: String, nome: String, parte: Int, partes: Int): ByteArray =
        Acervo.lerPedaco(nome, resolverPasta(pasta), parte, partes)

    /**
     * Resolve `pasta` (relativa) pra um diretório REAL dentro da raiz. Mesma cerca do
     * Acervo (travessia descartada, symlink pra fora é pego) + a lista proibida.
     */
    private fun resolverPasta(pasta: String): File {
        val raizCanon = raiz.canonicalFile
        val partes = pasta.replace('\\', '/').split('/')
            .filter { it.isNotEmpty() && it != "." && it != ".." }
        val relativo = partes.joinToString("/")
        if (PROIBIDAS.any { relativo.startsWith(it, ignoreCase = true) }) {
            throw IllegalArgumentException("pasta reservada do sistema")
        }
        if (partes.isEmpty()) return raizCanon
        // canonicalFile segue symlink de propósito: pega fuga por atalho.
        val alvo = File(raizCanon, relativo).canonicalFile
        if (raizCanon != alvo && !dentroDe(raizCanon, alvo)) {
            throw IllegalArgumentException("fora do armazenamento")
        }
        if (!alvo.isDirectory) throw IllegalArgumentException("pasta não encontrada: $pasta")
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

    companion object {
        /** Dado de app alheio: o sistema já cerca, e a gente recusa por conta própria. */
        val PROIBIDAS = listOf("Android/data", "Android/obb")
    }
}
