package com.ekodide.android.core

import javax.crypto.Mac
import javax.crypto.spec.SecretKeySpec

/**
 * HKDF-SHA256 (RFC 5869) à mão — não existe na stdlib do Android/JVM, e são ~25
 * linhas sobre o Mac que já temos (zero dependência nova, fiel à ética do projeto).
 *
 * Espelha o Python:
 *   HKDF(SHA256, length=32, salt=None, info=b"ekodide-cofre-aes256gcm-v1").derive(segredo_utf8)
 *
 * DETALHE QUE QUEBRA TUDO SE ERRAR: salt=None na lib `cryptography` == HashLen (32)
 * bytes ZERO, NÃO um salt vazio. Por isso o default aqui é 32 zeros (não ByteArray(0)).
 */
object Hkdf {
    private const val HASH_LEN = 32 // saída do SHA-256
    val INFO_COFRE: ByteArray = "ekodide-cofre-aes256gcm-v1".toByteArray(Charsets.UTF_8)

    fun deriveKey(
        ikm: ByteArray,
        info: ByteArray = INFO_COFRE,
        length: Int = 32,
        salt: ByteArray? = null,
    ): ByteArray {
        val effSalt = salt ?: ByteArray(HASH_LEN)   // salt=None -> 32 bytes zero
        val prk = hmac(effSalt, ikm)                // extract: PRK = HMAC(salt, IKM)
        return expand(prk, info, length)
    }

    /** expand: T(n)=HMAC(PRK, T(n-1) || info || n); OKM = primeiros `length` bytes. */
    private fun expand(prk: ByteArray, info: ByteArray, length: Int): ByteArray {
        require(length <= 255 * HASH_LEN) { "length grande demais pro HKDF" }
        val out = ByteArray(length)
        var t = ByteArray(0)
        var pos = 0
        var counter = 1
        while (pos < length) {
            val mac = newMac(prk)
            mac.update(t)
            mac.update(info)
            mac.update(byteArrayOf(counter.toByte())) // 0x01, 0x02, ...
            t = mac.doFinal()
            val n = minOf(t.size, length - pos)
            System.arraycopy(t, 0, out, pos, n)
            pos += n
            counter++
        }
        return out
    }

    private fun hmac(key: ByteArray, data: ByteArray): ByteArray = newMac(key).doFinal(data)

    private fun newMac(key: ByteArray): Mac {
        // SecretKeySpec recusa chave de COMPRIMENTO zero; 32 bytes zero é não-vazio, ok.
        val mac = Mac.getInstance("HmacSHA256")
        mac.init(SecretKeySpec(key, "HmacSHA256"))
        return mac
    }
}
