package com.ekodide.android

import android.app.Activity
import androidx.camera.core.CameraSelector
import androidx.camera.core.ImageAnalysis
import androidx.camera.core.ImageProxy
import androidx.camera.core.Preview
import androidx.camera.lifecycle.ProcessCameraProvider
import androidx.camera.view.PreviewView
import androidx.lifecycle.Lifecycle
import androidx.lifecycle.LifecycleOwner
import androidx.lifecycle.LifecycleRegistry
import com.google.zxing.BarcodeFormat
import com.google.zxing.BinaryBitmap
import com.google.zxing.DecodeHintType
import com.google.zxing.MultiFormatReader
import com.google.zxing.PlanarYUVLuminanceSource
import com.google.zxing.ReaderException
import com.google.zxing.common.HybridBinarizer
import java.util.concurrent.Executors

/**
 * O olho do pareamento: câmera (CameraX) + decodificador (ZXing core). Cada QR achado
 * desagua em [aoLer] na thread principal; o callback devolve `true` pra encerrar
 * (código adotado) ou `false` pra seguir escaneando (era um QR alheio — a pessoa
 * ainda vai mirar no certo).
 *
 * Tem vida própria (LifecycleOwner manual): liga com a tela de escanear e morre com
 * ela — o CameraX solta a câmera sozinho quando o lifecycle vai a DESTROYED. É o que
 * permite continuar com a Activity CRUA da casa (sem ComponentActivity/appcompat).
 */
class Escaneio(
    private val activity: Activity,
    private val aoLer: (String) -> Boolean,
) : LifecycleOwner {

    private val registry = LifecycleRegistry(this).apply {
        currentState = Lifecycle.State.CREATED
    }
    override val lifecycle: Lifecycle get() = registry

    // Uma thread só pra análise: um frame decodificado por vez, os demais caem
    // (KEEP_ONLY_LATEST) — QR de tela não precisa de mais.
    private val analista = Executors.newSingleThreadExecutor()

    private val leitor = MultiFormatReader().apply {
        setHints(mapOf(DecodeHintType.POSSIBLE_FORMATS to listOf(BarcodeFormat.QR_CODE)))
    }

    // Pausa a análise enquanto a thread principal decide o destino do QR lido.
    @Volatile private var pausado = false

    /** Liga a câmera traseira despejando o preview em [tela] e os frames no analista. */
    fun ligar(tela: PreviewView) {
        registry.currentState = Lifecycle.State.RESUMED
        val futuro = ProcessCameraProvider.getInstance(activity)
        futuro.addListener({
            // A pessoa pode ter voltado antes de a câmera abrir: não amarra em defunto.
            if (registry.currentState == Lifecycle.State.DESTROYED) return@addListener
            val provider = futuro.get()
            val preview = Preview.Builder().build().also {
                it.setSurfaceProvider(tela.surfaceProvider)
            }
            val analise = ImageAnalysis.Builder()
                .setBackpressureStrategy(ImageAnalysis.STRATEGY_KEEP_ONLY_LATEST)
                .build()
                .also { it.setAnalyzer(analista, ::decodificar) }
            provider.unbindAll()
            provider.bindToLifecycle(this, CameraSelector.DEFAULT_BACK_CAMERA, preview, analise)
        }, activity.mainExecutor)
    }

    /** Desliga tudo (idempotente): o lifecycle morre e o CameraX recolhe a câmera. */
    fun parar() {
        if (registry.currentState != Lifecycle.State.INITIALIZED) {
            registry.currentState = Lifecycle.State.DESTROYED
        }
        analista.shutdown()
    }

    /** Um frame YUV -> luminância (plano Y) -> ZXing. Tenta também INVERTIDO: o QR
     *  desenhado num terminal escuro vem com claro/escuro trocados. */
    private fun decodificar(img: ImageProxy) {
        img.use {
            if (pausado) return
            val plano = it.planes[0] // Y: luminância pura, pixelStride 1 garantido
            val dados = ByteArray(plano.buffer.remaining()).also { b -> plano.buffer.get(b) }
            val fonte = PlanarYUVLuminanceSource(
                dados, plano.rowStride, it.height, 0, 0, it.width, it.height, false,
            )
            val texto = tentar(BinaryBitmap(HybridBinarizer(fonte)))
                ?: tentar(BinaryBitmap(HybridBinarizer(fonte.invert())))
            if (texto != null) {
                pausado = true
                activity.runOnUiThread {
                    if (!aoLer(texto)) pausado = false // QR alheio: segue escaneando
                }
            }
        }
    }

    private fun tentar(bitmap: BinaryBitmap): String? = try {
        leitor.decodeWithState(bitmap).text
    } catch (_: ReaderException) {
        null // não tinha QR legível neste frame — vem outro já já
    } finally {
        leitor.reset()
    }
}
