package com.ekodide.android.ui

import android.content.Context
import android.content.res.ColorStateList
import android.graphics.Typeface
import android.graphics.drawable.GradientDrawable
import android.graphics.drawable.RippleDrawable
import android.util.TypedValue
import android.view.Gravity
import android.view.View
import android.view.ViewGroup.LayoutParams.MATCH_PARENT
import android.view.ViewGroup.LayoutParams.WRAP_CONTENT
import android.widget.ImageView
import android.widget.LinearLayout
import android.widget.TextView
import com.ekodide.android.R

/**
 * Design system do Ekodide — "sentinela / console cifrado". Tudo programático (sem
 * Material Components): hairlines precisas, rótulos em monospace caixa-alta com tracking,
 * e o creme (#E6DBC6, a máscara do papagaio) como único sinal quente sobre os cinzas.
 *
 * Centraliza paleta, tipografia e os blocos de UI pra as telas ficarem coerentes.
 */
object Estilo {
    // Paleta (espelha res/values/colors.xml).
    const val TINTA = 0xFF1D1D1C.toInt()   // fundo
    const val PAINEL = 0xFF444544.toInt()  // bordas / superfície
    const val TRACO = 0xFF6B6D6B.toInt()   // terciário
    const val NEVOA = 0xFFA29F98.toInt()   // texto secundário
    const val MASK = 0xFFE6DBC6.toInt()    // accent
    private const val SUPERFICIE = 0xFF242423.toInt() // leve elevação p/ o selo

    private val LIGHT: Typeface get() = Typeface.create("sans-serif-light", Typeface.NORMAL)
    private val MEDIUM: Typeface get() = Typeface.create("sans-serif-medium", Typeface.NORMAL)
    private val MONO: Typeface = Typeface.MONOSPACE

    fun dp(c: Context, v: Float): Int = (v * c.resources.displayMetrics.density).toInt()

    private fun TextView.sp(v: Float) = setTextSize(TypedValue.COMPLEX_UNIT_SP, v)

    private fun arredondado(c: Context, fill: Int?, borda: Int?, raio: Float, larg: Float = 1f) =
        GradientDrawable().apply {
            shape = GradientDrawable.RECTANGLE
            cornerRadius = dp(c, raio).toFloat()
            fill?.let { setColor(it) }
            borda?.let { setStroke(dp(c, larg), it) }
        }

    private fun comRipple(c: Context, base: GradientDrawable, cor: Int): RippleDrawable =
        RippleDrawable(ColorStateList.valueOf(cor), base, base)

    // ---------- texto ----------

    /** Rótulo-eyebrow: monospace, caixa-alta, tracking — a "voz" do painel. */
    fun eyebrow(c: Context, texto: String, cor: Int = TRACO): TextView = TextView(c).apply {
        text = texto.uppercase()
        typeface = MONO
        sp(11f)
        setTextColor(cor)
        letterSpacing = 0.22f
    }

    /** Título display: leve e arejado. */
    fun titulo(c: Context, texto: String): TextView = TextView(c).apply {
        text = texto
        typeface = LIGHT
        sp(30f)
        setTextColor(MASK)
        letterSpacing = 0.01f
        setLineSpacing(dp(c, 2f).toFloat(), 1f)
    }

    /** Corpo de texto, em névoa, com respiro entre linhas. */
    fun corpo(c: Context, texto: String): TextView = TextView(c).apply {
        text = texto
        typeface = Typeface.SANS_SERIF
        sp(15f)
        setTextColor(NEVOA)
        setLineSpacing(dp(c, 6f).toFloat(), 1f)
    }

    /** Valor técnico (endereço, caminho) em monospace creme. */
    fun valorMono(c: Context, texto: String): TextView = TextView(c).apply {
        text = texto
        typeface = MONO
        sp(15f)
        setTextColor(MASK)
        setTextIsSelectable(true)
    }

