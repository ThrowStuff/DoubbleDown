plugins { id("com.android.application") }
android {
    namespace = "org.openhearing.app"
    compileSdk = 35
    defaultConfig {
        applicationId = "org.openhearing.app"
        minSdk = 26
        targetSdk = 35
        versionCode = 1
        versionName = "0.1.0-dev"
    }
    compileOptions {
        sourceCompatibility = JavaVersion.VERSION_17
        targetCompatibility = JavaVersion.VERSION_17
    }
}
