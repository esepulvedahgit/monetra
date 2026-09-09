# Monetra para Android

Aplicación Expo/React Native para las acciones cotidianas: Resumen, Movimientos, Metas y Perfil.

## Configuración local

```bash
npm ci
EXPO_PUBLIC_API_URL=http://10.0.2.2:5000/api/v1 npm run android
```

En un teléfono físico, `EXPO_PUBLIC_API_URL` debe ser la URL HTTPS pública de Monetra.
Los tokens se guardan con SecureStore; las respuestas `GET` se conservan como caché de solo lectura para mostrar la última información conocida sin red. Las mutaciones siempre requieren conexión.

## APK interno firmado

```bash
npx eas-cli build --platform android --profile internal
```

EAS mantiene la clave privada de firma. Descarga el APK resultante y publícalo desde **Administración → App Android** en la web. El servidor verifica que su certificado SHA-256 coincida con `MOBILE_APK_SIGNER_SHA256`, conserva el historial de metadatos y entrega solamente el APK vigente a usuarios autenticados.
