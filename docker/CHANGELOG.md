# Monetra - Changelog

## v2.6

### IA · Telegram — registro de gastos por chat
- Integración de IA con proveedores OpenAI, Ollama, Anthropic, Gemini, DeepSeek y OpenRouter
- La IA extrae monto, descripción y comercio desde texto o foto de recibo enviados al bot
- Bot de Telegram vinculado a la cuenta del usuario; requiere IA activa (Paso 1) para activarse
- Registro de gastos por chat: el bot confirma importe, categoría y fecha antes de guardar
- Tarjeta de configuración unificada "IA · Telegram" en Configuración de Cuenta
- Derivación automática del username del bot desde la API de Telegram (`getMe`) al iniciar la app
- Normalización defensiva del username en la generación del deep link

### Seguridad
- Protección SSRF en validación de `base_url` del proveedor de IA
- Sanitización de respuestas JSON del modelo para evitar filtración de prompts internos
- Token de API del proveedor cifrado con Fernet en `UserAIConfig`

### Correcciones y mejoras
- Renombrado "Escáner IA" → "IA · Telegram" en etiquetas, títulos y traducciones
- Eliminado acceso por cámara/escáner desde la barra superior (reemplazado por bot)
- Columna Origen en exportación Excel para distinguir transacciones recurrentes vs. manuales
- Variables de entorno `SESSION_COOKIE_SECURE` y `SESSION_INACTIVITY_TIMEOUT` documentadas

---

## v2.5

### Escáner IA de recibos
- Nuevo blueprint `scanner` en `/scanner/extract` y `/scanner/test`
- Fotografía un recibo y la IA extrae monto, categoría y fecha para crear la transacción
- Proveedores soportados: OpenAI, DeepSeek, OpenRouter (compatibles OpenAI), Anthropic, Gemini y Ollama (local)
- Soporte de imágenes JPEG, PNG, WEBP y HEIC (pillow-heif)
- API key del proveedor cifrada con Fernet en `UserAIConfig`
- Nuevo modelo `UserAIConfig` con proveedor, modelo, URL base y token cifrado

### PIN de acceso rápido
- Login opt-in vinculado al dispositivo desde móvil (pantalla < 992 px) con PIN de 8 dígitos
- El PIN se activa desde Configuración → Seguridad; requiere confirmar contraseña actual
- Token sha256 almacenado en cookie httpOnly (`monetra_pin_device`); la app solo guarda el hash
- Bloqueo automático tras 5 intentos fallidos (15 min); la autorización expira a los 90 días
- Modelo `UserPinDevice`; no reemplaza la contraseña ni el segundo factor (2FA/TOTP)

### Panel de analítica en Dashboard Global
- Accesible en `/analytics/dashboard` — salud financiera, proyección de cierre y alertas
- Motor compuesto por módulos `insights/` (reglas, scoring, señales) y `analytics/` (forecasting, anomalías, capacidad de ahorro)
- Panel opcional: se activa desde Configuración de Cuenta; por defecto permanece oculto
- Modo aprendizaje para usuarios con poco historial — alertas más suaves y orientativas

### Mejoras de calidad (publicadas como parches en el período)
- Refactor SMTP: separación de configuración y envío; botón "Enviar reporte ahora" no bloqueante
- Demo mode: cierre automático de sesión al activar o desactivar datos demo
- Backup: re-autenticación obligatoria en export, reset del botón al completar, fix autocomplete en modal de restauración
- Anuncios de versión: corregidos botones de navegación (Bootstrap 5 `data-bs-dismiss` en `<a>` bloqueaba `href`)
- Reporte semanal por email acotado al mes actual en lugar del año completo

---

## v2.3

### Dashboard de analítica opcional
- Panel de Salud financiera, Proyección de cierre y Alertas inteligentes disponible desde Dashboard Global
- Se activa desde Configuración de Cuenta → Panel de Insights (por defecto oculto)

