package com.ekodide.android.core

import javax.crypto.Mac
import javax.crypto.spec.SecretKeySpec

/**
 * O lacre: assina/verifica cada mensagem com o segredo (HMAC-SHA256). O segredo
 * NUNCA trafega. Espelho byte-idêntico do lacre.py.
 *
 * Esta parte cobre o lado de PRODUÇÃO (assinar/empacotar), provável de testar no
 * JVM contra os vetores-ouro. A verificação (desempacotar) precisa de um parser
 * JSON e entra junto com o servidor.
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

    // Hex minúsculo correto: mascara pra 0xFF e zera-preenche 2 chars por byte.
    // (o "%x"/String.format ingênuo erra com bytes >= 0x80 e < 0x10.)
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
