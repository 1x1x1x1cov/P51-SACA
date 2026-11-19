plugins {
    alias(libs.plugins.android.application)
}

android {
    namespace = "au.edu.swin.saca"
    compileSdk {
        version = release(37)
    }

    defaultConfig {
        applicationId = "au.edu.swin.saca"
        minSdk = 26
        targetSdk = 37
        versionCode = 1
        versionName = "1.0"
    }

    buildTypes {
        release {
            optimization {
                enable = false
            }
            // Signed with the debug key so "Build APK" gives an APK you can install straight away.
            signingConfig = signingConfigs.getByName("debug")
        }
    }
    compileOptions {
        sourceCompatibility = JavaVersion.VERSION_11
        targetCompatibility = JavaVersion.VERSION_11
    }
    androidResources {
        // Python (WebAssembly) and the app bundle are read as they are, not unpacked from a compressed APK entry.
        noCompress += listOf("wasm", "zip")
    }
}