    // ---------- botões ----------

    fun botaoPrimario(c: Context, texto: String, onClick: () -> Unit): TextView =
        TextView(c).apply {
            text = texto
            typeface = MEDIUM
            sp(15f)
            setTextColor(TINTA)
            gravity = Gravity.CENTER
            isAllCaps = false
            setPadding(dp(c, 20f), dp(c, 15f), dp(c, 20f), dp(c, 15f))
            background = comRipple(c, arredondado(c, MASK, null, 12f), 0x33000000)
            isClickable = true
            setOnClickListener { onClick() }
            layoutParams = LinearLayout.LayoutParams(MATCH_PARENT, WRAP_CONTENT)
        }

    fun botaoFantasma(c: Context, texto: String, onClick: () -> Unit): TextView =
        TextView(c).apply {
            text = texto
            typeface = MEDIUM
            sp(15f)
            setTextColor(MASK)
            gravity = Gravity.CENTER
            setPadding(dp(c, 20f), dp(c, 14f), dp(c, 20f), dp(c, 14f))
            background = comRipple(c, arredondado(c, null, PAINEL, 12f, 1.2f), 0x22E6DBC6)
            isClickable = true
            setOnClickListener { onClick() }
            layoutParams = LinearLayout.LayoutParams(MATCH_PARENT, WRAP_CONTENT)
        }

    /** Botão-texto discreto (ex.: "Pular"). */
    fun botaoTexto(c: Context, texto: String, cor: Int = NEVOA, onClick: () -> Unit): TextView =
        TextView(c).apply {
            text = texto
            typeface = MEDIUM
            sp(14f)
            setTextColor(cor)
            gravity = Gravity.CENTER
            setPadding(dp(c, 16f), dp(c, 14f), dp(c, 16f), dp(c, 14f))
            background = comRipple(c, arredondado(c, null, null, 12f), 0x22FFFFFF)
            isClickable = true
            setOnClickListener { onClick() }
        }

    // ---------- containers ----------

    /** Raiz de tela: coluna vertical, fundo tinta, respiro nas bordas. */
    fun raiz(c: Context): LinearLayout = LinearLayout(c).apply {
        orientation = LinearLayout.VERTICAL
        setBackgroundColor(TINTA)
        setPadding(dp(c, 24f), dp(c, 28f), dp(c, 24f), dp(c, 28f))
    }

    /** Painel hairline (blueprint): borda fina, sem preenchimento. */
    fun painel(c: Context): LinearLayout = LinearLayout(c).apply {
        orientation = LinearLayout.VERTICAL
        background = arredondado(c, null, PAINEL, 14f, 1f)
        setPadding(dp(c, 18f), dp(c, 16f), dp(c, 18f), dp(c, 16f))
    }

    fun espaco(c: Context, altura: Float): View = View(c).apply {
        layoutParams = LinearLayout.LayoutParams(MATCH_PARENT, dp(c, altura))
    }

    fun margem(v: View, c: Context, topo: Float = 0f, baixo: Float = 0f) {
        val lp = (v.layoutParams as? LinearLayout.LayoutParams)
            ?: LinearLayout.LayoutParams(MATCH_PARENT, WRAP_CONTENT)
        lp.topMargin = dp(c, topo); lp.bottomMargin = dp(c, baixo)
        v.layoutParams = lp
    }

    // ---------- componentes ----------

    /** Cabeçalho: mascote redondo + wordmark + pill de status. */
    fun header(c: Context, statusAtivo: Boolean): LinearLayout = LinearLayout(c).apply {
        orientation = LinearLayout.HORIZONTAL
        gravity = Gravity.CENTER_VERTICAL
        val avatar = ImageView(c).apply {
            setImageResource(R.mipmap.ic_launcher_round)
            layoutParams = LinearLayout.LayoutParams(dp(c, 34f), dp(c, 34f))
        }
        val marca = TextView(c).apply {
            text = "EKODIDE"
            typeface = MEDIUM
            sp(16f)
            setTextColor(MASK)
            letterSpacing = 0.28f
            setPadding(dp(c, 12f), 0, 0, 0)
        }
        val mola = View(c).apply {
            layoutParams = LinearLayout.LayoutParams(0, 1, 1f)
        }
        addView(avatar)
        addView(marca)
        addView(mola)
        addView(pill(c, if (statusAtivo) "no ar" else "parado", statusAtivo))
    }

