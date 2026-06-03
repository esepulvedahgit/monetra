# Análisis de la Estructura del Proyecto Monetra

El proyecto **Monetra** está construido utilizando el framework web Flask bajo el patrón de diseño **Application Factory** y **Blueprints**. Esto permite que la aplicación sea modular, escalable y fácil de mantener.

A continuación se presenta un mapa detallado de la estructura del proyecto y la lógica de cada sección:

## 1. Raíz del Proyecto (`/site_finanzas`)

Contiene los archivos de configuración y puntos de entrada principales de la aplicación, así como la configuración para su despliegue.

*   **`run.py`**: El script principal de arranque de la aplicación durante el desarrollo.
*   **`config.py`**: Contiene las clases de configuración (por ejemplo, `Config`). Define variables de entorno, configuración de la base de datos (SQLAlchemy), secret keys, y configuraciones de extensiones como Babel (traducciones) y JWT (tokens).
*   **`init_db.py`**: Script de utilidad para inicializar la base de datos, crear tablas a partir de los modelos o insertar datos semilla (roles, usuarios administradores, categorías por defecto).
*   **`.env` / `.env.example`**: Archivos que almacenan variables de entorno sensibles (contraseñas, URLs de bases de datos, tokens).
*   **`Dockerfile` / `entrypoint.sh` / `.dockerignore`**: Configuración para contenerizar la aplicación con Docker, lo que facilita su despliegue y asegura que el entorno sea consistente en cualquier servidor.
*   **`requirements.txt`**: Listado de todas las dependencias y librerías de Python necesarias para ejecutar la aplicación.

---

## 2. Directorio Principal de la Aplicación (`/app`)

Este es el núcleo de la aplicación. Contiene toda la lógica de negocio, rutas, modelos y plantillas.

### 2.1 Archivos Core
*   **`__init__.py`**: Es el **Application Factory**. Aquí se inicializa la aplicación de Flask y todas sus extensiones (SQLAlchemy para BD, LoginManager para sesiones, CSRFProtect para seguridad, Babel para multi-idioma, JWTManager para la API). Además, se registran todos los **Blueprints** (módulos).
*   **`models.py`**: Define la estructura de la base de datos utilizando SQLAlchemy (ORM).
    *   *Modelos principales*: `User`, `Transaction`, `Category`, `Budget`, `SavingsGoal`, `RecurringTransaction`, `UserYear`, entre otros.
*   **`email_service.py`**: Contiene la lógica para el envío de correos electrónicos transaccionales (por ejemplo, reportes o recuperación de contraseñas).
*   **`scheduler.py`**: Lógica para tareas programadas (probablemente utilizando APScheduler) para ejecutar procesos en segundo plano, como la creación automática de transacciones recurrentes o el envío de reportes semanales.
*   **`announcements.py`**: Lógica para gestionar avisos o notificaciones del sistema que se muestran a los usuarios.

### 2.2 Blueprints (Módulos de Rutas)
La aplicación está dividida en submódulos o "Blueprints" para organizar mejor las rutas.

*   **`main/`**: El corazón del frontend para los usuarios autenticados.
    *   **Lógica**: Contiene rutas (`routes.py`) y formularios web (`forms.py`) para las vistas principales.
    *   **Rutas Clave**: `/dashboard`, `/transactions`, `/categories`, `/budget`, `/metas` (Metas de Ahorro), `/recurrentes` (Transacciones Recurrentes), `/configurar` (Ajustes de cuenta).
*   **`auth/`**: Gestión de usuarios y seguridad.
    *   **Lógica**: Rutas y formularios relacionados con la autenticación.
    *   **Rutas Clave**: Login, registro de usuarios, reseteo de contraseñas.
*   **`api/` (API v1)**: Interfaz de programación para aplicaciones externas o asincronía frontend.
    *   **Lógica**: En lugar de retornar HTML, esta sección retorna JSON. Está estructurada en archivos separados por entidad (`transactions.py`, `budgets.py`, `savings.py`, etc.).
    *   *Uso de JWT*: Protegida mediante tokens en lugar de sesiones tradicionales de navegador.
*   **`export/`**: Módulo dedicado a la exportación de datos.
    *   **Lógica**: Generación de reportes descargables por el usuario (probablemente CSV o PDF de sus transacciones y presupuestos).
*   **`demo_data/`**: Módulo de utilidad para entornos de demostración.
    *   **Lógica**: Rutas y scripts (`cli.py`) para poblar la base de datos con información de prueba o gestionar cuentas de modo "Demo".

### 2.3 Capa de Servicios (`/app/services`)
*   **`finance.py`**: Contiene la lógica de negocio pesada o "Business Logic". En lugar de tener cálculos matemáticos o agregaciones complejas en las rutas (controladores), se extraen a servicios. Aquí probablemente se calcula el total de ingresos/gastos, se agrupan datos para los gráficos del dashboard, o se evalúa el cumplimiento de presupuestos.

### 2.4 Frontend y Vistas
*   **`templates/`**: Archivos HTML utilizando el motor de plantillas **Jinja2**.
    *   `base.html`: Plantilla maestra que define la estructura general (Header, Sidebar, Footer, inclusión de CSS/JS).
    *   Carpetas como `main/`, `auth/` y `errors/` para organizar las vistas.
    *   `partials/`: Fragmentos de HTML reutilizables (como widgets, tarjetas o modales).
*   **`static/`**: Archivos estáticos públicos que el navegador descarga.
    *   Contiene hojas de estilo (`CSS`), scripts de cliente (`JS`), imágenes y posiblemente librerías de terceros.
*   **`translations/`**: Archivos de internacionalización (i18n) gestionados por Flask-Babel para soportar múltiples idiomas (ej. inglés y español).

---

## 🎯 Resumen del Flujo de Datos (Arquitectura MVC)

1.  **Model (Modelo):** `models.py` define cómo se guardan los datos.
2.  **View (Vista):** Los archivos en `templates/` (como el `budget.html` que tienes abierto) deciden cómo se muestra la información al usuario.
3.  **Controller (Controlador):** Los archivos `routes.py` (en `main`, `auth`, etc.) reciben la petición web, llaman a `services/finance.py` para procesar cálculos matemáticos, interactúan con los Modelos para guardar/leer la BD, y finalmente le pasan los datos estructurados a la Vista para renderizar la página.
