package com.ekodide.android.core

import java.security.SecureRandom
import java.util.Locale

/**
 * O código de pareamento: um segredo forte que dá pra DIGITAR (e escanear). Espelho
 * byte-a-byte do frase.py — os dois mudam JUNTOS.
 *
 * O segredo dos dois lados tem que ser o MESMO. Ele nasce como um CÓDIGO curto
 * sorteado — 'K7TP3-XQ9FM-H' — e NUNCA cruza a rede: vai de um aparelho ao outro pela
 * tela, câmera ou dedos (o "out-of-band" do pareamento). Quem sorteia é SEMPRE a
 * máquina: senha humana cai em dicionário (dá pra testar offline contra um pacote
 * lacrado capturado no Wi-Fi), sorteio não.
 *
 * A forma CANÔNICA do segredo é maiúscula e sem traço (11 caracteres: 10 sorteados +
 * 1 verificador). Traço e caixa baixa são ROUPA de leitura: [validar] tira a roupa e
 * devolve a forma canônica, e é ELA que se grava nas duas pontas — dali em diante o
 * segredo é usado byte-a-byte, sem mexer.
 */
object Frase {

    // 31 símbolos: maiúsculas + dígitos, SEM os confundíveis 0/O e 1/I/L. 10 sorteados
    // dão 31^10 ≈ 2^49,5 (~50 bits). E 31 é primo: o verificador (soma ponderada
    // mod 31) acusa GARANTIDO qualquer erro de um caractere e qualquer troca de
    // vizinhos. IDÊNTICO ao frase.py.
    const val ALFABETO = "23456789ABCDEFGHJKMNPQRSTUVWXYZ"
    const val SORTEADOS = 10           // caracteres sorteados (a força do segredo)
    const val TAMANHO = SORTEADOS + 1  // + 1 verificador no fim

    // CSPRNG (igual ao secrets do Python): sorteio forte, não previsível.
    private val rng = SecureRandom()

    /** O caractere verificador do corpo: soma ponderada pela posição, mod 31. */
    internal fun verificador(corpo: String): Char {
        var soma = 0
        corpo.forEachIndexed { i, c -> soma += (i + 1) * ALFABETO.indexOf(c) }
        return ALFABETO[soma % ALFABETO.length]
    }

    /** Sorteia um código novo, já com o verificador — canônico, pronto pra guardar. */
    fun gerar(): String {
        val corpo = buildString {
            repeat(SORTEADOS) { append(ALFABETO[rng.nextInt(ALFABETO.length)]) }
        }
        return corpo + verificador(corpo)
    }

    /**
     * Veste um código canônico pra LEITURA: 'K7TP3-XQ9FM-H' (5 + 5 + verificador).
     * O traço é só roupa — [validar] aceita com ou sem.
     */
    fun formatar(codigo: String): String =
        "${codigo.take(5)}-${codigo.substring(5, SORTEADOS)}-${codigo.substring(SORTEADOS)}"

    /**
     * Confere um código digitado/escaneado e devolve a forma canônica (a que se grava).
     *
     * Aceita a roupa da leitura (traço, espaço, caixa baixa). Recusa com
     * [IllegalArgumentException] de mensagem clara o que não é código sorteado:
     * tamanho errado, caractere fora do alfabeto ou verificador que não bate — o erro
     * de digitação é acusado NA HORA, em vez de quebrar o lacre em silêncio depois.
     */
    fun validar(texto: String): String {
        // Locale.ROOT: uppercase sem regra de idioma (em turco 'i' viraria 'İ')
        val canonico = texto.uppercase(Locale.ROOT).filterNot { it.isWhitespace() || it == '-' }
        require(canonico.length == TAMANHO) {
            "código de pareamento tem $TAMANHO caracteres " +
                "($SORTEADOS sorteados + 1 verificador); vieram ${canonico.length}"
        }
        val fora = canonico.filterNot { it in ALFABETO }.toSortedSet()
        require(fora.isEmpty()) {
            "caractere que não existe em código de pareamento: ${fora.joinToString(", ")} " +
                "(0/O e 1/I/L ficam fora de propósito, por parecidos — releia na tela)"
        }
        require(canonico.last() == verificador(canonico.dropLast(1))) {
            "o verificador não bate — algum caractere saiu trocado; confira e digite de novo"
        }
        return canonico
    }
}
