# API de movimientos USD — Diseño

**Estado:** aprobado para planificación
**Fecha:** 2026-09-04

## Objetivo

Exponer una API REST para los movimientos USD con el mismo alcance CRUD que
`/api/v1/transactions`, usando el mismo JWT o token persistente `mntr_*` que
la API principal. La nueva API debe respetar el modelo USD existente, donde
todos los movimientos son gastos y las categorías pertenecen a cada usuario.

## Alcance

Incluido:

- Blueprint API independiente, anidado bajo `api_v1`, con prefijo `/usd`.
- Listado, creación, actualización parcial y eliminación de movimientos USD.
- Listado de categorías USD del usuario autenticado para construir solicitudes
  de movimiento válidas.
- Autenticación compartida mediante `api_login_required` y
  `get_current_api_user`.
- Validación de datos, aislamiento por usuario, pruebas y documentación de
  los endpoints.

Excluido:

- Tokens, tablas de autenticación, configuración o cabeceras nuevas.
- Migraciones de base de datos y cambios a `UsdTransaction`, `UsdCategory` o
  `UsdBudget`.
- Ingresos USD, recurrencias USD, metas USD, categorías globales USD y una API
  de presupuestos USD. Estos conceptos no existen en el dominio USD actual.
- Cambios en las rutas web existentes bajo `/usd`.

## Decisión de arquitectura

Se creará el child blueprint `usd_api` dentro del paquete `app.api.usd` y se
registrará en `api_v1`. Flask compondrá ambos prefijos para publicar las rutas
bajo `/api/v1/usd`; la aplicación continúa registrando y eximiendo de CSRF
solamente a `api_v1` desde la factory. Así, el nuevo recurso participa de la
configuración REST ya existente sin duplicar registro de aplicación, CORS o
exención CSRF.

La autenticación se aplica explícitamente a cada vista USD con el decorador
existente. Este decorador identifica al usuario con el mismo encabezado
`Authorization: Bearer <token>` utilizado por la API principal:

- JWT de acceso obtenido desde `/api/v1/login`.
- Token persistente revocable con formato `mntr_*`.

No se emitirá ni almacenará un token adicional. `get_current_api_user()` será
la única fuente de identidad para las consultas y mutaciones USD.

## Estructura de archivos

| Archivo | Responsabilidad |
|---|---|
| `site_finanzas/app/api/usd/__init__.py` | Declara `usd_api` con `url_prefix='/usd'` e importa las vistas. |
| `site_finanzas/app/api/usd/transactions.py` | Implementa los cuatro endpoints de movimientos y sus helpers de validación/propiedad. |
| `site_finanzas/app/api/usd/categories.py` | Implementa el listado de categorías USD del usuario autenticado. |
| `site_finanzas/app/api/usd/schemas.py` | Serializa movimientos y categorías USD sin reutilizar esquemas CLP incompatibles. |
| `site_finanzas/app/api/__init__.py` | Registra `usd_api` dentro de `api_v1` después de declarar el blueprint padre. |
| `site_finanzas/tests/test_api_usd.py` | Pruebas de integración del contrato USD. |
| `README.md` | Añade USD a los recursos REST y documenta su uso con el token compartido. |
| `docker/documentacion_monetra.md` | Añade la tabla de endpoints USD y sus restricciones. |

## Contrato HTTP

Todas las rutas requieren `Authorization: Bearer <JWT o mntr_*>` y producen
JSON.

| Método y ruta | Entrada | Respuesta exitosa |
|---|---|---|
| `GET /api/v1/usd/transactions` | Filtros opcionales `year`, `month`, `category_id` | `200 {"transactions": [...], "total": N}` |
| `POST /api/v1/usd/transactions` | JSON con `amount`, `date`, `category_id`; `description` opcional | `201` y el movimiento creado |
| `PUT /api/v1/usd/transactions/<id>` | JSON parcial con los mismos campos | `200` y el movimiento actualizado |
| `DELETE /api/v1/usd/transactions/<id>` | — | `200 {"message": "Eliminada"}` |
| `GET /api/v1/usd/categories` | — | `200` y la lista de categorías USD del usuario |

