package com.ekodide.android.server

import com.ekodide.android.core.CaixaPostal
import com.ekodide.android.core.Cofre
import com.ekodide.android.core.Lacre
import com.ekodide.android.core.TrancaInvalida
import java.io.File
import java.util.Base64

/**
 * O núcleo do recebedor: dada uma ROTA e o CORPO já lido, confere o lacre, decifra o
 * cofre e grava com a caixa postal. Espelho de recebedor.py, mas SEM sockets — essa
 * separação deixa a lógica testável no JVM (a casca HTTP/socket que chama isto entra
 * em ServidorHttp, coberta por teste no emulador e no PC↔celular).
 */
object Recebedor {
    const val PORTA = 8778

    data class Resposta(
        val status: Int,
        val corpo: ByteArray,
        val contentType: String = "application/json",
    )

    /**
     * Trata uma requisição. `agora` (epoch s) só pra teste fixar o relógio do lacre;
     * em produção fica null (= relógio atual).
     */
    fun tratar(
        rota: String,
        corpo: ByteArray,
        segredo: String,
        base: File,
        agora: Long? = null,
    ): Resposta {
        val carga = try {
            Lacre.desempacotar(corpo, segredo, agora)
        } catch (e: TrancaInvalida) {
            return texto(401, "recusado pela tranca: ${e.message}")
        }
        return when (rota) {
            "/receber" -> receber(carga, segredo, base)
            "/progresso" -> progresso(carga, segredo, base)
            else -> texto(404, "rota desconhecida")
        }
    }

    private fun receber(carga: Map<String, Any?>, segredo: String, base: File): Resposta {
        val conteudoB64 = carga["conteudo"] as? String
            ?: return texto(400, "envio sem conteúdo")
        // DECIFRA o cofre — na rede veio embaralhado. A caixa postal só vê texto-claro.
        val aberto = try {
            Cofre.decifrar(Base64.getDecoder().decode(conteudoB64), segredo)
        } catch (e: Exception) {
            return texto(400, "conteúdo não abriu o cofre: ${e.message}")
        }
        val nome = carga["nome"] as? String ?: return texto(400, "envio sem nome")
        val alvo: File? = try {
            if (carga.containsKey("partes")) {
                val parte = (carga["parte"] as? Long)?.toInt() ?: -1
                val partes = (carga["partes"] as? Long)?.toInt() ?: 0
                val tamanho = (carga["tamanho"] as? Long) ?: -1L
                if (partes < 1 || parte < 0 || parte >= partes) {
                    return texto(400, "índice de pedaço inválido")
                }
                CaixaPostal.guardarPedaco(nome, aberto, parte, partes, base, tamanho)
            } else {
                CaixaPostal.guardar(nome, aberto, base)
            }
        } catch (e: Exception) {
            return texto(400, "envio inválido: ${e.message}")
        }
        return selar(mapOf("ok" to true, "destino" to (alvo?.path ?: "")), segredo)
    }

    private fun progresso(carga: Map<String, Any?>, segredo: String, base: File): Resposta {
        val nome = carga["nome"] as? String ?: return texto(400, "consulta inválida")
        val partes = (carga["partes"] as? Long)?.toInt()
            ?: return texto(400, "consulta inválida")
        val tamanho = (carga["tamanho"] as? Long) ?: -1L
        val recebidos = CaixaPostal.progressoDe(nome, partes, base, tamanho)
        return selar(mapOf("recebidos" to recebidos.toLong()), segredo)
    }

    private fun selar(dados: Map<String, Any?>, segredo: String): Resposta =
        Resposta(200, Lacre.empacotar(dados, segredo))

    private fun texto(codigo: Int, msg: String): Resposta =
        Resposta(codigo, msg.toByteArray(Charsets.UTF_8), "text/plain; charset=utf-8")
}
