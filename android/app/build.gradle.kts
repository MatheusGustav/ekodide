plugins {
    // AGP 9+ tem Kotlin embutido — NÃO se aplica mais o plugin kotlin.android
    // (ver android/README e https://developer.android.com/build/migrate-to-built-in-kotlin).
    alias(libs.plugins.android.application)
}

android {
    namespace = "com.ekodide.android"
    compileSdk = 36

    defaultConfig {
        applicationId = "com.ekodide.android"
        minSdk = 29
        targetSdk = 36
        versionCode = 1
        versionName = "0.1.0"

        testInstrumentationRunner = "androidx.test.runner.AndroidJUnitRunner"
    }

    signingConfigs {
        // Chave de debug FIXA, commitada no repo (credenciais-padrão de debug, públicas).
        // Sem isto, cada build do CI assina com um keystore novo (runner descartável) e o
        // APK não atualiza por cima do anterior (INSTALL_FAILED_UPDATE_INCOMPATIBLE). É só
        // debug/sideload — NÃO serve pra release/Play.
        getByName("debug") {
            storeFile = file("debug.keystore")
            storePassword = "android"
            keyAlias = "androiddebugkey"
            keyPassword = "android"
        }
    }

    buildTypes {
        release {
            // Sem ofuscação por ora (a cifra usa javax.crypto, sem reflexão frágil).
            isMinifyEnabled = false
            proguardFiles(
                getDefaultProguardFile("proguard-android-optimize.txt"),
                "proguard-rules.pro"
            )
        }
    }

    compileOptions {
        sourceCompatibility = JavaVersion.VERSION_17
        targetCompatibility = JavaVersion.VERSION_17
    }
    // O jvmTarget do Kotlin herda o targetCompatibility acima (17) no Kotlin embutido.
}

dependencies {
    // Núcleo de cifra é Kotlin puro + javax.crypto: zero dependência de runtime.

    // Testes JVM (rodam sem aparelho): provam o byte-idêntico contra os vetores-ouro.
    testImplementation(libs.junit)

    // Testes instrumentados (rodam no emulador): provam a cifra no runtime real do Android.
    androidTestImplementation(libs.androidx.test.ext.junit)
    androidTestImplementation(libs.androidx.test.runner)
}