    /** Pill de status com bolinha. */
    fun pill(c: Context, texto: String, ativo: Boolean): LinearLayout = LinearLayout(c).apply {
        orientation = LinearLayout.HORIZONTAL
        gravity = Gravity.CENTER_VERTICAL
        background = arredondado(c, null, if (ativo) PAINEL else TRACO, 20f, 1f)
        setPadding(dp(c, 12f), dp(c, 6f), dp(c, 12f), dp(c, 6f))
        val ponto = View(c).apply {
            background = GradientDrawable().apply {
                shape = GradientDrawable.OVAL
                setColor(if (ativo) MASK else TRACO)
            }
            layoutParams = LinearLayout.LayoutParams(dp(c, 7f), dp(c, 7f))
        }
        val t = TextView(c).apply {
            text = texto.uppercase()
            typeface = MONO
            sp(10f)
            setTextColor(if (ativo) MASK else TRACO)
            letterSpacing = 0.18f
            setPadding(dp(c, 7f), 0, 0, 0)
        }
        addView(ponto)
        addView(t)
    }

    /** Barra de progresso segmentada (wizard): preenche em creme até o passo atual. */
    fun progresso(c: Context, atual: Int, total: Int): LinearLayout = LinearLayout(c).apply {
        orientation = LinearLayout.HORIZONTAL
        for (i in 0 until total) {
            val seg = View(c).apply {
                background = arredondado(c, if (i <= atual) MASK else PAINEL, null, 3f)
            }
            val lp = LinearLayout.LayoutParams(0, dp(c, 4f), 1f)
            if (i > 0) lp.leftMargin = dp(c, 6f)
            addView(seg, lp)
        }
    }

    /**
     * O SELO de pareamento — elemento-assinatura. Bloco emoldurado em creme com a frase
     * em monospace grande; toque copia. As palavras vêm separadas por "·".
     */
    fun selo(c: Context, frase: String, onCopiar: () -> Unit): LinearLayout = LinearLayout(c).apply {
        orientation = LinearLayout.VERTICAL
        background = arredondado(c, SUPERFICIE, MASK, 16f, 1.5f)
        setPadding(dp(c, 20f), dp(c, 18f), dp(c, 20f), dp(c, 18f))
        addView(eyebrow(c, "frase de pareamento", NEVOA))
        addView(TextView(c).apply {
            text = frase.replace("-", "  ·  ")
            typeface = MONO
            sp(20f)
            setTextColor(MASK)
            letterSpacing = 0.04f
            setLineSpacing(dp(c, 6f).toFloat(), 1f)
            setPadding(0, dp(c, 12f), 0, dp(c, 10f))
        })
        addView(TextView(c).apply {
            text = "Toque para copiar · digite igual no computador"
            typeface = Typeface.SANS_SERIF
            sp(12f)
            setTextColor(TRACO)
        })
        background = comRipple(c, arredondado(c, SUPERFICIE, MASK, 16f, 1.5f), 0x22E6DBC6)
        isClickable = true
        setOnClickListener { onCopiar() }
    }

    /** Linha de dado dentro de um painel: eyebrow + valor mono. */
    fun dado(c: Context, rotulo: String, valor: String): LinearLayout = painel(c).apply {
        addView(eyebrow(c, rotulo, NEVOA))
        addView(valorMono(c, valor).also { margem(it, c, topo = 6f) })
    }
}
