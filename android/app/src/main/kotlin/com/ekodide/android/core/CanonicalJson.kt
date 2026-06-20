package com.ekodide.android.core

/**
 * JSON canônico byte-IDÊNTICO ao do Python:
 *
 *     json.dumps(carga, sort_keys=True, separators=(",",":"), ensure_ascii=False)
 *
 * É a base da assinatura HMAC (lacre): se os dois lados não gerarem exatamente os
 * mesmos bytes, a assinatura não confere. NENHUMA biblioteca Kotlin reproduz isso
 * fielmente (chaves ordenadas + separadores compactos + UTF-8 cru sem \u + inteiro
 * sem ".0"), então serializamos à mão — é a única forma de garantir o byte-idêntico.
 *
 * Suporta só os tipos que a carga do Ekodide usa: String, Int/Long, Boolean, null,
 * Map e List. Propositalmente NÃO suporta Double: o `ts` do Python é int (vira
 * "1750000000"); um Double renderizaria "1.75E9"/"...0" e quebraria o HMAC.
 */
object CanonicalJson {

    private const val HEX = "0123456789abcdef"

    fun encode(value: Any?): String = buildString { write(value, this) }

    private fun write(v: Any?, sb: StringBuilder) {
        when (v) {
            null -> sb.append("null")
            is Boolean -> sb.append(if (v) "true" else "false")
            is Int -> sb.append(v.toString())
            is Long -> sb.append(v.toString())
            is String -> writeString(v, sb)
            is Map<*, *> -> {
                // sort_keys=True: ordena pelo code point da chave (igual ao Python no BMP).
                val keys = v.keys.map { it as String }.sortedWith(naturalOrder())
                sb.append('{')
                keys.forEachIndexed { i, k ->
                    if (i > 0) sb.append(',')        // separador de itens = ","
                    writeString(k, sb)
                    sb.append(':')                   // separador chave/valor = ":"
                    write(v[k], sb)
                }
                sb.append('}')
            }
            is List<*> -> {
                sb.append('[')
                v.forEachIndexed { i, e ->
                    if (i > 0) sb.append(',')
                    write(e, sb)
                }
                sb.append(']')
            }
            else -> error("tipo não suportado no JSON canônico: ${v::class}")
        }
    }

    /**
     * Escapa string igual ao json do Python com ensure_ascii=False: escapa apenas
     * " \ e os controles C0; \b \t \n \f \r ganham forma curta; outros controles
     * viram \u00xx (hex minúsculo). '/' NÃO é escapado; não-ASCII passa cru (vira
     * UTF-8 no toByteArray no fim).
     */
    private fun writeString(s: String, sb: StringBuilder) {
        sb.append('"')
        for (ch in s) {
            when (ch.code) {
                '"'.code -> sb.append("\\\"")
                '\\'.code -> sb.append("\\\\")
                0x08 -> sb.append("\\b")   // backspace
                0x09 -> sb.append("\\t")   // tab
                0x0A -> sb.append("\\n")   // newline
                0x0C -> sb.append("\\f")   // form feed
                0x0D -> sb.append("\\r")   // carriage return
                else -> if (ch.code < 0x20) {
                    // controle C0 sem forma curta -> \u00xx (4 dígitos, hex minúsculo)
                    sb.append("\\u00")
                    sb.append(HEX[(ch.code ushr 4) and 0xF])
                    sb.append(HEX[ch.code and 0xF])
                } else {
                    sb.append(ch)
                }
            }
        }
        sb.append('"')
    }
}
