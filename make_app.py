import os

files = {
    "settings.gradle.kts": """pluginManagement {
    repositories { google(); mavenCentral(); gradlePluginPortal() }
}
dependencyResolutionManagement {
    repositoriesMode.set(RepositoriesMode.FAIL_ON_PROJECT_REPOS)
    repositories { google(); mavenCentral() }
}
rootProject.name = "ALL AI"
include(":app")""",

    "build.gradle.kts": """plugins {
    id("com.android.application") version "8.7.3" apply false
    id("org.jetbrains.kotlin.android") version "2.1.0" apply false
    id("org.jetbrains.kotlin.plugin.compose") version "2.1.0" apply false
    id("com.google.devtools.ksp") version "2.1.0-1.0.29" apply false
}""",

    "gradle.properties": """org.gradle.jvmargs=-Xmx2048m -Dfile.encoding=UTF-8
android.useAndroidX=true
kotlin.code.style=official
android.nonTransitiveRClass=true""",

    "app/build.gradle.kts": """plugins {
    id("com.android.application")
    id("org.jetbrains.kotlin.android")
    id("org.jetbrains.kotlin.plugin.compose")
    id("com.google.devtools.ksp")
}
android {
    namespace = "com.allai.app"
    compileSdk = 35
    defaultConfig {
        applicationId = "com.allai.app"
        minSdk = 29
        targetSdk = 35
        versionCode = 1
        versionName = "1.0.0"
    }
    compileOptions {
        sourceCompatibility = JavaVersion.VERSION_17
        targetCompatibility = JavaVersion.VERSION_17
    }
    kotlinOptions { jvmTarget = "17" }
    buildFeatures { compose = true }
}
dependencies {
    val composeBom = platform("androidx.compose:compose-bom:2025.02.00")
    implementation(composeBom)
    implementation("androidx.compose.ui:ui")
    implementation("androidx.compose.material3:material3")
    implementation("androidx.compose.material:material-icons-extended")
    implementation("androidx.navigation:navigation-compose:2.8.7")
    implementation("androidx.activity:activity-compose:1.10.0")
    implementation("com.squareup.okhttp3:okhttp:4.12.0")
    implementation("org.jetbrains.kotlinx:kotlinx-coroutines-android:1.9.0")
    implementation("androidx.security:security-crypto:1.1.0-alpha06")
    implementation("androidx.room:room-runtime:2.6.1")
    implementation("androidx.room:room-ktx:2.6.1")
    ksp("androidx.room:room-compiler:2.6.1")
    implementation("io.coil-kt:coil-compose:2.7.0")
}""",

    "app/src/main/AndroidManifest.xml": """<?xml version="1.0" encoding="utf-8"?>
<manifest xmlns:android="http://android.com">
    <uses-permission android:name="android.permission.INTERNET" />
    <uses-permission android:name="android.permission.RECORD_AUDIO" />
    <application
        android:name=".AllAiApplication"
        android:allowBackup="false"
        android:usesCleartextTraffic="true"
        android:label="ALL AI"
        android:supportsRtl="true"
        android:theme="@android:style/Theme.Material.NoActionBar">
        <activity
            android:name=".MainActivity"
            android:exported="true"
            android:windowSoftInputMode="adjustResize">
            <intent-filter>
                <action android:name="android.intent.action.MAIN" />
                <category android:name="android.intent.category.LAUNCHER" />
            </intent-filter>
        </activity>
    </application>
</manifest>""",

    "app/src/main/java/com/allai/app/core/security/SecureKeyStorage.kt": """package com.allai.app.core.security
import android.content.Context
import androidx.security.crypto.EncryptedSharedPreferences
import androidx.security.crypto.MasterKey

class SecureKeyStorage(context: Context) {
    private val masterKey = MasterKey.Builder(context).setKeyScheme(MasterKey.KeyScheme.AES256_GCM).build()
    private val prefs = EncryptedSharedPreferences.create(
        context, "all_ai_vault", masterKey,
        EncryptedSharedPreferences.PrefKeyEncryptionScheme.AES256_SIV,
        EncryptedSharedPreferences.PrefValueEncryptionScheme.AES256_GCM
    )
    fun saveApiKey(id: String, key: String) = prefs.edit().putString("k_$id", key.trim()).apply()
    fun getApiKey(id: String): String? = prefs.getString("k_$id", null)?.takeIf { it.isNotBlank() }
    fun saveOllamaUrl(url: String) = prefs.edit().putString("ollama", url.trim().removeSuffix("/")).apply()
    fun getOllamaUrl(): String = prefs.getString("ollama", "http://192.168.1.100:11434") ?: "http://192.168.1.100:11434"
}""",

    "app/src/main/java/com/allai/app/domain/model/AiModels.kt": """package com.allai.app.domain.model
enum class PricingTier(val label: String) {
    FREE_TIER("Бесплатный тариф (с лимитами)"),
    LOCAL_SERVER("Бесплатно (Локальный сервер)"),
    DEMO("Встроенный деморежим")
}
data class AiModelInfo(
    val id: String, val providerId: String, val displayName: String,
    val description: String, val pricingTier: PricingTier, val limits: String
)
data class ChatMessage(val role: String, val content: String, val modelUsed: String? = null)
sealed class AiResult<out T> {
    data class Success<T>(val data: T, val usedModel: String) : AiResult<T>()
    data class Error(val reason: String) : AiResult<Nothing>()
}""",

    "app/src/main/java/com/allai/app/data/provider/Providers.kt": """package com.allai.app.data.provider
import com.allai.app.core.security.SecureKeyStorage
import com.allai.app.domain.model.*
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.withContext
import okhttp3.MediaType.Companion.toMediaType
import okhttp3.OkHttpClient
import okhttp3.Request
import okhttp3.RequestBody.Companion.toRequestBody
import org.json.JSONArray
import org.json.JSONObject
import java.net.URLEncoder

interface AiProviderAdapter {
    val providerId: String
    suspend fun isAvailable(): Boolean
    suspend fun generateText(modelId: String, messages: List<ChatMessage>, systemPrompt: String? = null): AiResult<String>
}

class GeminiAdapter(private val client: OkHttpClient, private val keys: SecureKeyStorage) : AiProviderAdapter {
    override val providerId = "gemini"
    override suspend fun isAvailable() = keys.getApiKey(providerId) != null
    override suspend fun generateText(modelId: String, messages: List<ChatMessage>, systemPrompt: String?): AiResult<String> = withContext(Dispatchers.IO) {
        val key = keys.getApiKey(providerId) ?: return@withContext AiResult.Error("Нет ключа Gemini")
        try {
            val contents = JSONArray()
            messages.forEach {
                val role = if (it.role == "assistant") "model" else "user"
                contents.put(JSONObject().put("role", role).put("parts", JSONArray().put(JSONObject().put("text", it.content))))
            }
            val payload = JSONObject().put("contents", contents)
            if (!systemPrompt.isNullOrBlank()) {
                payload.put("systemInstruction", JSONObject().put("parts", JSONArray().put(JSONObject().put("text", systemPrompt))))
            }
            val req = Request.Builder()
                .url("https://googleapis.com")
                .post(payload.toString().toRequestBody("application/json".toMediaType())).build()
            client.newCall(req).execute().use { res ->
                val body = res.body?.string().orEmpty()
                if (!res.isSuccessful) return@withContext AiResult.Error("Gemini ${res.code}: $body")
                val text = JSONObject(body).getJSONArray("candidates").getJSONObject(0).getJSONObject("content").getJSONArray("parts").getJSONObject(0).getString("text")
                AiResult.Success(text, modelId)
            }
        } catch (e: Exception) { AiResult.Error("Ошибка Gemini: ${e.message}") }
    }
}

class OpenAiCompatAdapter(
    override val providerId: String, private val baseUrl: () -> String,
    private val needKey: Boolean, private val client: OkHttpClient, private val keys: SecureKeyStorage
) : AiProviderAdapter {
    override suspend fun isAvailable() = !needKey || keys.getApiKey(providerId) != null
    override suspend fun generateText(modelId: String, messages: List<ChatMessage>, systemPrompt: String?): AiResult<String> = withContext(Dispatchers.IO) {
        val key = keys.getApiKey(providerId)
        if (needKey && key == null) return@withContext AiResult.Error("Нет ключа $providerId")
        try {
            val arr = JSONArray()
            if (!systemPrompt.isNullOrBlank()) arr.put(JSONObject().put("role", "system").put("content", systemPrompt))
            messages.forEach { arr.put(JSONObject().put("role", it.role).put("content", it.content)) }
            val body = JSONObject().put("model", modelId).put("messages", arr)
            val rb = Request.Builder().url("${baseUrl()}/chat/completions").post(body.toString().toRequestBody("application/json".toMediaType()))
            if (key != null) rb.addHeader("Authorization", "Bearer $key")
            client.newCall(rb.build()).execute().use { res ->
                val raw = res.body?.string().orEmpty()
                if (!res.isSuccessful) return@withContext AiResult.Error("$providerId ${res.code}: $raw")
                val text = JSONObject(raw).getJSONArray("choices").getJSONObject(0).getJSONObject("message").getString("content")
                AiResult.Success(text, modelId)
            }
        } catch (e: Exception) { AiResult.Error("Ошибка $providerId: ${e.message}") }
    }
}

class DemoAdapter : AiProviderAdapter {
    override val providerId = "demo"
    override suspend fun isAvailable() = true
    override suspend fun generateText(modelId: String, messages: List<ChatMessage>, systemPrompt: String?): AiResult<String> {
        val q = messages.lastOrNull()?.content.orEmpty()
        return AiResult.Success("[Деморежим ALL AI]\nВаш запрос: «$q».\nДобавьте бесплатный ключ Gemini, Groq или OpenRouter в Настройках для полноценных ответов.", "Demo Engine")
    }
}

object Catalog {
    val models = listOf(
