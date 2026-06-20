package com.ekodide.android.core

import org.junit.Assert.assertEquals
import org.junit.Test

/**
 * Vetores oficiais do RFC 5869 (Apêndice A) pra SHA-256. Provam que nosso HKDF
 * hand-roll segue o padrão à risca — independente do Python.
 *
 * Usamos A.1 e A.2 (salt não-vazio). A.3 usa salt de comprimento ZERO, que o
 * SecretKeySpec do Java recusa (chave vazia); o caso salt=None do projeto (= 32
 * bytes zero, diferente de vazio) já é coberto pelo vetor-ouro em CryptoVectorsTest.
 */
class HkdfRfcTest {

    @Test
    fun rfc5869_a1_sha256() {
        val ikm = "0b".repeat(22).hexToBytes()
        val salt = "000102030405060708090a0b0c".hexToBytes()
        val info = "f0f1f2f3f4f5f6f7f8f9".hexToBytes()
        val okm = Hkdf.deriveKey(ikm, info, length = 42, salt = salt)
        assertEquals(
            "3cb25f25faacd57a90434f64d0362f2a" +
                "2d2d0a90cf1a5a4c5db02d56ecc4c5bf" +
                "34007208d5b887185865",
            okm.toHex(),
        )
    }

    @Test
    fun rfc5869_a2_sha256() {
        val ikm = (0..0x4f).joinToString("") { "%02x".format(it) }.hexToBytes()
        val salt = (0x60..0xaf).joinToString("") { "%02x".format(it) }.hexToBytes()
        val info = (0xb0..0xff).joinToString("") { "%02x".format(it) }.hexToBytes()
        val okm = Hkdf.deriveKey(ikm, info, length = 82, salt = salt)
        assertEquals(
            "b11e398dc80327a1c8e7f78c596a4934" +
                "4f012eda2d4efad8a050cc4c19afa97c" +
                "59045a99cac7827271cb41c65e590e09" +
                "da3275600c2f09b8367793a9aca3db71" +
                "cc30c58179ec3e87c14c01d5c1f3434f" +
                "1d87",
            okm.toHex(),
        )
    }

    private fun ByteArray.toHex(): String =
        joinToString("") { "%02x".format(it.toInt() and 0xFF) }

    private fun String.hexToBytes(): ByteArray =
        chunked(2).map { it.toInt(16).toByte() }.toByteArray()
}