### Mejoras en transacciones recurrentes
- Los recurrentes ya no se pueden eliminar: pasan al estado "Finalizada" conservando todo el historial
- Nuevo botón "Finalizar hoy" para terminar un recurrente en la fecha actual sin eliminarlo
- La fecha de término se puede editar desde el formulario

### Export global por rango de meses en tiempo real
- El botón de descarga Excel en Dashboard Global respeta el período seleccionado (ej. Mayo–Agosto) sin necesidad de hacer clic en "Aplicar" primero

### Guía de uso integrada
- Nueva sección accesible desde el menú de usuario (esquina superior derecha) → Guía de uso
- Explica cómo funciona cada módulo de Monetra

---

## v2.2

### Correcciones y mejoras intermedias
- Estabilización del panel de analítica introducido en v2.1
- Mejoras visuales en la sección de recurrentes
- Fixes de navegación en modales de anuncios de versión

---

## v2.1

### Cuenta en dólares (USD)
- Nuevo blueprint `usd` en `/usd/` para registrar ingresos y gastos en dólares de forma separada
- Categorías USD propias (`UsdCategory`), transacciones USD (`UsdTransaction`) y presupuesto mensual USD (`UsdBudget`)
- Vista consolidada en `/analytics/consolidated` — mueve los gastos USD a moneda local usando el valor de referencia configurado

### Análisis financiero inteligente
- Primer motor de análisis financiero: salud, proyección de cierre, alertas, anomalías
- Aprendizaje automático adaptativo: ajusta umbrales según el historial disponible del usuario
- Modo aprendizaje para usuarios nuevos con datos limitados

### Token API persistente
- Nuevo modelo `ApiToken` — tokens de 365 días con prefijo `mntr_*`
- Generados desde Configuración de Cuenta → Token API
- Autenticación dual en la API REST: JWT de sesión (15 min) o token persistente

---

## v2.0 Release

### Presupuestos por categoría
- Límites mensuales por categoría específica (hasta 5 por período)
- Visualización de progreso con estado ok / warning / over en Dashboard y Presupuestos

### Presupuestos personalizados
- Rango libre de fechas dentro del mes con nombre propio
- Crea automáticamente una categoría de gasto vinculada
- Un presupuesto personalizado por período

### Exportación Excel mensual, anual y por rango
- Descarga desde Configuración → Reporte Excel
- Un mes, año completo, o rango personalizado de meses
- Hojas: Dashboard, Movimientos, Categorías, Presupuestos, Metas, Recurrentes, Base de Datos

### Datos de demostración (Admin)
- Carga 3 años completos de transacciones ficticias con un clic (`/admin/demo/load`)
- Datos marcados como `is_demo=True` — protegidos de edición
- Reset completo que restaura el estado previo (`/admin/demo/reset`)

### Registro de auditoría (Admin)
- Panel `/admin/audit/` con KPIs, gráfico y tabla paginada de eventos
- Eventos registrados: auth, app, config, admin
- API de auditoría: `GET /api/v1/audit/logs` con filtros por categoría, IP, usuario y rango de fechas

### Backup y restauración de base de datos (Admin)
- Export cifrado `.sql.gz` con `mysqldump` desde `/admin/backup/export`
- Restauración desde archivo `.sql` en `/admin/backup/restore`
- Re-autenticación obligatoria con contraseña de cuenta antes de cualquier operación

---

## v1.4
### Mejoras de visualización en gráficos
- Barras más delgadas y con espaciado proporcional en Recurrentes y Metas
- Dashboard Global: gráfico "Gastos por Categoría" con ancho dinámico según número de categorías, barras delgadas y labels del eje X rotados 60°
- Dashboard Global: gráfico "Resumen Anual" con las mismas dimensiones que "Gastos por Categoría"

