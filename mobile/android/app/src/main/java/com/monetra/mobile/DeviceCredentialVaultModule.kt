package com.monetra.mobile

import android.app.Activity
import android.app.KeyguardManager
import android.hardware.biometrics.BiometricManager
import android.hardware.biometrics.BiometricPrompt
import android.os.Build
import android.os.CancellationSignal
import android.security.keystore.KeyGenParameterSpec
import android.security.keystore.KeyProperties
import android.util.Base64
import com.facebook.react.bridge.Arguments
import com.facebook.react.bridge.Promise
import com.facebook.react.bridge.ReactApplicationContext
import com.facebook.react.bridge.ReactContextBaseJavaModule
import com.facebook.react.bridge.ReactMethod
import com.facebook.react.module.annotations.ReactModule
import java.nio.charset.StandardCharsets
import java.security.KeyStore
import java.security.SecureRandom
import javax.crypto.Cipher
import javax.crypto.KeyGenerator
import javax.crypto.SecretKey
import javax.crypto.spec.GCMParameterSpec
import javax.crypto.spec.SecretKeySpec

/**
 * Keeps a refresh token encrypted with a random data key. That data key is itself
 * wrapped by an Android Keystore key that requires BIOMETRIC_STRONG or the device
 * credential (PIN, pattern, or password). Only the data key is kept in memory
 * while a quick-access session is open, so rotated refresh tokens can be sealed
 * without prompting again.
 */
@ReactModule(name = DeviceCredentialVaultModule.NAME)
class DeviceCredentialVaultModule(reactContext: ReactApplicationContext) : ReactContextBaseJavaModule(reactContext) {
  companion object {
    const val NAME = "DeviceCredentialVault"
    private const val KEYSTORE = "AndroidKeyStore"
    private const val KEY_ALIAS = "monetra.quick_access.wrapping_key.v1"
    private const val PREFS = "monetra.quick_access.v1"
    private const val WRAPPED_KEY = "wrapped_data_key"
    private const val WRAPPED_KEY_IV = "wrapped_data_key_iv"
    private const val REFRESH_TOKEN = "refresh_token"
    private const val REFRESH_TOKEN_IV = "refresh_token_iv"
    private const val GCM_TAG_LENGTH = 128
  }

  private val stateLock = Any()
  private var operationGeneration = 0L
  private var activeDataKey: ByteArray? = null
  private var cancellationSignal: CancellationSignal? = null

  override fun getName() = NAME

  @ReactMethod
  fun getStatus(promise: Promise) {
    val map = Arguments.createMap()
    map.putBoolean("supported", isSupported())
    map.putBoolean("enrolled", isEnrolled())
    promise.resolve(map)
  }

  @ReactMethod
  fun enroll(refreshToken: String, promise: Promise) {
    if (!requireSupported(promise)) return
    val dataKey = ByteArray(32).also { SecureRandom().nextBytes(it) }
    try {
      authenticateCipher(Cipher.ENCRYPT_MODE, null, "Activar acceso rápido", promise) { cipher ->
        try {
          val wrappedKey = cipher.doFinal(dataKey)
          val refresh = encryptWithDataKey(dataKey, refreshToken.toByteArray(StandardCharsets.UTF_8))
          val stored = prefs().edit()
            .putString(WRAPPED_KEY, encode(wrappedKey))
            .putString(WRAPPED_KEY_IV, encode(cipher.iv))
            .putString(REFRESH_TOKEN, encode(refresh.first))
            .putString(REFRESH_TOKEN_IV, encode(refresh.second))
            .commit()
          if (!stored) throw IllegalStateException("The credential vault could not be written.")
          replaceActiveDataKey(dataKey)
          promise.resolve(null)
        } catch (error: Exception) {
          dataKey.fill(0)
          clearPersistedVault()
          promise.reject("ENROLL_FAILED", "No fue posible activar el acceso rápido.", error)
        }
      }
    } catch (error: Exception) {
      dataKey.fill(0)
      promise.reject("ENROLL_FAILED", "No fue posible preparar el acceso rápido.", error)
    }
  }

