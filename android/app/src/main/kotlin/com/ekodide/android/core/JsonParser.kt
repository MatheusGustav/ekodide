package com.ekodide.android.core

/**
 * Parser JSON mínimo, à mão — par do CanonicalJson (que SERIALIZA). Lê o subconjunto
 * que o protocolo do Ekodide usa: objeto, lista, string (com escapes), inteiro, true/
 * false/null. Inteiro vira Long (pra re-serializar sem ".0" e bater o HMAC); número
 * com ponto/expoente vira Double (não usado pelo protocolo, mas suportado).
 *
 * Zero dependência (o org.json nem existe nos testes JVM puros). Quem chama trata as
 * exceções (o desempacotar converte qualquer erro em TrancaInvalida).
 */
object JsonParser {

    fun parse(texto: String): Any? {
        val p = Estado(texto)
        val v = p.valor()
        p.pulaEspaco()
        require(p.fim()) { "lixo depois do JSON" }
        return v
    }

    private class Estado(val s: String) {
        var i = 0

        fun fim() = i >= s.length
        fun pulaEspaco() { while (i < s.length && s[i].isWhitespace()) i++ }

        fun valor(): Any? {
            pulaEspaco()
            require(!fim()) { "JSON vazio" }
            return when (s[i]) {
                '{' -> objeto()
                '[' -> lista()
                '"' -> str()
                't' -> literal("true", true)
                'f' -> literal("false", false)
                'n' -> literal("null", null)
                else -> numero()
            }
        }

        fun objeto(): Map<String, Any?> {
            val m = LinkedHashMap<String, Any?>()
            i++ // '{'
            pulaEspaco()
            if (s[i] == '}') { i++; return m }
            while (true) {
                pulaEspaco()
                val chave = str()
                pulaEspaco()
                require(s[i] == ':') { "esperava ':'" }
                i++
                m[chave] = valor()
                pulaEspaco()
                val c = s[i]; i++
                if (c == '}') break
                require(c == ',') { "esperava ',' ou '}'" }
            }
            return m
        }

        fun lista(): List<Any?> {
            val l = ArrayList<Any?>()
            i++ // '['
            pulaEspaco()
            if (s[i] == ']') { i++; return l }
            while (true) {
                l.add(valor())
                pulaEspaco()
                val c = s[i]; i++
                if (c == ']') break
                require(c == ',') { "esperava ',' ou ']'" }
            }
            return l
        }

        fun str(): String {
            require(s[i] == '"') { "esperava string" }
            i++
            val sb = StringBuilder()
            while (true) {
                val c = s[i]; i++
                when (c) {
                    '"' -> return sb.toString()
                    '\\' -> {
                        val e = s[i]; i++
                        when (e) {
                            '"' -> sb.append('"')
                            '\\' -> sb.append('\\')
                            '/' -> sb.append('/')
                            'b' -> sb.append('\b')
                            'f' -> sb.append('\u000C')
                            'n' -> sb.append('\n')
                            'r' -> sb.append('\r')
                            't' -> sb.append('\t')
                            'u' -> {
                                val h = s.substring(i, i + 4); i += 4
                                sb.append(h.toInt(16).toChar())
                            }
                            else -> error("escape inválido: \\$e")
                        }
                    }
                    else -> sb.append(c)
                }
            }
        }

        fun numero(): Any {
            val ini = i
            if (s[i] == '-') i++
            while (i < s.length && s[i].isDigit()) i++
            var inteiro = true
            if (i < s.length && s[i] == '.') { inteiro = false; i++; while (i < s.length && s[i].isDigit()) i++ }
            if (i < s.length && (s[i] == 'e' || s[i] == 'E')) {
                inteiro = false; i++
                if (i < s.length && (s[i] == '+' || s[i] == '-')) i++
                while (i < s.length && s[i].isDigit()) i++
            }
            val t = s.substring(ini, i)
            return if (inteiro) t.toLong() else t.toDouble()
        }

        fun literal(palavra: String, v: Any?): Any? {
            require(s.startsWith(palavra, i)) { "literal inválido" }
            i += palavra.length
            return v
        }
    }
}
