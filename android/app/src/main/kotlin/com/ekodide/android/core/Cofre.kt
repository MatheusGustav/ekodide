package com.ekodide.android.core

import java.security.SecureRandom
import javax.crypto.Cipher
import javax.crypto.spec.GCMParameterSpec
import javax.crypto.spec.SecretKeySpec

/**
 * O cofre: cifra o CONTEÚDO com AES-256-GCM, chave derivada do segredo via HKDF.
 * Espelho byte-idêntico do cofre.py.
 *
 * Formato na rede == Python: nonce(12) || ciphertext+tag(16 no fim). Sem AAD
 * (o Python passou None). O doFinal do Java já anexa a tag de 16 bytes no mesmo
 * lugar que a lib `cryptography`, então os bytes são intercambiáveis entre as pontas.
 */
object Cofre {
    private const val NONCE_LEN = 12   // AES-GCM: nonce de 96 bits (igual ao Python)
    private const val TAG_BITS = 128   // tag de 16 bytes
    private val rng = SecureRandom()

    private fun chave(segredo: String): ByteArray =
        Hkdf.deriveKey(segredo.toByteArray(Charsets.UTF_8))

    /** Embaralha `dados`. Sorteia um nonce novo a cada chamada (nunca repetir nonce). */
    fun cifrar(dados: ByteArray, segredo: String): ByteArray {
        val nonce = ByteArray(NONCE_LEN).also { rng.nextBytes(it) }
        val cipher = Cipher.getInstance("AES/GCM/NoPadding")
        cipher.init(
            Cipher.ENCRYPT_MODE,
            SecretKeySpec(chave(segredo), "AES"),
            GCMParameterSpec(TAG_BITS, nonce),
        )
        return nonce + cipher.doFinal(dados) // doFinal já traz ct||tag
    }

    /** Desembaralha o que `cifrar` (ou o cofre.py) produziu. Lança em chave errada/adulteração. */
    fun decifrar(blob: ByteArray, segredo: String): ByteArray {
        require(blob.size >= NONCE_LEN + 16) { "blob curto demais" }
        val nonce = blob.copyOfRange(0, NONCE_LEN)
        val ctTag = blob.copyOfRange(NONCE_LEN, blob.size)
        val cipher = Cipher.getInstance("AES/GCM/NoPadding")
        cipher.init(
            Cipher.DECRYPT_MODE,
            SecretKeySpec(chave(segredo), "AES"),
            GCMParameterSpec(TAG_BITS, nonce),
        )
        return cipher.doFinal(ctTag) // lança AEADBadTagException em adulteração/chave errada
    }
}