  @ReactMethod
  fun unlock(promise: Promise) {
    if (!requireSupported(promise)) return
    val wrapped = prefs().getString(WRAPPED_KEY, null)
    val wrappedIv = prefs().getString(WRAPPED_KEY_IV, null)
    val refresh = prefs().getString(REFRESH_TOKEN, null)
    val refreshIv = prefs().getString(REFRESH_TOKEN_IV, null)
    if (wrapped == null || wrappedIv == null || refresh == null || refreshIv == null) {
      promise.reject("NOT_ENROLLED", "El acceso rápido no está configurado.")
      return
    }
    try {
      authenticateCipher(Cipher.DECRYPT_MODE, decode(wrappedIv), "Desbloquear Monetra", promise) { cipher ->
        try {
          val dataKey = cipher.doFinal(decode(wrapped))
          val token = decryptWithDataKey(dataKey, decode(refresh), decode(refreshIv))
          replaceActiveDataKey(dataKey)
          promise.resolve(String(token, StandardCharsets.UTF_8))
          token.fill(0)
        } catch (error: Exception) {
          lockMemory()
          promise.reject("UNLOCK_FAILED", "No fue posible desbloquear el acceso rápido.", error)
        }
      }
    } catch (error: Exception) {
      promise.reject("UNLOCK_FAILED", "No fue posible preparar el desbloqueo.", error)
    }
  }

  @ReactMethod
  fun rotate(refreshToken: String, promise: Promise) {
    synchronized(stateLock) {
      val dataKey = activeDataKey
      if (dataKey == null) {
        promise.reject("LOCKED", "Desbloquea el acceso rápido antes de renovar la sesión.")
        return
      }
      try {
        val refresh = encryptWithDataKey(dataKey, refreshToken.toByteArray(StandardCharsets.UTF_8))
        val stored = prefs().edit().putString(REFRESH_TOKEN, encode(refresh.first)).putString(REFRESH_TOKEN_IV, encode(refresh.second)).commit()
        if (!stored) throw IllegalStateException("The rotated credential could not be written.")
        promise.resolve(null)
      } catch (error: Exception) {
        promise.reject("ROTATE_FAILED", "No fue posible proteger la sesión renovada.", error)
      }
    }
  }

  @ReactMethod
  fun lock(promise: Promise) {
    val cancellation = synchronized(stateLock) {
      operationGeneration += 1
      lockMemory()
      cancellationSignal.also { cancellationSignal = null }
    }
    cancellation?.cancel()
    promise.resolve(null)
  }

  @ReactMethod
  fun clear(promise: Promise) {
    val result = synchronized(stateLock) {
      operationGeneration += 1
      lockMemory()
      val cancellation = cancellationSignal.also { cancellationSignal = null }
      Pair(cancellation, clearPersistedVault())
    }
    result.first?.cancel()
    if (result.second) promise.resolve(null)
    else promise.reject("CLEAR_FAILED", "No fue posible eliminar de forma segura el acceso rápido.")
  }

  private fun isSupported(): Boolean {
    if (Build.VERSION.SDK_INT < Build.VERSION_CODES.R) return false
    val keyguard = reactApplicationContext.getSystemService(KeyguardManager::class.java)
    return keyguard?.isDeviceSecure == true
  }

  private fun isEnrolled(): Boolean = isSupported() &&
    prefs().contains(WRAPPED_KEY) && prefs().contains(WRAPPED_KEY_IV) &&
    prefs().contains(REFRESH_TOKEN) && prefs().contains(REFRESH_TOKEN_IV) && hasWrappingKey()

  private fun requireSupported(promise: Promise): Boolean {
    if (isSupported()) return true
    promise.reject("UNSUPPORTED", "El acceso rápido requiere Android 11 o superior y un bloqueo de pantalla configurado.")
    return false
  }

  private fun hasWrappingKey(): Boolean = try {
    KeyStore.getInstance(KEYSTORE).let { keyStore ->
      keyStore.load(null)
      keyStore.containsAlias(KEY_ALIAS)
    }
  } catch (_: Exception) { false }

