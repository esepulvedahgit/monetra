# Monetra

![Version](https://img.shields.io/badge/version-2.5-brightgreen)
![Python](https://img.shields.io/badge/python-3.12-blue?logo=python&logoColor=white)
![Flask](https://img.shields.io/badge/flask-3.0-lightgrey?logo=flask&logoColor=white)
![MySQL](https://img.shields.io/badge/mysql-8.0-blue?logo=mysql&logoColor=white)
![Docker](https://img.shields.io/badge/docker-ready-2496ED?logo=docker&logoColor=white)
![Bootstrap](https://img.shields.io/badge/bootstrap-5.3-7952B3?logo=bootstrap&logoColor=white)
![Chart.js](https://img.shields.io/badge/chart.js-4-FF6384?logo=chartdotjs&logoColor=white)
[![Ko-fi](https://img.shields.io/badge/Ko--fi-Apóyame-FF5E5B?logo=ko-fi&logoColor=white)](https://ko-fi.com/esepulvedah)

![Monetra](imagen_gitgub.png)

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
- **Escáner IA de recibos** — fotografía un ticket y extrae monto, categoría y fecha automáticamente (OpenAI, Anthropic, Gemini, Ollama)
- **Autenticación biométrica** — Face ID, huella dactilar o Windows Hello vía WebAuthn
- **Panel de analítica** — salud financiera, proyección de cierre del mes y alertas inteligentes
- **Backup y restauración de base de datos** (admin) — export cifrado `.sql.gz` con re-autenticación
- Exportación a Excel con todas las secciones del período seleccionado (mensual, anual o rango)
- **Registro de auditoría de seguridad** (admin) — todos los eventos críticos con filtros y API
- Sistema de temas visuales: Dark, Ocean, Carbon, Dusk, Forest, Pearl, Abyss, Graphite
- Soporte bilingüe (Español / Inglés)
- Multi-moneda con 22 países latinoamericanos y europeos
- API REST completa con autenticación JWT (15 min) y tokens persistentes (365 días)
- Autenticación multifactor (TOTP / MFA)
- Reportes Excel semanales automáticos por correo + envío inmediato desde configuración
- Gestión de usuarios con roles (admin / user)
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
| Biometría | python-webauthn | 2.1.0 |
| MFA (TOTP) | pyotp + qrcode | ≥2.9 / ≥7.4 |
| i18n | Flask-Babel | ≥3.1 |
| Cifrado | Cryptography (Fernet) | 41.0.7 |
| Rate Limiting | Flask-Limiter | 3.8.0 |
| Scheduler | APScheduler | ≥3.10 |
| Exportación Excel | xlsxwriter | ≥3.1 |
| Imágenes (scanner) | Pillow + pillow-heif | — / ≥0.13 |
| IA proveedores | OpenAI · Anthropic · Gemini · Ollama | API compatible |
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
      auth/           # Login, registro, MFA, biometría, recuperación de contraseña
      api/            # API REST en /api/v1
      export/         # Generador de reportes Excel
      demo_data/      # Carga y reset de datos de demostración
      usd/            # Cuenta en dólares y vista consolidada
      scanner/        # Escáner IA de recibos (/scanner/extract)
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
- Pregunta tu dominio para pre-configurar la autenticación biométrica (opcional — Enter para omitir)
- Genera automáticamente: `SECRET_KEY`, `FIELD_ENCRYPTION_KEY`, `JWT_SECRET_KEY`, `DB_PASSWORD`, `MYSQL_ROOT_PASSWORD`
- Construye la imagen de producción `monetra:release`
- Levanta `docker-compose.prod.yml` y espera a que la app responda
- Imprime la URL de acceso y los pasos siguientes

La app queda disponible en `http://localhost:8085`. El primer usuario en registrarse queda como administrador.

> **Biometría (WebAuthn):** si ingresaste un dominio durante la instalación, edita `docker/.env` y activa las líneas `WEBAUTHN_*` con tu dominio real + HTTPS (nginx/Caddy delante del contenedor). Sin dominio propio la app funciona completamente; solo la autenticación biométrica requiere HTTPS.

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

# WebAuthn (biometría) — ajustar al dominio real en producción
WEBAUTHN_RP_ID=tudominio.com
WEBAUTHN_RP_NAME=Monetra
WEBAUTHN_ORIGIN=https://tudominio.com
```

**3. Levantar los servicios:**

```bash
# Desde la carpeta docker/
docker compose -f docker-compose.prod.yml up -d
```

El contenedor Flask espera a que MySQL esté saludable, ejecuta `init_db.py` automáticamente y levanta Gunicorn con **1 worker** en el puerto 8000 (expuesto en 8085).

> **¿Por qué 1 worker?** Flask-Limiter almacena los contadores de rate limiting en memoria. Con múltiples workers, cada proceso tendría su propio contador independiente, lo que permitiría bypassear los límites de intentos. No aumentes los workers sin migrar a un backend compartido como Redis.

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
| `WEBAUTHN_RP_ID` | No | Dominio para biometría WebAuthn (default: `localhost`) |
| `WEBAUTHN_RP_NAME` | No | Nombre de la app en el diálogo biométrico (default: `Monetra`) |
| `WEBAUTHN_ORIGIN` | No | Origen completo `https://dominio` para verificación WebAuthn |
| `MAX_CONTENT_UPLOAD_MB` | No | Tamaño máximo de archivos subidos en MB (default: `15`) |
| `MAX_RESTORE_SQL_MB` | No | Tamaño máximo del archivo SQL de restauración en MB (default: `500`) |

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

# WebAuthn (producción)
WEBAUTHN_RP_ID=
WEBAUTHN_RP_NAME=Monetra
WEBAUTHN_ORIGIN=

# Backup (opcional, defaults razonables)
MAX_CONTENT_UPLOAD_MB=15
MAX_RESTORE_SQL_MB=500
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
- **Token persistente** — generado desde Configuración → Token API, válido 365 días, formato `mntr_*`.

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