### Recuperación de contraseña con SMTP del administrador
- Los usuarios sin SMTP propio pueden recuperar su contraseña usando el SMTP configurado por el administrador (transparente para el usuario)
- Nueva prioridad de envío: SMTP propio activo → SMTP del administrador → sin envío
- Sección SMTP en configuración actualizada: nuevo texto explicativo, checkbox renombrado a "Usar mi propio SMTP", badge con 3 estados (propio / vía administrador / no disponible)

### Sistema de temas (Branding)
- 5 temas visuales disponibles: Dark, Ocean, Carbon, Dusk, Forest
- Implementado con CSS custom properties en archivo central `themes.css` (sin duplicación de bloques CSS)
- Preferencia de tema guardada por usuario en base de datos
- Selector visual en Configuración → Apariencia con swatches de color interactivos
- El tema se aplica globalmente: fondo, navbar, cards, hover states y dropdowns

### Sistema guia
- Pequeña reseña de uso de la aplicacion en popup de bienvenida
- Iconos Guia (?) por seccion para mejor sensacion al usuario

### Exportar excel
- Permite exportar excel, todas las las secciones

### Exportar excel
- 2 Themas nuevos Life y Dark Profundo


## v1.8

### Indicador de complejidad de contraseña en registro
- Barra de 5 segmentos que avanza de rojo → naranja → amarillo → verde a medida que se cumplen requisitos
- Checklist en tiempo real con iconos: 10 caracteres, mayúscula, minúscula, número, carácter especial
- Se muestra al comenzar a escribir y se oculta si el campo queda vacío
- Colores y estilos usando CSS variables del tema activo (`--monetra-primary`, `--monetra-text-muted`, `--card-border`)
- Verificaciones en JS espejo exacto de la política del backend (`validate_password_policy`)

### Seguridad — Rate limiting en autenticación
- `POST /login`: límite de 5 intentos por minuto por IP
- `POST /register`: límite de 5 intentos por minuto por IP
- `POST /mfa-verify`: límite de 5 intentos por minuto por IP (cierra bypass en flujo MFA)
- `POST /forgot-password` y `POST /reset-password`: límites preexistentes conservados (3/15min y 5/15min)
- Todos los límites aplican solo a POST; GET no se ve afectado
- Página de error 429 (`errors/429.html`) con tema del usuario — reemplaza la respuesta en texto plano del sistema

### Seguridad — Infraestructura Docker
- `docker/.env` corregido: nombres de variables unificados (`DB_USER`, `DB_PASSWORD`, `DB_NAME`) para que coincidan con las referencias `${VAR}` del compose
- Variables faltantes agregadas: `DB_NAME`, `SECRET_KEY`, `FIELD_ENCRYPTION_KEY`, `JWT_SECRET_KEY`
- `docker-compose.yml` (dev) migrado a `environment: ${VAR}` — ambos compose leen desde `docker/.env` como fuente única
- Gunicorn reducido a 1 worker en `entrypoint.sh`: con almacenamiento en memoria, múltiples workers dividían el contador de rate limiting permitiendo bypass
- `entrypoint.sh` normalizado a LF sin BOM: CRLF o BOM en el shebang causa `exec format error` al levantar el contenedor en Linux

### Descarga de Excel reorganizada
- Botón de descarga Excel eliminado del navbar principal para reducir densidad del menú
- Botón reubicado en Configurar → Reporte semanal por email, junto al botón "Enviar ahora"
- Visible en ambos estados: con SMTP configurado (junto a "Enviar ahora") y sin SMTP (junto al aviso de configuración)
- Icono y estilo verde Excel (`#1D6F42`) consistente con el formato del archivo generado

### Sistema de anuncios de versión para usuarios existentes
- Nuevo modelo `UserSeenAnnouncement` (`user_seen_announcements`) que persiste qué versión vio cada usuario
- Modal de novedades mostrado una sola vez al primer inicio de sesión posterior a una actualización
- Usuarios nuevos (creados a partir de la fecha de lanzamiento) no ven el modal
- Contenido del modal desacoplado en partials por versión (`partials/announcements/vX_Y.html`)
- Registro centralizado en `app/announcements.py`: agregar nueva versión requiere solo una entrada en el dict y un nuevo partial
- Marcado como visto vía `fetch POST /announcements/<key>/seen` al mostrarse el modal (sin recarga de página)


