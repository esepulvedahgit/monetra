# Monetra

[![CI](https://github.com/esepulvedahgit/monetra/actions/workflows/ci.yml/badge.svg)](https://github.com/esepulvedahgit/monetra/actions/workflows/ci.yml)
![Version](https://img.shields.io/badge/version-2.6-brightgreen)
![Python](https://img.shields.io/badge/python-3.12-blue?logo=python&logoColor=white)
![Flask](https://img.shields.io/badge/flask-3.0-lightgrey?logo=flask&logoColor=white)
![MySQL](https://img.shields.io/badge/mysql-8.0-blue?logo=mysql&logoColor=white)
![Docker](https://img.shields.io/badge/docker-ready-2496ED?logo=docker&logoColor=white)
![Bootstrap](https://img.shields.io/badge/bootstrap-5.3-7952B3?logo=bootstrap&logoColor=white)
![Chart.js](https://img.shields.io/badge/chart.js-4-FF6384?logo=chartdotjs&logoColor=white)
[![Ko-fi](https://img.shields.io/badge/Ko--fi-Apóyame-FF5E5B?logo=ko-fi&logoColor=white)](https://ko-fi.com/esepulvedah)

![Monetra](imagen_gitgub.png)

<div align="center">

[![ko-fi](https://ko-fi.com/img/githubbutton_sm.svg)](https://ko-fi.com/esepulvedah)

</div>

Aplicación web de **finanzas personales** desarrollada en Flask. Permite registrar ingresos y gastos, gestionar presupuestos mensuales, definir metas de ahorro, programar transacciones recurrentes y visualizar el estado financiero mediante gráficos interactivos.

---

## Características

- Dashboard mensual con resumen de ingresos, gastos, balance y gráfico de gastos por categoría
- Dashboard global con comparativa anual, tendencia multi-año y filtro por rango de meses
- Registro de movimientos con categorías personalizadas (colores individuales por categoría)
- Presupuesto mensual general, presupuestos por categoría (hasta 5) y presupuestos personalizados (rango libre de fechas)
- Transacciones recurrentes con generación automática mensual
- Metas de ahorro con seguimiento de progreso y fecha objetivo
- **Cuenta en dólares (USD)** con vista consolidada en moneda local
- **Escáner IA de recibos** — fotografía un ticket y extrae monto, descripción y comercio automáticamente (OpenAI, Anthropic, Gemini, DeepSeek, OpenRouter)
- **Bot de Telegram** — registra gastos desde el móvil enviando foto de recibo o texto libre; la IA extrae los datos y el bot confirma antes de guardar
- **IA compartida con control por usuario** — el admin puede compartir su clave de IA y habilitar el acceso individualmente a cada cuenta desde el panel de usuarios
- **PIN de acceso rápido** — login móvil con PIN de 8 dígitos vinculado al dispositivo (opt-in)
- **Panel de analítica** — salud financiera, proyección de cierre del mes y alertas inteligentes
- **Backup y restauración de base de datos** (admin) — export cifrado `.sql.gz` con re-autenticación
- Exportación a Excel con todas las secciones del período seleccionado (mensual, anual o rango)
- **Registro de auditoría de seguridad** (admin) — todos los eventos críticos con filtros y API
- Sistema de temas visuales: Dark, Ocean, Carbon, Dusk, Forest, Pearl, Abyss, Graphite, Enterprise
- Soporte bilingüe (Español / Inglés)
- Multi-moneda con 22 países latinoamericanos y europeos
- API REST completa con autenticación JWT (15 min) y tokens persistentes (sin expiración, formato `mntr_*`)
- Autenticación multifactor (TOTP / MFA)
- Reportes Excel semanales automáticos por correo + envío inmediato desde configuración
- Gestión de usuarios con roles (admin / user) y control de acceso a IA por cuenta
- Datos de demostración precargados (3 años, solo admin)
- Modo ayuda con tooltips por sección
- Guía de uso integrada

---

## Stack

| Capa | Tecnología | Versión |
|---|---|---|
| Backend | Flask + Gunicorn | 3.0 / ≥21.2 |
| Base de datos | MySQL | 8.0 |
| ORM | SQLAlchemy + PyMySQL | 3.1.1 / 1.1.0 |
| Autenticación web | Flask-Login + Flask-WTF (CSRF) | 0.6.3 / 1.2.1 |
| Autenticación API | Flask-JWT-Extended | 4.6.0 |
| MFA (TOTP) | pyotp + qrcode | ≥2.9 / ≥7.4 |
| i18n | Flask-Babel | ≥3.1 |
| Cifrado | Cryptography (Fernet) | 41.0.7 |
| Rate Limiting | Flask-Limiter | 3.8.0 |
| Storage rate limiting | Redis (opcional, recomendado en producción expuesta) | 8.0-alpine |
| Scheduler | APScheduler | ≥3.10 |
| Exportación Excel | xlsxwriter | ≥3.1 |
| Imágenes (scanner) | Pillow + pillow-heif | — / ≥0.13 |
| IA proveedores | OpenAI · Anthropic · Gemini · DeepSeek · OpenRouter | API compatible |
| CORS | Flask-CORS | 4.0.0 |
| Frontend | Bootstrap + Chart.js | 5.3 / 4 |
| Contenedores | Docker + Docker Compose | — |
| Runtime | Python 3.12-slim + mysql-client | — |

---

## Estructura del repositorio

```
monetra/
  site_finanzas/      # Código fuente de la aplicación Flask
    app/
      main/           # Vistas web principales (dashboard, transacciones, presupuestos, etc.)
      auth/           # Login, registro, MFA, PIN de acceso rápido, recuperación de contraseña
      admin/          # Gestión de usuarios — suspender, eliminar, control de acceso a IA (/admin/users)
      api/            # API REST en /api/v1
      export/         # Generador de reportes Excel
      demo_data/      # Carga y reset de datos de demostración
      usd/            # Cuenta en dólares y vista consolidada
      scanner/        # Escáner IA de recibos (/scanner/extract)
      telegram/       # Bot de Telegram — webhook, handlers, mensajes y vinculación de cuentas
      analytics/      # Salud financiera, proyección y alertas (/analytics)
      insights/       # Motor de análisis financiero (reglas, scoring, señales)
      backup/         # Export/restore de base de datos (/admin/backup)
      audit/          # Registro de auditoría (/admin/audit)
      services/       # Lógica de negocio compartida (finance.py)
      templates/      # Jinja2 (base, auth, main, errors, partials/announcements)
      translations/   # Archivos .po/.mo (es, en)
    models.py         # Todos los modelos SQLAlchemy (22 modelos)
    init_db.py        # Inicialización y migraciones de esquema
    run.py            # Punto de entrada (desarrollo)
    entrypoint.sh     # Espera MySQL → init_db.py → Gunicorn 1 worker (producción Docker)
    Dockerfile
    .env.example
  docker/
    docker-compose.yml       # Entorno de desarrollo (puerto 8085, build local, hot-reload)
    docker-compose.prod.yml  # Entorno de producción (imagen monetra:release)
    .env.example             # Variables unificadas para ambos compose
    CHANGELOG.md
    build-arm64.md           # Instrucciones build ARM64 con buildx + QEMU
    documentacion_monetra.md # Documentación completa de funciones y rutas
```

---

## Instalación rápida (un comando)

Requiere **Docker** y **Docker Compose** instalados. El script descarga el repositorio, genera todos los secretos automáticamente y levanta la aplicación lista para usar.

```bash
curl -fsSL https://raw.githubusercontent.com/esepulvedahgit/monetra/main/install.sh | bash
```

El script:
- Verifica las dependencias (Docker, git, openssl)
- Genera automáticamente: `SECRET_KEY`, `FIELD_ENCRYPTION_KEY`, `JWT_SECRET_KEY`, `DB_PASSWORD`, `MYSQL_ROOT_PASSWORD`
- Construye la imagen de producción `monetra:release`
- Levanta `docker-compose.prod.yml` y espera a que la app responda
- Imprime la URL de acceso y los pasos siguientes

La app queda disponible en `http://localhost:8085`. El primer usuario en registrarse queda como administrador.

---

## Despliegue con Docker

### Desarrollo

Construye la imagen desde el código fuente y monta el directorio para hot-reload.

```bash
# Desde la carpeta docker/
cp .env.example .env                          # Credenciales y config
cp .env ../site_finanzas/.env  # Config de Flask

# Edita ambos archivos con tus valores, luego:
docker compose up -d --build
```

La app queda disponible en `http://localhost:8085`.

### Producción

Usa la imagen etiquetada `monetra:release`. Requiere todas las variables de entorno definidas en `docker/.env`.

**1. Construir la imagen** (desde `site_finanzas/`):

```bash
# AMD64 (x86_64 — servidor estándar)
docker build -t monetra:release .
```

**2. Crear el archivo `.env`** en la carpeta `docker/`:

```env
# MySQL
MYSQL_ROOT_PASSWORD=clave-root-segura
DB_NAME=monetra_db
DB_USER=monetra_user
DB_PASSWORD=clave-db-segura

# Flask
SECRET_KEY=genera-con-secrets.token_hex(32)
FIELD_ENCRYPTION_KEY=genera-con-Fernet.generate_key()
JWT_SECRET_KEY=genera-con-secrets.token_hex(32)

```

**3. Levantar los servicios:**

```bash
# Desde la carpeta docker/
docker compose -f docker-compose.prod.yml up -d
```

El contenedor Flask espera a que MySQL y Redis estén saludables, ejecuta `init_db.py` automáticamente y levanta Gunicorn con **1 worker** en el puerto 8000 (expuesto en 8085).

> **¿Por qué 1 worker?** Sin un backend compartido, Flask-Limiter guarda los contadores de rate limiting en memoria de cada proceso — con varios workers, cada uno llevaría su propio contador y el límite efectivo se multiplicaría por la cantidad de workers. Ambos `docker-compose*.yml` incluyen un servicio **Redis** (ver sección [Rate limiting y seguridad de login](#rate-limiting-y-seguridad-de-login)) que resuelve esto: con `RATELIMIT_STORAGE_URI=redis://redis:6379/0` (default) el contador es compartido, por lo que subir el número de workers en `entrypoint.sh` ya es seguro si lo necesitas.

---

## Rate limiting y seguridad de login

### Backend compartido (Redis)

Ambos `docker-compose*.yml` levantan un servicio `redis` (imagen `redis:8.0-alpine`, sin persistencia, memoria acotada a 128 MB con expulsión LRU, **sin puerto publicado al host** — solo accesible dentro de la red interna del compose) que Flask-Limiter usa como almacén compartido de los contadores de intentos.

| Variable | Default | Descripción |
|---|---|---|
| `RATELIMIT_STORAGE_URI` | `redis://redis:6379/0` (Docker) / `memory://` (fuera de Docker) | Backend de Flask-Limiter. `redis://...` comparte el contador entre workers y sobrevive a reinicios — **recomendado si la app está expuesta directamente a internet** (sin WAF/equipo de seguridad delante). `memory://` es válido detrás de un WAF o en desarrollo con 1 worker. |

### Límites por ruta (configurables sin tocar código)

Cada límite sigue la sintaxis de Flask-Limiter: `"N per second|minute|hour|day"`. Cambia el valor en `docker/.env` (o `site_finanzas/.env` fuera de Docker) y reinicia el contenedor para aplicar — sin definir, cada uno usa el default indicado.

| Variable | Default | Ruta |
|---|---|---|
| `LOGIN_RATE_LIMIT` | `5 per minute` | `POST /login` |
| `API_LOGIN_RATE_LIMIT` | `5 per minute` | `POST /api/v1/login` |
| `MFA_VERIFY_RATE_LIMIT` | `5 per minute` | `POST /mfa-verify` |
| `REGISTER_RATE_LIMIT` | `5 per minute` | `POST /register` |
| `RESEND_ACTIVATION_RATE_LIMIT` | `3 per 15 minute` | `POST /resend-activation` |
| `FORGOT_PASSWORD_RATE_LIMIT` | `3 per 15 minute` | `POST /forgot-password` |
| `RESET_PASSWORD_RATE_LIMIT` | `5 per 15 minute` | `POST /reset-password/<token>` |
| `PIN_SET_RATE_LIMIT` | `10 per minute` | `POST /pin/set` |
| `PIN_DELETE_RATE_LIMIT` | `10 per minute` | `POST /pin/delete` |
| `PIN_LOGIN_RATE_LIMIT` | `5 per minute` | `POST /pin/login` |
| `BACKUP_EXPORT_RATE_LIMIT` | `5 per hour` | `POST /admin/backup/export` |
| `BACKUP_RESTORE_RATE_LIMIT` | `5 per hour` | `POST /admin/backup/restore` |
| `AI_TEST_CONNECTION_RATE_LIMIT` | `10 per minute` | `POST /configurar/test-ai` |
| `TELEGRAM_WEBHOOK_RATE_LIMIT` | `30 per minute` (por chat_id, `/start` exento) | `POST /telegram/webhook/<path>` |
| `TELEGRAM_LINK_CODE_RATE_LIMIT` | `5 per 10 minute` | `POST /telegram/generate-code` |

### Lockout de cuenta por fuerza bruta

Además del rate limit por IP, la cuenta se bloquea temporalmente tras varios intentos fallidos de login (**password o código MFA — un mismo contador cubre ambos pasos**), sin importar la IP de origen. Protege contra ataques distribuidos desde múltiples IPs, algo que el rate limit por IP no puede evitar por sí solo.

| Variable | Default | Descripción |
|---|---|---|
| `LOGIN_MAX_FAILS` | `3` | Intentos fallidos (password + MFA combinados) antes de bloquear la cuenta |
| `LOGIN_LOCK_MINUTES` | `30` | Minutos que dura el bloqueo |

Al alcanzar el umbral: la cuenta queda bloqueada, se registra el evento `auth.account_locked` en el [registro de auditoría](#características) y se envía un correo de alerta de seguridad al usuario. El contador se reinicia automáticamente en el siguiente login exitoso.

---

### Build multiarquitectura (AMD64 / ARM64)

Para VPS con procesador ARM64 (Oracle Cloud, AWS Graviton, Raspberry Pi, Apple Silicon con Docker):

**Requisitos previos (solo la primera vez):**

```bash
# Instalar emulación ARM64 en máquina x86
docker run --privileged --rm tonistiigi/binfmt --install all

# Crear builder multiplatforma
docker buildx create --driver docker-container --name multiplatform --use
```

**Build ARM64** (desde `site_finanzas/`):

```bash
docker buildx build --platform linux/arm64 -t monetra:release-arm64 --load .
```

**Build para ambas arquitecturas simultáneamente** (requiere registry):

```bash
docker buildx build \
  --platform linux/amd64,linux/arm64 \
  -t turegistro/monetra:release \
  --push .
```

**Transferir imagen ARM64 al VPS (sin registry):**

```bash
# Exportar
docker save monetra:release-arm64 -o monetra-release-arm64.tar

# Copiar al VPS
scp monetra-release-arm64.tar usuario@ip-vps:/ruta/destino/

# Cargar en el VPS
docker load -i monetra-release-arm64.tar
```

> Ver `docker/build-arm64.md` para más detalles y notas de troubleshooting.

---

## Variables de entorno

### `site_finanzas/.env` (Flask)

| Variable | Requerida | Descripción |
|---|---|---|
| `SECRET_KEY` | Sí | Clave de sesión Flask |
| `FIELD_ENCRYPTION_KEY` | Sí | Clave Fernet — cifra contraseñas SMTP, secrets MFA y API keys del scanner |
| `DB_HOST` | Sí* | Host MySQL (usar `mysql` dentro de Docker) |
| `DB_PORT` | No | Puerto MySQL (default: `3306`) |
| `DB_NAME` | Sí* | Nombre de la base de datos |
| `DB_USER` | Sí* | Usuario MySQL |
| `DB_PASSWORD` | Sí* | Contraseña MySQL |
| `DATABASE_URL` | Alt.* | URL completa MySQL (reemplaza las variables `DB_*`) |
| `JWT_SECRET_KEY` | No | Clave JWT para la API REST (se genera automáticamente si no se define) |
| `CORS_ORIGINS` | No | Orígenes permitidos para la API REST (default: `*`) |
| `FLASK_DEBUG` | No | `true` activa modo debug (default: `false`) |
| `FLASK_TESTING` | No | `true` activa modo testing (default: `false`) |
| `MAX_CONTENT_UPLOAD_MB` | No | Tamaño máximo de archivos subidos en MB (default: `15`) |
| `MAX_RESTORE_SQL_MB` | No | Tamaño máximo del archivo SQL de restauración en MB (default: `500`) |
| `SESSION_COOKIE_SECURE` | No | `true` → cookies solo por HTTPS (reverse proxy con TLS). `false` → HTTP plano. Default: `true` en producción, `false` en debug |
| `SESSION_INACTIVITY_TIMEOUT` | No | Segundos de inactividad antes de cerrar sesión automáticamente (default: `900` — 15 min) |
| `TELEGRAM_BOT_TOKEN` | No* | Token del bot obtenido de @BotFather. Requerido para habilitar el bot de Telegram. |
| `TELEGRAM_WEBHOOK_SECRET` | No* | Cadena aleatoria para validar que los mensajes entrantes provienen de Telegram. Requerido con `TELEGRAM_BOT_TOKEN`. |
| `TELEGRAM_BOT_USERNAME` | No* | Username del bot sin `@` (ej. `mi_bot`). Si se omite, Monetra lo deriva automáticamente al iniciar via la API de Telegram. |
| `AI_SHARED_DAILY_LIMIT` | No | Máximo de escaneos de IA por usuario por día cuando se usa la clave compartida del admin (default: `25`). |
| `RATELIMIT_STORAGE_URI` | No | Backend de Flask-Limiter — `memory://` (default) o `redis://host:6379/0`. Ver [Rate limiting y seguridad de login](#rate-limiting-y-seguridad-de-login). |
| `LOGIN_MAX_FAILS` / `LOGIN_LOCK_MINUTES` | No | Umbral y duración del bloqueo de cuenta por fuerza bruta en login (defaults: `3` / `30`). Ver sección de rate limiting. |
| `<RUTA>_RATE_LIMIT` (15 variables) | No | Límite por ruta (login, registro, PIN, backup, etc.) — ver tabla completa en [Rate limiting y seguridad de login](#rate-limiting-y-seguridad-de-login). |

Generar valores seguros:
```bash
python -c "import secrets; print(secrets.token_hex(32))"        # SECRET_KEY, JWT_SECRET_KEY
python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"  # FIELD_ENCRYPTION_KEY
```

### `docker/.env` (Docker Compose — fuente única para dev y prod)

```env
# MySQL
MYSQL_ROOT_PASSWORD=
DB_NAME=
DB_USER=
DB_PASSWORD=

# Flask
SECRET_KEY=
FIELD_ENCRYPTION_KEY=
JWT_SECRET_KEY=

# Seguridad de sesión (opcional)
# false → HTTP plano (sin TLS). true → solo HTTPS (con reverse proxy).
# install.sh establece false por defecto; cámbialo a true al activar HTTPS.
SESSION_COOKIE_SECURE=false
# Segundos de inactividad antes de cerrar sesión automáticamente (default: 900 = 15 min)
# SESSION_INACTIVITY_TIMEOUT=900

# API REST — orígenes CORS permitidos (default: '*')
# CORS_ORIGINS=*

# Rate limiting — backend compartido (recomendado si la app está expuesta
# directamente a internet, sin WAF/equipo de seguridad delante)
# RATELIMIT_STORAGE_URI=redis://redis:6379/0

# Lockout de cuenta por fuerza bruta en login (password + MFA)
# LOGIN_MAX_FAILS=3
# LOGIN_LOCK_MINUTES=30

# Límites por ruta — ver README § Rate limiting y seguridad de login para la
# lista completa (LOGIN_RATE_LIMIT, API_LOGIN_RATE_LIMIT, PIN_LOGIN_RATE_LIMIT, ...)

# Backup (opcional, defaults razonables)
# MAX_CONTENT_UPLOAD_MB=15
# MAX_RESTORE_SQL_MB=500

# Bot de Telegram (opcional — si no se definen, la sección Telegram queda deshabilitada)
# TELEGRAM_BOT_TOKEN=123456789:ABCdef...
# TELEGRAM_WEBHOOK_SECRET=cadena-aleatoria-segura
# TELEGRAM_BOT_USERNAME=nombre_del_bot   # opcional: Monetra lo detecta automáticamente

# IA compartida — límite diario de escaneos por usuario sobre la clave del admin (default: 25)
# AI_SHARED_DAILY_LIMIT=25
```

---

## Primera ejecución

Al iniciar, `init_db.py` crea todas las tablas y siembra 12 categorías predeterminadas con sus colores. El **primer usuario que se registre** queda automáticamente como administrador.

Para cargar datos de demostración (3 años de transacciones ficticias), accede a `/admin/demo/load` como administrador.

---

## Ejecución local (sin Docker)

Requiere una instancia MySQL accesible.

```bash
cd site_finanzas
pip install -r requirements.txt
cp .env.example .env   # Completar con credenciales reales
python init_db.py
python run.py
```

---

## API REST

Disponible en `/api/v1`. Soporta dos métodos de autenticación:

- **JWT de sesión** — token de 15 minutos obtenido en `/api/v1/login` (access + refresh).
- **Token persistente** — generado desde Configuración → Token API, sin fecha de expiración, formato `mntr_*`. Se puede revocar en cualquier momento.

```bash
# Obtener token JWT
curl -X POST http://localhost:8085/api/v1/login \
  -H "Content-Type: application/json" \
  -d '{"email": "usuario@ejemplo.com", "password": "contraseña"}'

# Usar token (JWT o token persistente)
curl http://localhost:8085/api/v1/transactions \
  -H "Authorization: Bearer <token>"
```

Recursos disponibles: `transactions`, `budgets`, `categories`, `recurring`, `savings`, `dashboard/summary`, `dashboard/global`, `audit/logs` (solo admin).

---

## Traducciones

```bash
# Después de agregar strings en Python o templates:
cd site_finanzas
pybabel extract -F babel.cfg -k _l -o messages.pot .
pybabel update -i messages.pot -d app/translations

# Editar app/translations/en/LC_MESSAGES/messages.po
# Luego compilar:
pybabel compile -d app/translations
```

---

## Apoya el proyecto

Monetra es un proyecto personal de código abierto. Si te resulta útil, puedes apoyar su desarrollo con una donación en Ko-fi:

[![ko-fi](https://ko-fi.com/img/githubbutton_sm.svg)](https://ko-fi.com/esepulvedah)
