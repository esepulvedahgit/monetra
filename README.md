# Monetra

![Monetra](imagen_gitgub.png)

Aplicación web de **finanzas personales** desarrollada en Flask. Permite registrar ingresos y gastos, gestionar presupuestos mensuales, definir metas de ahorro, programar transacciones recurrentes y visualizar el estado financiero mediante gráficos interactivos.

---

## Características

- Dashboard mensual con resumen de ingresos, gastos, balance y gráfico de gastos por categoría
- Dashboard global con comparativa anual y tendencia multi-año
- Registro de movimientos con categorías personalizadas (colores individuales por categoría)
- Presupuesto mensual general y presupuestos por categoría (hasta 3)
- Transacciones recurrentes con generación automática mensual
- Metas de ahorro con seguimiento de progreso y fecha objetivo
- Exportación a Excel con todas las secciones del período seleccionado
- Sistema de temas visuales: Dark, Ocean, Carbon, Dusk, Forest, Life
- Soporte bilingüe (Español / Inglés)
- Multi-moneda con 22 países latinoamericanos y europeos
- API REST completa con autenticación JWT
- Autenticación multifactor (TOTP / MFA)
- Reportes Excel semanales automáticos por correo
- Gestión de usuarios con roles (admin / user)

---

## Stack

| Capa | Tecnología |
|---|---|
| Backend | Flask 3.x + Gunicorn |
| Base de datos | MySQL 8.0 |
| ORM | SQLAlchemy + PyMySQL |
| Autenticación web | Flask-Login + Flask-WTF (CSRF) |
| Autenticación API | Flask-JWT-Extended |
| i18n | Flask-Babel |
| Cifrado | Cryptography (Fernet) |
| Scheduler | APScheduler |
| Frontend | Bootstrap 5.3 + Chart.js 4 |
| Contenedores | Docker + Docker Compose |

---

## Estructura del repositorio

```
monetra/
  site_finanzas/      # Código fuente de la aplicación Flask
    app/
      main/           # Vistas web principales
      auth/           # Login, registro, MFA, recuperación de contraseña
      api/            # API REST en /api/v1
      export/         # Generador de reportes Excel
      demo_data/      # Carga y reset de datos de demostración
      services/       # Lógica de negocio compartida
      templates/      # Jinja2 (base, auth, main, errors)
      translations/   # Archivos .po/.mo (es, en)
    init_db.py        # Inicialización y migraciones de esquema
    run.py            # Punto de entrada (desarrollo)
    entrypoint.sh     # Init + Gunicorn (producción Docker)
    Dockerfile
    .env.example
  docker/
    docker-compose.yml       # Entorno de desarrollo
    docker-compose.prod.yml  # Entorno de producción
    .env.example             # Variables de MySQL para Compose
    CHANGELOG.md
```

---

## Despliegue con Docker

### Desarrollo

Construye la imagen desde el código fuente y monta el directorio para hot-reload.

```bash
# Desde la carpeta docker/
cp .env.example .env                          # Credenciales de MySQL
cp ../site_finanzas/.env.example ../site_finanzas/.env  # Config de Flask

# Edita ambos archivos con tus valores, luego:
docker compose up -d --build
```

La app queda disponible en `http://localhost:8000`.

### Producción

Usa una imagen pre-construida con tag `monetra:1.0`. Requiere todas las variables de entorno definidas en el `.env` de la carpeta `docker/`.

**1. Construir y exportar la imagen** (desde `site_finanzas/`):

```bash
docker build -t monetra:1.0 .
```

**2. Crear el archivo `.env`** en la carpeta `docker/` con todas las variables:

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

El contenedor Flask espera a que MySQL esté saludable antes de arrancar, ejecuta `init_db.py` automáticamente y levanta Gunicorn con 2 workers en el puerto 8000.

---

## Variables de entorno

### `site_finanzas/.env` (Flask)

| Variable | Requerida | Descripción |
|---|---|---|
| `SECRET_KEY` | Sí | Clave de sesión Flask |
| `FIELD_ENCRYPTION_KEY` | Sí | Clave Fernet para cifrar contraseñas SMTP y secrets MFA |
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

Generar valores seguros:
```bash
python -c "import secrets; print(secrets.token_hex(32))"        # SECRET_KEY, JWT_SECRET_KEY
python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"  # FIELD_ENCRYPTION_KEY
```

### `docker/.env` (Docker Compose — solo desarrollo)

```env
MYSQL_ROOT_PASSWORD=
MYSQL_USER=
MYSQL_PASSWORD=
```

---

## Primera ejecución

Al iniciar, `init_db.py` crea todas las tablas y siembra 12 categorías predeterminadas con sus colores. El primer usuario registrado con el email `e.esepulvedah@gmail.com` es promovido automáticamente a administrador. Este email puede cambiarse en `init_db.py` (constante `FIRST_ADMIN_EMAIL`).

Para cargar datos de demostración (4 años de transacciones ficticias), accede a `/admin/demo/load` como administrador.

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

Disponible en `/api/v1`. Usa autenticación JWT (Bearer token).

```bash
# Obtener token
curl -X POST http://localhost:8000/api/v1/login \
  -H "Content-Type: application/json" \
  -d '{"email": "usuario@ejemplo.com", "password": "contraseña"}'

# Usar token
curl http://localhost:8000/api/v1/transactions \
  -H "Authorization: Bearer <access_token>"
```

Recursos disponibles: `transactions`, `budgets`, `categories`, `recurring`, `savings`, `dashboard/summary`, `dashboard/global`.

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
