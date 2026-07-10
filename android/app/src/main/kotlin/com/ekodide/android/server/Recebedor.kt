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
     * em produção fica null (= relógio atual). `compartilhar` é a fonte que o admin pode
     * PUXAR (rotas /listar e /buscar) — null (padrão) = nada exposto: o "puxar" é opt-in,
     * nada vaza sem o app apontar uma pasta. `aberto` é a navegação por pastas (campo
     * `pasta` no /listar e /buscar) — null = pedido com `pasta` é recusado (403).
     */
    fun tratar(
        rota: String,
        corpo: ByteArray,
        segredo: String,
        base: File,
        agora: Long? = null,
        compartilhar: FonteCompartilhada? = null,
        aberto: FonteAberta? = null,
    ): Resposta {
        val carga = try {
            Lacre.desempacotar(corpo, segredo, agora)
        } catch (e: TrancaInvalida) {
            return texto(401, "recusado pela tranca: ${e.message}")
        }
        return when (rota) {
            "/receber" -> receber(carga, segredo, base)
            "/progresso" -> progresso(carga, segredo, base)
            "/listar" -> listar(carga, segredo, compartilhar, aberto)
            "/buscar" -> buscar(carga, segredo, compartilhar, aberto)
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

    /**
     * Diz o que dá pra PUXAR daqui. Sem `pasta` na carga: a lista (recursiva) da pasta
     * compartilhada, como sempre. Com `pasta`: a vista RASA daquela pasta via [FonteAberta]
     * (itens + subpastas) — recusada se a navegação não está liberada. O lacre já foi
     * exigido em `tratar` — só responde a quem tem o segredo.
     */
    private fun listar(
        carga: Map<String, Any?>,
        segredo: String,
        compartilhar: FonteCompartilhada?,
        aberto: FonteAberta?,
    ): Resposta {
        val pasta = carga["pasta"] as? String
        if (pasta != null) {
            if (aberto == null) return texto(403, SEM_NAVEGACAO)
            val vista = try {
                aberto.listar(pasta)
            } catch (e: Exception) {
                return texto(400, "pedido inválido: ${e.message}")
            }
            return selar(
                mapOf(
                    "itens" to vista.itens.map { mapOf("nome" to it.nome, "tamanho" to it.tamanho) },
                    "pastas" to vista.pastas,
                ),
                segredo,
            )
        }
        val itens = (compartilhar?.listar() ?: emptyList()).map {
            mapOf("nome" to it.nome, "tamanho" to it.tamanho)
        }
        return selar(mapOf("itens" to itens), segredo)
    }

    /**
     * Entrega UM pedaço de um arquivo da pasta compartilhada, CIFRADO (cofre) — na rede
     * passa só embaralhado, como no /receber. Recusa se nada é compartilhado ou se o nome
     * tentar escapar da pasta.
     */
    private fun buscar(
        carga: Map<String, Any?>,
        segredo: String,
        compartilhar: FonteCompartilhada?,
        aberto: FonteAberta?,
    ): Resposta {
        val pasta = carga["pasta"] as? String
        if (pasta == null && compartilhar == null) {
            return texto(403, "este aparelho não compartilha nada (sirva com --compartilhar)")
        }
        if (pasta != null && aberto == null) return texto(403, SEM_NAVEGACAO)
        val nome = carga["nome"] as? String ?: return texto(400, "pedido inválido: nome")
        val parte = (carga["parte"] as? Long)?.toInt() ?: return texto(400, "pedido inválido: parte")
        val partes = (carga["partes"] as? Long)?.toInt() ?: return texto(400, "pedido inválido: partes")
        val bruto = try {
            if (pasta != null) aberto!!.lerPedaco(pasta, nome, parte, partes)
            else compartilhar!!.lerPedaco(nome, parte, partes)
        } catch (e: Exception) {
            return texto(400, "pedido inválido: ${e.message}")
        }
        // CIFRA antes de mandar: na rede passa só o cofre, igual ao /receber.
        val cifrado = Base64.getEncoder().encodeToString(Cofre.cifrar(bruto, segredo))
        return selar(
            mapOf(
                "nome" to nome,
                "parte" to parte.toLong(),
                "partes" to partes.toLong(),
                "conteudo" to cifrado,
            ),
            segredo,
        )
    }

    private const val SEM_NAVEGACAO =
        "esta ponta não navega por pastas (no celular, conceda 'Acesso a todos os arquivos' no app)"

    private fun selar(dados: Map<String, Any?>, segredo: String): Resposta =
        Resposta(200, Lacre.empacotar(dados, segredo))

    private fun texto(codigo: Int, msg: String): Resposta =
        Resposta(codigo, msg.toByteArray(Charsets.UTF_8), "text/plain; charset=utf-8")
}
