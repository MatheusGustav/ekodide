package com.ekodide.android.core

import java.io.File
import java.io.FileOutputStream
import java.nio.file.Files

/**
 * A caixa postal: grava com segurança o que CHEGA pela rede. Espelho do caixa_postal.py,
 * sobre `java.io.File` (vale no JVM e no armazenamento interno do Android; a gravação
 * via SAF na pasta escolhida pelo usuário entra na etapa do seletor de pasta).
 *
 * Lógica pura (sem rede): grava DENTRO de uma `base` cercada —
 *   - travessia ('../') é descartada (nunca escapa da base);
 *   - arquivo existente NÃO é sobrescrito (ganha ' (1)', ' (2)'…);
 *   - arquivo grande chega PICADO e é remontado num '.parcial' até o último pedaço,
 *     anotando progresso no '.parcial.meta' (pra RETOMAR depois).
 */
object CaixaPostal {

    private fun caminhoSeguro(nome: String, base: File): Pair<File, String> {
        val baseCanon = base.canonicalFile
        val partes = nome.replace('\\', '/').split('/')
            .filter { it.isNotEmpty() && it != "." && it != ".." }
        require(partes.isNotEmpty()) { "nome de arquivo inválido" }
        val alvoDir = if (partes.size == 1) baseCanon
        else File(baseCanon, partes.dropLast(1).joinToString("/"))
        val alvoDirCanon = alvoDir.canonicalFile
        if (baseCanon != alvoDirCanon && !dentroDe(baseCanon, alvoDirCanon)) {
            throw IllegalArgumentException("destino fora da pasta permitida")
        }
        return Pair(alvoDirCanon, partes.last())
    }

    private fun dentroDe(base: File, alvo: File): Boolean {
        var p: File? = alvo.parentFile
        while (p != null) {
            if (p == base) return true
            p = p.parentFile
        }
        return false
    }

    private fun nomeLivre(dir: File, nome: String): File {
        if (!File(dir, nome).exists()) return File(dir, nome)
        val ponto = nome.lastIndexOf('.')
        val tronco = if (ponto > 0) nome.substring(0, ponto) else nome
        val sufixo = if (ponto > 0) nome.substring(ponto) else ""
        var n = 1
        while (File(dir, "$tronco ($n)$sufixo").exists()) n++
        return File(dir, "$tronco ($n)$sufixo")
    }

    private fun lerProgresso(dir: File, filename: String, partes: Int, tamanho: Long): Int {
        val parcial = File(dir, "$filename.parcial")
        val meta = File(dir, "$filename.parcial.meta")
        if (!(parcial.exists() && meta.exists())) return 0
        try {
            val t = meta.readText().trim().split(Regex("\\s+"))
            val mp = t[0].toInt(); val mr = t[1].toInt(); val mt = t[2].toLong()
            if (mp == partes && mt == tamanho) return maxOf(0, minOf(mr, partes))
        } catch (_: Exception) {
        }
        return 0
    }

    /** Grava um arquivo INTEIRO dentro de `base` (recria subpastas, sem escapar/sobrescrever). */
    fun guardar(nome: String, conteudo: ByteArray, base: File): File {
        val (dir, filename) = caminhoSeguro(nome, base)
        dir.mkdirs()
        val alvo = nomeLivre(dir, filename)
        alvo.writeBytes(conteudo)
        return alvo
    }

    /** Quantos pedaços contíguos o destino já tem deste arquivo (pro carteiro RETOMAR). */
    fun progressoDe(nome: String, partes: Int, base: File, tamanho: Long = -1): Int {
        val (dir, filename) = caminhoSeguro(nome, base)
        return lerProgresso(dir, filename, partes, tamanho)
    }

    /**
     * Recebe UM pedaço e vai montando num '.parcial' (anotando '.parcial.meta'). No
     * último pedaço fecha, renomeia pro nome final (sem sobrescrever), apaga o meta e
     * devolve o caminho. Enquanto monta, devolve null. Idempotente: pedaço já recebido
     * é ignorado; pedaço fora de ordem é recusado.
     */
    fun guardarPedaco(
        nome: String, conteudo: ByteArray, parte: Int, partes: Int, base: File, tamanho: Long = -1,
    ): File? {
        val (dir, filename) = caminhoSeguro(nome, base)
        dir.mkdirs()
        val parcial = File(dir, "$filename.parcial")
        val meta = File(dir, "$filename.parcial.meta")

        val recebidos = lerProgresso(dir, filename, partes, tamanho)
        if (parte < recebidos) return null                 // reenvio repetido: ignora
        require(parte == recebidos) {                       // pulou um: não dá pra anexar com buraco
            "pedaço fora de ordem (esperava $recebidos, veio $parte)"
        }

        FileOutputStream(parcial, parte != 0).use { it.write(conteudo) }
        val agora = parte + 1

        if (agora >= partes) {                              // último pedaço: vira o final
            val final = nomeLivre(dir, filename)
            Files.move(parcial.toPath(), final.toPath())
            meta.delete()
            return final
        }
        meta.writeText("$partes $agora $tamanho")
        return null
    }
}
