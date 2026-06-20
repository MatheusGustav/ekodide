package com.ekodide.android.core

import javax.crypto.Mac
import javax.crypto.spec.SecretKeySpec
import kotlin.math.abs

/** Mensagem recusada pela fechadura (assinatura, formato ou tempo). */
class TrancaInvalida(mensagem: String) : Exception(mensagem)

/**
 * O lacre: assina/verifica cada mensagem com o segredo (HMAC-SHA256). O segredo
 * NUNCA trafega. Espelho byte-idêntico do lacre.py.
 */
object Lacre {
    private const val HEX = "0123456789abcdef"

    /** Janela do carimbo de tempo (segundos): barra repetição de mensagens antigas. */
    const val JANELA_SEGUNDOS = 300L

    /** HMAC-SHA256 de `corpo` com `segredo`, em hex minúsculo (igual ao .hexdigest()). */
    fun assinar(corpo: ByteArray, segredo: String): String {
        val mac = Mac.getInstance("HmacSHA256")
        mac.init(SecretKeySpec(segredo.toByteArray(Charsets.UTF_8), "HmacSHA256"))
        return mac.doFinal(corpo).toHexLower()
    }

    /**
     * Carimba o tempo, assina e devolve os bytes prontos pra enviar. `agora` em
     * segundos epoch (default = relógio atual). Espelha lacre.empacotar.
     */
    fun empacotar(carga: Map<String, Any?>, segredo: String, agora: Long? = null): ByteArray {
        val ts = agora ?: (System.currentTimeMillis() / 1000)
        val selada = LinkedHashMap<String, Any?>(carga).apply { put("ts", ts) }
        val assinatura = assinar(CanonicalJson.encode(selada).toByteArray(Charsets.UTF_8), segredo)
        val envelope = linkedMapOf<String, Any?>("carga" to selada, "assinatura" to assinatura)
        return CanonicalJson.encode(envelope).toByteArray(Charsets.UTF_8)
    }

    /**
     * Verifica assinatura e tempo; devolve a carga. Lança TrancaInvalida se algo não
     * bate. Espelha lacre.desempacotar — inclusive a re-canonicalização da carga
     * (json.loads + re-dump canônico) pra recalcular o HMAC.
     */
    @Suppress("UNCHECKED_CAST")
    fun desempacotar(corpo: ByteArray, segredo: String, agora: Long? = null): Map<String, Any?> {
        val envelope = try {
            JsonParser.parse(String(corpo, Charsets.UTF_8)) as? Map<String, Any?>
        } catch (e: Exception) {
            throw TrancaInvalida("mensagem malformada")
        } ?: throw TrancaInvalida("mensagem malformada")

        val carga = envelope["carga"] as? Map<String, Any?>
            ?: throw TrancaInvalida("mensagem malformada")
        val assinatura = envelope["assinatura"] as? String
            ?: throw TrancaInvalida("mensagem malformada")

        val esperada = assinar(CanonicalJson.encode(carga).toByteArray(Charsets.UTF_8), segredo)
        if (!comparaConstante(esperada, assinatura)) {
            throw TrancaInvalida("assinatura não confere (segredo errado ou corpo adulterado)")
        }

        val ts = carga["ts"] as? Long ?: throw TrancaInvalida("sem carimbo de tempo")
        val n = agora ?: (System.currentTimeMillis() / 1000)
        if (abs(n - ts) > JANELA_SEGUNDOS) {
            throw TrancaInvalida("mensagem fora da janela de tempo (possível repetição)")
        }
        return carga
    }

    /** Comparação em tempo constante (não vaza por timing), como hmac.compare_digest. */
    private fun comparaConstante(a: String, b: String): Boolean {
        val ab = a.toByteArray(Charsets.UTF_8)
        val bb = b.toByteArray(Charsets.UTF_8)
        if (ab.size != bb.size) return false
        var dif = 0
        for (k in ab.indices) dif = dif or (ab[k].toInt() xor bb[k].toInt())
        return dif == 0
    }

    // Hex minúsculo correto: mascara pra 0xFF e zera-preenche 2 chars por byte.
    private fun ByteArray.toHexLower(): String {
        val sb = StringBuilder(size * 2)
        for (b in this) {
            val v = b.toInt() and 0xFF
            sb.append(HEX[v ushr 4])
            sb.append(HEX[v and 0x0F])
        }
        return sb.toString()
    }
}