## v1.7

### Sistema de colores persistentes en categorías
- Nueva columna `color VARCHAR(7)` en la tabla `categories` con migración automática en `init_db.py`
- Paleta A — Default (21 colores vivid/saturados): asignados a las 12 categorías globales por nombre y reserva para futuras defaults
- Paleta B — Custom (21 colores compound/muted): mismos tonos que paleta A con menor brillo y saturación, visualmente distinguibles al verlos juntos
- Auto-asignación al crear una categoría personalizada: `_next_custom_color()` recorre la paleta B sin repetir hasta agotar los 21 slots
- Retroalimentación de colores en categorías default existentes (UPDATE al ejecutar `init_db.py`)

### Mejoras visuales en la sección Categorías
- Separación clara entre "Por defecto" (globales, sin borrar) y "Tuyas" (personales, borrables) dentro de cada card de tipo
- Cada badge muestra su color individual almacenado en el borde/stroke, no un color genérico por tipo
- Badges default: fondo transparente con borde del color propio de la categoría
- Badges custom: fondo con tint al 12% del color propio (`color-mix`) + borde, diferenciados visualmente de los default
- Header de cada card mantiene `--expense-color` / `--income-color` como indicador semántico de tipo
- Macro Jinja2 `category_section` reutilizable: cero duplicación entre el bloque de Gastos e Ingresos

### Gráficos del dashboard con colores por categoría
- Dashboard mensual: el pie chart "Gastos por Categoría" usa el color almacenado de cada categoría en lugar de rotar `CHART_COLORS`
- Dashboard global: el bar chart "Gastos por Categoría" usa el color almacenado de cada categoría
- Query ampliadao con `Category.color` en SELECT y GROUP BY en ambas vistas
- Fallback a `CHART_COLORS` cíclico si alguna categoría no tiene color asignado (datos pre-migración)
- `CHART_COLORS` se mantiene sin cambios para compatibilidad con gráficos que no agrupan por categoría (multi-year trend, recurrentes)

### Eliminación de categorías personalizadas
- Nueva ruta `POST /categories/<cat_id>/delete` con validación de propiedad (`user_id == current_user.id`)
- Bloqueo de borrado si la categoría tiene movimientos, recurrentes o presupuestos asociados (integridad de datos en dashboards garantizada)
- Modal de advertencia rectangular, centrado, con cierre por X o clic fuera del recuadro
- El modal muestra conteo exacto de cada tipo de dato que bloquea la eliminación (movimientos, transacciones recurrentes, presupuestos de categoría)
- Diseño consistente con el tema activo del usuario usando CSS variables (`--monetra-gold`, `--card-bg`, `--monetra-text`, `--card-border`)

### Páginas de error 404 y 500
- `errors/base_error.html`: template base standalone (no extiende `base.html`) para evitar fallos en cadena durante errores de BD o contexto
- `errors/404.html` y `errors/500.html` extienden `base_error.html` mediante bloques Jinja2, sin HTML propio
- Tema del usuario aplicado vía `data-theme="{{ current_user.theme if current_user.is_authenticated else 'dark' }}"` — consistencia visual total
- Todos los colores usan CSS variables del sistema de temas (`--monetra-bg`, `--card-bg`, `--monetra-primary`, `--expense-color`)
- Error 500 hace `db.session.rollback()` antes de renderizar para limpiar transacciones rotas

### Configuración por variables de entorno
- `FLASK_DEBUG=true/false` habilita o deshabilita el modo debug desde Docker o `.env`
- `FLASK_TESTING=true/false` habilita o deshabilita el modo testing desde Docker o `.env`
- Ambas variables son insensibles a mayúsculas (`True`, `TRUE`, `true` son equivalentes)
- Valor por defecto `false` si la variable no está definida

