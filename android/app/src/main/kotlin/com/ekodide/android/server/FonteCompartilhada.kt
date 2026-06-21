package com.ekodide.android.server

import com.ekodide.android.core.Acervo
import java.io.File

/**
 * O que o "puxar" expõe, sem amarrar a COMO os bytes são lidos. Duas implementações:
 *   - [FonteArquivo]: pasta de arquivos comuns (java.io.File) — pura, testável no JVM;
 *   - FonteSaf (no app): pasta escolhida pelo usuário via SAF (content://, Android).
 *
 * Assim o Recebedor (já provado) fala com a abstração e o core de leitura cercada
 * (Acervo) continua intocado.
 */
interface FonteCompartilhada {
    /** Itens disponíveis pra puxar: {nome relativo, tamanho}, recursivo. */
    fun listar(): List<Acervo.Item>

    /** Um pedaço (de PEDACO bytes) do arquivo `nome`. Lança se o nome escapar/sumir. */
    fun lerPedaco(nome: String, parte: Int, partes: Int): ByteArray
}

/** Fonte baseada em pasta de arquivos comuns — delega ao Acervo (leitura cercada). */
class FonteArquivo(private val base: File) : FonteCompartilhada {
    override fun listar(): List<Acervo.Item> = Acervo.listar(base)
    override fun lerPedaco(nome: String, parte: Int, partes: Int): ByteArray =
        Acervo.lerPedaco(nome, base, parte, partes)
}