Un movimiento serializado tendrá:

```json
{
  "id": 42,
  "type": "expense",
  "currency": "USD",
  "amount": 24.99,
  "description": "Suscripción",
  "date": "2026-09-04",
  "category_id": 7,
  "category_name": "Servicios",
  "is_demo": false,
  "created_at": "2026-09-04T10:00:00+00:00"
}
```

`type` y `currency` son valores constantes de representación (`expense` y
`USD`); no se reciben ni persisten como campos editables. Una categoría
serializada tendrá `id`, `name`, `color` e `is_demo`.

## Flujo y reglas de dominio

1. La vista valida el Bearer token con el decorador existente y toma el usuario
   resultante desde `get_current_api_user()`.
2. El listado consulta únicamente `UsdTransaction.user_id == user.id`, aplica
   los filtros presentes y ordena por `date DESC, id DESC`, igual que el
   recurso principal.
3. Al crear o cambiar `category_id`, la API busca la categoría exclusivamente
   por el ID solicitado y `UsdCategory.user_id == user.id`. Una categoría de
   otro usuario se trata como no válida.
4. Al actualizar o eliminar, la API busca el movimiento por ID y usuario. Un
   ID inexistente o ajeno responde como no encontrado.
5. Después de una mutación válida, se confirma la transacción de base de datos
   y se devuelve la representación USD actualizada.

## Validación y errores

| Condición | Resultado |
|---|---|
| Sin JSON en `POST`, o JSON malformado | `400 {"error": "Se requiere JSON"}` |
| `amount` ausente, no numérico, no finito, menor o igual a cero, más de dos decimales o fuera de `Numeric(12,2)` | `400 {"error": "Monto inválido"}` |
| `date` ausente en creación o inválida | `400 {"error": "Fecha inválida (use YYYY-MM-DD)"}` |
| `description` no textual o de más de 200 caracteres | `400` con error descriptivo |
| `category_id` ausente al crear, nulo al modificar, inválido o ajeno | `400` con error de categoría |
| Token ausente, inválido o expirado | `401`, provisto por el decorador existente |
| Movimiento USD inexistente o ajeno | `404 {"error": "Transacción no encontrada"}` |

`PUT` permite actualizaciones parciales. Si incluye `amount`, `date`,
`description` o `category_id`, cada valor debe superar su validación. Campos
desconocidos no cambian el estado del movimiento.

## Pruebas de aceptación

`tests/test_api_usd.py` verificará, como mínimo:

- Un JWT y un único token persistente `mntr_*` ya existentes autorizan rutas
  principales y USD; no se crea ni configura un token USD.
- Un usuario puede crear un movimiento USD y recibe los campos constantes
  `type: "expense"` y `currency: "USD"`.
- El listado devuelve `transactions` y `total`, con filtros de año, mes y
  categoría, y con orden descendente por fecha/ID.
- Un usuario puede actualizar parcialmente monto, fecha, descripción y
  categoría propia, y eliminar posteriormente el movimiento.
- `POST`/`PUT` rechazan JSON, monto, fecha, descripción y categoría inválidos.
- Las categorías y movimientos de un segundo usuario no aparecen, no se
  aceptan como categoría y no se pueden actualizar ni eliminar.
- Las rutas principales de transacciones mantienen sus pruebas existentes.

## Compatibilidad y despliegue

No hay cambios de esquema ni datos que migrar. El cambio es aditivo: no
altera URLs, payloads ni autenticación de `/api/v1/transactions`. Desplegar
la aplicación actualizada publica las rutas USD; clientes existentes continúan
operando sin cambios. La documentación indicará que el token actual sirve para
ambas áreas.