  @Suppress("DEPRECATION")
  private fun authenticateCipher(mode: Int, iv: ByteArray?, title: String, promise: Promise, onSuccess: (Cipher) -> Unit) {
    val activity = reactApplicationContext.currentActivity
    if (activity == null) {
      promise.reject("NO_ACTIVITY", "No hay una pantalla activa para desbloquear Monetra.")
      return
    }
    val generation = synchronized(stateLock) {
      if (cancellationSignal != null) {
        promise.reject("PROMPT_IN_PROGRESS", "Ya hay una solicitud de desbloqueo en curso.")
        return
      }
      operationGeneration
    }
    val cipher = Cipher.getInstance("AES/GCM/NoPadding")
    val key = getOrCreateWrappingKey()
    if (mode == Cipher.ENCRYPT_MODE) cipher.init(mode, key) else cipher.init(mode, key, GCMParameterSpec(GCM_TAG_LENGTH, requireNotNull(iv)))
    val cancellation = CancellationSignal()
    synchronized(stateLock) {
      if (generation != operationGeneration) {
        promise.reject("CANCELLED", "La operación de acceso rápido fue cancelada.")
        return
      }
      cancellationSignal = cancellation
    }
    val prompt = BiometricPrompt.Builder(activity)
      .setTitle(title)
      .setAllowedAuthenticators(BiometricManager.Authenticators.BIOMETRIC_STRONG or BiometricManager.Authenticators.DEVICE_CREDENTIAL)
      .build()
    prompt.authenticate(BiometricPrompt.CryptoObject(cipher), cancellation, activity.mainExecutor,
      object : BiometricPrompt.AuthenticationCallback() {
        override fun onAuthenticationSucceeded(result: BiometricPrompt.AuthenticationResult) {
          val authenticatedCipher = result.cryptoObject?.cipher
          synchronized(stateLock) {
            if (generation != operationGeneration || cancellation.isCanceled) {
              promise.reject("CANCELLED", "La operación de acceso rápido fue cancelada.")
              return
            }
            if (cancellationSignal === cancellation) cancellationSignal = null
            if (authenticatedCipher == null) promise.reject("AUTH_FAILED", "No fue posible validar la credencial del dispositivo.")
            else onSuccess(authenticatedCipher)
          }
        }

        override fun onAuthenticationError(errorCode: Int, errString: CharSequence) {
          synchronized(stateLock) { if (cancellationSignal === cancellation) cancellationSignal = null }
          val code = if (errorCode == BiometricPrompt.BIOMETRIC_ERROR_USER_CANCELED || errorCode == BiometricPrompt.BIOMETRIC_ERROR_CANCELED) "CANCELLED" else "AUTH_FAILED"
          promise.reject(code, errString.toString())
        }

        override fun onAuthenticationFailed() {
          // Android allows another attempt. The prompt reports its terminal state via onAuthenticationError.
        }
      })
  }

  private fun getOrCreateWrappingKey(): SecretKey {
    val keyStore = KeyStore.getInstance(KEYSTORE).apply { load(null) }
    (keyStore.getKey(KEY_ALIAS, null) as? SecretKey)?.let { return it }
    val generator = KeyGenerator.getInstance(KeyProperties.KEY_ALGORITHM_AES, KEYSTORE)
    generator.init(KeyGenParameterSpec.Builder(KEY_ALIAS, KeyProperties.PURPOSE_ENCRYPT or KeyProperties.PURPOSE_DECRYPT)
      .setBlockModes(KeyProperties.BLOCK_MODE_GCM)
      .setEncryptionPaddings(KeyProperties.ENCRYPTION_PADDING_NONE)
      .setUserAuthenticationRequired(true)
      .setUserAuthenticationParameters(0, KeyProperties.AUTH_BIOMETRIC_STRONG or KeyProperties.AUTH_DEVICE_CREDENTIAL)
      .build())
    return generator.generateKey()
  }

  private fun encryptWithDataKey(dataKey: ByteArray, plainText: ByteArray): Pair<ByteArray, ByteArray> {
    val cipher = Cipher.getInstance("AES/GCM/NoPadding")
    cipher.init(Cipher.ENCRYPT_MODE, SecretKeySpec(dataKey, "AES"))
    return Pair(cipher.doFinal(plainText), cipher.iv)
  }

  private fun decryptWithDataKey(dataKey: ByteArray, cipherText: ByteArray, iv: ByteArray): ByteArray {
    val cipher = Cipher.getInstance("AES/GCM/NoPadding")
    cipher.init(Cipher.DECRYPT_MODE, SecretKeySpec(dataKey, "AES"), GCMParameterSpec(GCM_TAG_LENGTH, iv))
    return cipher.doFinal(cipherText)
  }

  private fun replaceActiveDataKey(dataKey: ByteArray) {
    lockMemory()
    activeDataKey = dataKey.copyOf()
    dataKey.fill(0)
  }

  private fun lockMemory() {
    activeDataKey?.fill(0)
    activeDataKey = null
  }

  /** Must run while [stateLock] is held. Either ciphertext removal or key removal destroys the vault. */
  private fun clearPersistedVault(): Boolean {
    val ciphertextCleared = prefs().edit().clear().commit()
    val keyDeleted = try {
      KeyStore.getInstance(KEYSTORE).let { keyStore ->
        keyStore.load(null)
        if (keyStore.containsAlias(KEY_ALIAS)) keyStore.deleteEntry(KEY_ALIAS)
        true
      }
    } catch (_: Exception) { false }
    return ciphertextCleared || keyDeleted
  }

  private fun prefs() = reactApplicationContext.getSharedPreferences(PREFS, Activity.MODE_PRIVATE)
  private fun encode(value: ByteArray): String = Base64.encodeToString(value, Base64.NO_WRAP)
  private fun decode(value: String): ByteArray = Base64.decode(value, Base64.NO_WRAP)
}
