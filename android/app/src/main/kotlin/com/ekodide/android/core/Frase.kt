package com.ekodide.android.core

import java.security.SecureRandom

/**
 * A frase-código: um segredo forte que dá pra DIGITAR. Espelho do frase.py.
 *
 * O segredo dos dois lados tem que ser o MESMO. Em vez de copiar uma chave aleatória
 * ("9f3a..."), geramos o segredo como uma FRASE de palavras simples
 * ('casa-vento-rio-azul-pedra-lobo'): forte o bastante e fácil de ditar/digitar.
 *
 * A frase *é* o segredo (a chave do HMAC). Ela NUNCA cruza a rede — vai de um aparelho
 * ao outro pela boca/tela (um lê, o outro digita). É o "out-of-band" do pareamento. Por
 * isso aqui NÃO se normaliza nada: a frase é usada byte-a-byte como veio; mexer (caixa,
 * espaços) divergiria do outro lado e quebraria o lacre.
 */
object Frase {

    // Lista de palavras curtas, sem acento (fáceis de ditar/digitar). IDÊNTICA ao
    // frase.py: 164 palavras (~7,4 bits cada); 6 palavras dão ~44 bits — folgado pra
    // parear numa LAN (o lacre ainda tem janela de 5 min + HMAC).
    val PALAVRAS: List<String> = listOf(
        "abelha", "agua", "anel", "areia", "arroz", "arvore", "asa", "aviao",
        "bambu", "banana", "barco", "bicho", "bola", "bolo", "boto", "brisa",
        "cabra", "cacto", "caju", "carro", "casa", "cavalo", "chave", "chuva",
        "cobra", "copo", "corda", "couro", "dado", "dedo", "dente", "disco",
        "doce", "dragao", "duna", "elefante", "erva", "escada", "espelho", "estrela",
        "faca", "farol", "festa", "flor", "fogo", "folha", "forte", "fruta",
        "galho", "ganso", "gato", "gelo", "gema", "gota", "grama", "gruta",
        "harpa", "haste", "hera", "hino", "horta", "iate", "iglu", "ilha",
        "indio", "ipe", "isca", "jacare", "janela", "jardim", "jarro", "jiboia",
        "jogo", "joia", "juba", "lago", "lama", "leao", "leite", "lenha",
        "livro", "lobo", "lua", "mar", "mato", "mel", "mesa", "milho",
        "moeda", "monte", "mundo", "nabo", "navio", "nervo", "neve", "ninho",
        "noite", "norte", "nuvem", "oasis", "olho", "ombro", "onca", "onda",
        "ostra", "ouro", "ovo", "pao", "pato", "pedra", "peixe", "pena",
        "pinha", "ponte", "porta", "quadra", "quati", "queijo", "quilo", "quintal",
        "raiz", "rato", "rede", "rio", "rocha", "roda", "rosa", "rumo",
        "sapo", "selva", "serra", "sino", "sol", "sopa", "suco", "sul",
        "tatu", "teia", "telha", "terra", "tigre", "torre", "trem", "trilha",
        "uniao", "unha", "urna", "ursa", "urso", "urubu", "uva", "uivo",
        "vaca", "vale", "vela", "vento", "verao", "vidro", "vinho", "voo",
        "zebra", "zinco", "zona", "ziper",
    )

    // CSPRNG (igual ao secrets do Python): sorteio forte, não previsível.
    private val rng = SecureRandom()

    /** Sorteia uma frase-código forte (segredo pronto pra usar nos dois lados). */
    fun gerar(palavras: Int = 6, separador: String = "-"): String {
        require(palavras >= 4) {
            "uma frase fraca demais não pareia com segurança; use >= 4 palavras"
        }
        return (0 until palavras).joinToString(separador) { PALAVRAS[rng.nextInt(PALAVRAS.size)] }
    }
}
