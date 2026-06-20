// Arquivo de build raiz: declara os plugins, mas só os aplica no módulo :app.
plugins {
    alias(libs.plugins.android.application) apply false
    alias(libs.plugins.kotlin.android) apply false
}
