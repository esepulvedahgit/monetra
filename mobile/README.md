# Monetra para Android

Aplicación Expo/React Native para las acciones cotidianas: Resumen, Movimientos, Metas y Perfil.

## Configuración local

```bash
npm ci
EXPO_PUBLIC_API_URL=http://10.0.2.2:5000/api/v1 npm run android
```

## Servidor

La app no queda atada a un servidor. En el primer inicio, la pantalla de ingreso pide la **dirección del servidor**, el correo y la contraseña. Puedes escribir solo el dominio (`monetra.midominio.com`) o una subruta (`https://midominio.com/monetra`), y la app agrega `/api/v1`. Antes de enviar las credenciales, la app comprueba que la dirección responda como una API de Monetra. El servidor queda guardado solo después de un ingreso exitoso.

En los siguientes ingresos ya no se pide el servidor. El botón **Servidor** de la parte superior del ingreso, el desbloqueo rápido y el Perfil permite editarlo. Al cambiarlo se cierra la sesión y se borran el acceso rápido y la caché local, de modo que los tokens de un servidor nunca se envían a otro.

- Solo se acepta **HTTPS con un certificado válido** (por ejemplo, Let's Encrypt). Los certificados autofirmados no funcionan en el APK de producción. HTTP solo se permite en compilaciones de desarrollo (emulador `10.0.2.2`).
- `EXPO_PUBLIC_API_URL` ya no fija el servidor. Solo prellena el campo en el primer inicio. Además, en teléfonos que se actualizan desde la versión 0.1.x con acceso rápido activo, se adopta como servidor guardado para no perder la sesión.
Los tokens se guardan con SecureStore; las respuestas `GET` se conservan como caché de solo lectura para mostrar la última información conocida sin red. Las mutaciones siempre requieren conexión.

## APK interno firmado

```bash
npx eas-cli build --platform android --profile internal
```

## APK de producción

La versión de producción sugiere `https://monetra.hgrey.net/api/v1` como servidor inicial y debe compilarse con el perfil `production`:

```bash
npx eas-cli build --platform android --profile production
```

EAS mantiene la clave privada de firma. Descarga el APK resultante y publícalo desde **Administración → App Android** en la web. El servidor verifica que su certificado SHA-256 coincida con `MOBILE_APK_SIGNER_SHA256`, conserva el historial de metadatos y entrega solamente el APK vigente a usuarios autenticados.
