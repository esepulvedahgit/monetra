# Guía de Usuario — Monetra v2.3

Monetra es una aplicación de finanzas personales que te permite registrar ingresos y gastos, establecer presupuestos, definir metas de ahorro, automatizar movimientos recurrentes y exportar tus datos en Excel. Esta guía explica cómo funciona cada sección y cómo sacarle el máximo provecho.

---

## Índice

1. [Conceptos básicos](#1-conceptos-básicos)
2. [Selección de período](#2-selección-de-período)
3. [Dashboard mensual](#3-dashboard-mensual)
4. [Dashboard global](#4-dashboard-global)
5. [Transacciones](#5-transacciones)
6. [Categorías](#6-categorías)
7. [Presupuestos](#7-presupuestos)
8. [Metas de ahorro](#8-metas-de-ahorro)
9. [Recurrentes](#9-recurrentes)
10. [Exportar a Excel](#10-exportar-a-excel)
11. [Configuración de cuenta](#11-configuración-de-cuenta)
12. [Panel de analítica](#12-panel-de-analítica)
13. [Escáner IA](#13-escáner-ia)
14. [Autenticación biométrica](#14-autenticación-biométrica)
15. [Preguntas frecuentes](#15-preguntas-frecuentes)

---

## 1. Conceptos básicos

### Tipos de movimiento

Todo movimiento en Monetra es de uno de dos tipos:

- **Ingreso** — dinero que entra (sueldo, freelance, venta, etc.)
- **Gasto** — dinero que sale (arriendo, supermercado, servicios, etc.)

### Años y meses

Monetra organiza tus datos por año. Puedes tener datos de múltiples años y navegar entre ellos libremente. El año activo se muestra en la barra de navegación superior junto con el mes seleccionado.

### Datos de demostración

Al crear tu cuenta verás datos de ejemplo precargados. Estos registros están marcados como **Demo** y no pueden editarse ni eliminarse — sirven únicamente como referencia. Puedes crear tus propios registros en paralelo o limpiar los datos demo desde el panel de administración.

---

## 2. Selección de período

El **selector de período** en la barra superior controla qué datos ves en toda la aplicación.

- **Año**: selecciona el año de trabajo (ej. 2026).
- **Mes**: selecciona el mes dentro de ese año (ej. Mayo).

Al cambiar el período, el dashboard, las transacciones y los presupuestos se actualizan automáticamente al contexto seleccionado.

> **Nota:** Las transacciones nuevas deben crearse dentro del mes seleccionado. Si intentas guardar una transacción con una fecha fuera del mes activo, el formulario mostrará un error.

### Crear un nuevo año

Si necesitas registrar datos de un año que aún no aparece en el selector, ve a **Dashboard → Nuevo año** e ingresa el año deseado. Una vez creado, aparecerá disponible en el selector.

### Eliminar un año

Puedes eliminar un año completo desde el Dashboard. Esta operación **borra permanentemente** todas las transacciones, presupuestos y recurrentes de ese año. Es irreversible.

---

## 3. Dashboard mensual

El Dashboard mensual es la vista principal. Se accede desde el menú **Inicio** y muestra un resumen completo del mes seleccionado.

### ¿Qué muestra?

| Sección | Descripción |
|---|---|
| **Ingresos** | Suma de todos los ingresos del mes |
| **Gastos** | Suma de todos los gastos del mes |
| **Balance** | Ingresos − Gastos |
| **Presupuesto** | Barra de progreso: gastos vs. límite mensual definido |
| **Gastos por categoría** | Gráfico de torta con la distribución |
| **Últimas transacciones** | Los 5 movimientos más recientes del mes |
| **Presupuestos por categoría** | Estado de cada límite de categoría |
| **Metas de ahorro** | Hasta 4 metas activas con su progreso |
| **Panel de analítica** | Salud financiera, proyección y alertas *(opcional)* |

### Panel de analítica (opcional)

El panel de análisis inteligente incluye:

- **Salud financiera** — puntuación del mes según tus ingresos, gastos, presupuesto y metas.
- **Proyección de cierre** — estimación de cómo terminarás el mes si mantienes tu ritmo actual de gasto.
- **Alertas** — avisos sobre presupuesto excedido, déficit, metas en riesgo y comportamientos inusuales.

Este panel está **desactivado por defecto**. Para activarlo ve a **Configuración de Cuenta → Panel de Insights** y activa el interruptor.

### Generación automática de recurrentes

Cada vez que abres el Dashboard, Monetra verifica si existen transacciones recurrentes pendientes de generar para el mes actual y las crea automáticamente. No necesitas hacer nada manualmente.

---

## 4. Dashboard global

El Dashboard global permite analizar tus finanzas en un **rango de meses**, no solo uno. Se accede desde el menú **Global**.

### Selector de rango

- **Año**: el año de análisis.
- **Desde**: mes de inicio del rango (ej. Mayo).
- **Hasta**: mes de término del rango (ej. Agosto).

Haz clic en **Aplicar** para actualizar los gráficos al nuevo rango.

### ¿Qué muestra?

- **Tendencia mensual** — gráfico de líneas con ingresos y gastos mes a mes dentro del rango.
- **Gastos por categoría** — acumulado de todo el período.
- **Comparativa anual** — evolución de cada año disponible.

### Exportar desde el Dashboard global

El botón **Exportar Excel → Global** genera un archivo con los datos exactos del rango seleccionado. El enlace se actualiza en tiempo real al cambiar los selectores, sin necesidad de hacer clic en Aplicar primero.

---

## 5. Transacciones

Las transacciones son los movimientos individuales de dinero (ingresos y gastos). Se accede desde el menú **Transacciones**.

### Listado

Muestra todas las transacciones del mes seleccionado. Puedes filtrar por:

- **Tipo**: Todos / Ingresos / Gastos
- **Categoría**: filtrar por una categoría específica
- **Día**: mostrar solo las de un día en particular

Cada fila muestra: fecha, tipo, monto, descripción, categoría y acciones (editar / eliminar).

Las transacciones generadas por una recurrente muestran un indicador especial (ícono de recurrencia).

### Crear una transacción

1. Haz clic en **Nueva transacción**.
2. Completa los campos:
   - **Tipo**: Gasto o Ingreso.
   - **Monto**: valor en tu moneda (mayor a 0).
   - **Categoría**: lista filtrada según el tipo elegido.
   - **Descripción**: texto libre, opcional (máx. 200 caracteres).
   - **Fecha**: debe estar dentro del mes actualmente seleccionado.
3. Haz clic en **Guardar**.

### Editar una transacción

Haz clic en el ícono de lápiz en la fila correspondiente. Puedes cambiar cualquier campo. La fecha debe mantenerse dentro del mismo mes.

### Eliminar una transacción

Haz clic en el ícono de papelera. Se pedirá confirmación antes de borrar. Las transacciones de demostración no pueden eliminarse.

> **Importante:** Las transacciones generadas automáticamente por una recurrente también pueden eliminarse individualmente si así lo necesitas, sin afectar la recurrente.

---

## 6. Categorías

Las categorías organizan tus transacciones y recurrentes. Se accede desde el menú **Categorías**.

### Tipos de categorías

- **Categorías predeterminadas** — vienen incluidas en Monetra y no puedes modificarlas:
  - *Gastos*: Alimentación, Transporte, Vivienda, Servicios, Salud, Educación, Ocio, Otros.
  - *Ingresos*: Sueldo, Freelance, Inversiones, Otros Ingresos.
- **Categorías personalizadas** — las que tú creas. Tienen un color asignado automáticamente de una paleta de 21 colores.

### Crear una categoría

1. Haz clic en **Nueva categoría**.
2. Ingresa un nombre (máx. 50 caracteres).
3. Selecciona el tipo: Gasto o Ingreso.
4. Guarda.

El color se asigna automáticamente. No puedes tener dos categorías del mismo nombre y tipo.

### Eliminar una categoría

Una categoría **no puede eliminarse** si tiene:

- Transacciones asociadas.
- Recurrentes asociadas.
- Presupuestos de categoría asociados.
- Un presupuesto personalizado vinculado.

Si intentas eliminar una categoría con referencias, verás un mensaje indicando cuántos registros la bloquean. Primero debes eliminar o reasignar esos registros.

---

## 7. Presupuestos

Los presupuestos te permiten controlar cuánto gastas. Se accede desde el menú **Presupuestos**.

Hay tres tipos:

---

### 7.1 Presupuesto mensual general

Define el techo total de gastos para el mes seleccionado.

- Solo puede haber **un presupuesto general por mes**.
- En el Dashboard verás una barra de progreso que muestra cuánto has consumido del límite.
- Estados de la barra:
  - Verde: < 80% consumido.
  - Amarillo/advertencia: 80–99%.
  - Rojo/excedido: ≥ 100%.

Para crear o editar el presupuesto del mes, haz clic en **Editar presupuesto** en la sección de Presupuestos.

---

### 7.2 Presupuestos por categoría

Permiten establecer límites individuales por categoría de gasto dentro del mes.

- **Máximo 5 presupuestos de categoría por mes.**
- Solo aplican a categorías de tipo **Gasto**.
- Cada categoría solo puede tener un presupuesto por mes.

Para cada presupuesto de categoría se muestra:
- Monto establecido.
- Gasto real acumulado en esa categoría.
- Monto restante.
- Porcentaje consumido.

---

### 7.3 Presupuesto personalizado

Es un presupuesto puntual con rango de fechas dentro de un mes, pensado para eventos o proyectos específicos (ej. "Vacaciones julio", "Renovación depto").

**Características:**

- Crea automáticamente una **categoría de gasto** con el mismo nombre del presupuesto.
- Los gastos que registres en esa categoría se contabilizan contra el límite del presupuesto.
- Solo puede haber **un presupuesto personalizado vigente** por mes.
- Las fechas de inicio y término deben estar dentro del mismo mes.
- La fecha de término no puede ser anterior a hoy.

**Estados:**

| Estado | ¿Qué significa? |
|---|---|
| **Vigente** | end_date ≥ hoy. Puede editarse y eliminarse. |
| **Finalizado** | end_date < hoy. Es historial de solo lectura, no puede modificarse. |

**Al eliminar un presupuesto personalizado vigente:**

Se eliminarán también:
- Todas las transacciones de su categoría asociada.
- Todas las recurrentes de esa categoría.
- Los presupuestos de categoría vinculados.
- La categoría creada automáticamente.

Se te informará cuántos registros se borrarán antes de confirmar.

---

## 8. Metas de ahorro

Las metas te permiten definir objetivos financieros (ej. "Fondo de emergencia", "Viaje a Europa") y registrar tu avance. Se accede desde el menú **Metas**.

### Campos de una meta

| Campo | Descripción |
|---|---|
| **Nombre** | Identificador de la meta (máx. 100 caracteres) |
| **Monto objetivo** | Cuánto quieres ahorrar (mayor a 0) |
| **Monto ahorrado** | Cuánto llevas acumulado (empieza en 0) |
| **Fecha objetivo** | Fecha límite deseada (opcional) |
| **Descripción** | Notas adicionales (opcional, máx. 200 caracteres) |

### Abonar a una meta

Desde el listado de metas, haz clic en **Abonar** en la meta deseada e ingresa el monto. El progreso se actualiza automáticamente. Si el monto ahorrado alcanza el objetivo, la meta se marca como **Completada**.

### Marcar como completada manualmente

Puedes marcar/desmarcar una meta como completada con el botón de estado, independientemente del monto ahorrado.

### Visualización

- Las metas activas se muestran con barras de progreso.
- Las completadas aparecen en una sección separada.
- En el Dashboard mensual se muestran hasta 4 metas activas.

> Las metas son **independientes** de las transacciones. Abonar a una meta no crea un gasto en tu historial.

---

## 9. Recurrentes

Las recurrentes automatizan la creación de movimientos que se repiten todos los meses en una fecha fija (ej. arriendo el día 1, sueldo el día 30, Netflix el día 15). Se accede desde el menú **Recurrentes**.

### ¿Cómo funcionan?

Cada mes, cuando abres el Dashboard o la lista de transacciones, Monetra verifica las recurrentes activas y genera automáticamente la transacción si todavía no existe para ese mes. No necesitas hacerlo manualmente.

Si una recurrente tiene el día 31 y el mes solo tiene 30 días, Monetra ajusta automáticamente al último día del mes.

### Crear una recurrente

1. Haz clic en **Nueva recurrente**.
2. Completa los campos:
   - **Tipo**: Gasto o Ingreso.
   - **Monto**: valor que se generará cada mes.
   - **Categoría**: filtrada según el tipo elegido.
   - **Día del mes**: entre 1 y 28. Se recomienda usar máximo 28 para que funcione correctamente en febrero.
   - **Fecha de término**: opcional. Sin fecha, la recurrente genera movimientos hasta el 31/12 del año en que fue creada.
   - **Descripción**: texto libre (ej. "Arriendo", "Sueldo", "Netflix").
   - **Activa**: si está activa, genera transacciones; si está inactiva, no genera.
3. **¿El día ya pasó este mes?** — si seleccionas un día que ya ocurrió en el mes actual, aparecerá una casilla opcional para generar también la transacción del mes actual.

> **Importante:** Las recurrentes **no pueden eliminarse** una vez creadas. Para detenerlas usa el botón **Finalizar hoy** o establece una fecha de término.

### Editar una recurrente

Puedes cambiar cualquier campo (monto, categoría, día, fecha de término, etc.). Si activas una recurrente que estaba inactiva, Monetra generará retroactivamente las transacciones de los meses pasados que estén pendientes.

### Finalizar una recurrente

El botón **Finalizar hoy** (ícono de stop) en el listado de recurrentes vigentes:
- Establece la fecha de término como hoy.
- Desactiva la recurrente.
- No elimina las transacciones ya generadas — estas permanecen en tu historial.

También puedes usar el formulario de edición para establecer una fecha de término específica. La fecha de término no puede ser anterior al día de hoy.

### Listado de recurrentes

Las recurrentes se dividen en dos secciones:

- **Vigentes** — activas o que aún no han llegado a su fecha de término.
- **Finalizadas** — colapsadas, son solo historial de lectura.

---

## 10. Exportar a Excel

Monetra genera un reporte Excel completo con tus datos financieros. Se puede exportar desde dos lugares:

- **Menú superior → Exportar → Mes actual**: exporta el mes seleccionado.
- **Dashboard Global → Exportar → Global**: exporta el rango de meses seleccionado.

### Contenido del archivo

El Excel incluye las siguientes pestañas:

| Pestaña | Contenido | Alcance |
|---|---|---|
| **Portada** | KPIs del período (ingresos, gastos, balance, N° transacciones) e índice de pestañas | Período seleccionado |
| **Dashboard** | Gráficos e indicadores clave del período | Período seleccionado |
| **Movimientos** | Listado completo de transacciones | Período seleccionado |
| **Categorías** | Totales agrupados por categoría | Período seleccionado |
| **Presupuestos** | Comparativa presupuesto vs. gasto real | Período seleccionado |
| **Metas** | Objetivos de ahorro y su estado de avance | Historial completo |
| **Recurrentes** | Recurrentes vigentes y finalizadas con KPIs | Historial completo |
| **Base de Datos** | Datos en bruto para análisis propio (tablas dinámicas) | Período seleccionado |

### Nombre del archivo

El archivo se descarga con el nombre: `monetra_{usuario}_{año}_{mes}.xlsx` (para un mes) o `monetra_{usuario}_{año}.xlsx` (para un rango anual).

### Reporte semanal automático

Si configuras tu SMTP en **Configuración de Cuenta**, puedes activar el **Reporte semanal**. Monetra te enviará automáticamente el Excel todos los lunes con tus datos del año en curso.

---

## 11. Configuración de cuenta

Se accede desde el menú superior → tu nombre de usuario → **Configuración**. Aquí puedes personalizar todos los aspectos de tu cuenta.

### Moneda y país

- Selecciona tu país de la lista. Esto define el símbolo, código y formato de tu moneda.
- Puedes editar manualmente el **símbolo de moneda** si lo necesitas (ej. cambiar "$" por "CLP").
- Si tu moneda no es USD, puedes ingresar el **valor de referencia del dólar** (1 USD = N en tu moneda). Esto permite a Monetra convertir gastos en USD para la vista consolidada.

### Tema visual

Elige entre 9 temas disponibles: Dark, Ocean, Carbon, Dusk, Forest, Pearl, Abyss, Graphite, Enterprise. El cambio se aplica inmediatamente.

### Idioma

Selecciona entre Español e Inglés. Todos los textos de la aplicación cambian según esta preferencia.

### Panel de insights

Activa o desactiva el panel de analítica inteligente en el Dashboard (Salud financiera, Proyección de cierre, Alertas). Por defecto está desactivado.

### Modo de ayuda

Al activarlo, aparecen íconos de ayuda con explicaciones en los campos del formulario.

### Correo electrónico (SMTP)

Configura tu servidor SMTP para recibir reportes automáticos y recuperar tu contraseña por email. Campos requeridos si está habilitado:

- Servidor SMTP (ej. `smtp.gmail.com`)
- Puerto (ej. 587 para TLS, 465 para SSL)
- Usuario y contraseña
- Email y nombre del remitente
- TLS o SSL (solo uno a la vez)

Usa el botón **Enviar correo de prueba** para verificar que la configuración es correcta.

### Cambio de contraseña

Ingresa tu contraseña actual y la nueva (dos veces para confirmar). Al guardar, la sesión se cerrará automáticamente y deberás iniciar sesión con la nueva contraseña.

### Autenticación de dos factores (2FA)

Agrega una capa extra de seguridad con una app de autenticación (Google Authenticator, Authy, etc.):

1. Haz clic en **Configurar 2FA**.
2. Escanea el código QR con tu app.
3. Ingresa el código de 6 dígitos para confirmar.
4. A partir de ese momento, cada inicio de sesión pedirá un código TOTP.

Para desactivar, ingresa el código actual de tu app cuando se solicite.

### Token de API

Token de acceso personal (`mntr_…`) para consumir la API REST desde agentes o aplicaciones externas. Activo hasta que se revoque — sin fecha de expiración. Muestra el prefijo, la fecha de creación y la fecha de último uso. Opciones: **Generar**, **Regenerar** y **Revocar**. Guárdalo al crearlo — no se mostrará nuevamente.

### Reporte semanal

Activa el envío automático de tu reporte Excel cada lunes (requiere SMTP configurado).

---

## 15. Preguntas frecuentes

**¿Por qué no puedo eliminar una categoría?**
Porque tiene registros asociados: transacciones, recurrentes o presupuestos. Primero elimina o reasigna esos registros, luego podrás eliminar la categoría. El sistema te indicará exactamente cuántos registros la bloquean.

**¿Por qué no puedo editar un registro de Demo?**
Los registros de demostración son de solo lectura. Puedes crear tus propios registros en paralelo o resetear los datos demo desde el panel de administración.

**¿Puedo eliminar una recurrente?**
No. Las recurrentes no pueden eliminarse para preservar la coherencia de tu historial. Para detenerla usa el botón **Finalizar hoy** o edita la fecha de término. Las transacciones ya generadas permanecen en tu historial.

**¿Qué pasa si el día de mi recurrente no existe en el mes?**
Por ejemplo, si defines el día 31 y el mes tiene 30 días, Monetra ajusta automáticamente al último día del mes. Por eso se recomienda usar máximo el día 28 para que funcione igual en todos los meses, incluido febrero.

**¿El presupuesto personalizado borra mis transacciones si lo elimino?**
Sí. Al eliminar un presupuesto personalizado **vigente**, se borran también todas las transacciones y recurrentes de la categoría creada automáticamente. Se te informará cuántos registros se eliminarán antes de confirmar. Los presupuestos finalizados (cuya fecha de término ya pasó) no pueden eliminarse.

**¿Abonar a una meta descuenta de mi saldo?**
No. Las metas de ahorro son independientes de tus transacciones. Registrar un abono solo actualiza el contador de progreso de la meta. Si quieres también registrar el movimiento de dinero, debes crear una transacción por separado.

**¿Para qué sirve el valor del dólar en Configuración?**
Si gastas en dólares y tu moneda local es otra (ej. pesos chilenos), Monetra puede convertir tus gastos en USD al valor de referencia ingresado, permitiéndote ver un consolidado de todos tus gastos en una sola moneda.

**¿Cada cuánto se envía el reporte semanal?**
Todos los lunes a las 10:00 UTC. Requiere que hayas configurado tu servidor SMTP en Configuración de Cuenta y activado la opción "Reporte semanal".

**¿Puedo tener datos de varios años?**
Sí. Monetra soporta múltiples años. Puedes crear años desde el Dashboard y navegar entre ellos con el selector de período. Cada año es independiente en sus presupuestos y recurrentes.

**¿El Export de Excel incluye todos mis datos o solo el período visible?**
Depende de la pestaña. Movimientos, Categorías, Presupuestos, Dashboard y Base de Datos se filtran al período exportado. Metas y Recurrentes muestran el historial completo, independientemente del período seleccionado.

**¿El escáner siempre extrae bien los datos?**
Depende de la calidad de la imagen y el modelo de IA configurado. Imágenes claras, bien encuadradas y con buena iluminación dan mejores resultados. Siempre puedes revisar y corregir los datos extraídos en el paso de revisión antes de guardar la transacción.

**¿Puedo usar el PIN si tengo 2FA activado?**
Sí. Al ingresar con PIN y tener 2FA activo, serás redirigido a la pantalla de verificación TOTP. Deberás ingresar tu código de autenticador como de costumbre.

---

## 13. Escáner IA

El escáner usa inteligencia artificial para leer una foto o captura de pantalla de un recibo y extraer automáticamente el monto, la descripción y el comercio. Requiere configurar un proveedor de IA en **Configuración → Escáner IA**.

### Cómo acceder

- **Botón "Escanear recibo"** — visible en la barra de herramientas de la sección Movimientos.
- **Botón flotante (FAB)** — ícono de cámara en la esquina inferior derecha en dispositivos móviles (modo responsive) cuando el escáner está configurado y activo.

### Flujo de uso

1. **Elegir modo**: selecciona *Cámara* (acceso directo a la cámara del dispositivo) o *Subir imagen* (arrastra o selecciona un archivo).
2. **Capturar o subir**: toma la foto o sube el archivo. Formatos soportados: JPEG, PNG, WebP, HEIC.
3. **Revisar**: la IA extrae monto, descripción y comercio. Puedes editar cualquier dato antes de continuar.
4. **Guardar**: se crea la transacción en el mes activo con los datos revisados.

> **Privacidad:** la imagen se envía al proveedor de IA que hayas configurado. Monetra nunca almacena la imagen — se procesa en memoria y se descarta.

> **Nota:** imágenes borrosas, con poca luz o con texto muy pequeño pueden producir resultados incorrectos. Revisa siempre los datos antes de guardar.

### Configuración del proveedor

Ve a **Configuración → Escáner IA** y completa:

| Campo | Descripción |
|---|---|
| **Proveedor** | OpenAI, Anthropic, Gemini, DeepSeek u OpenRouter |
| **Modelo** | Debe soportar imágenes (multimodal). Ej: gpt-4o, claude-3-5-sonnet, gemini-1.5-flash |
| **URL base** | Opcional. Solo para proveedores compatibles con OpenAI. Vacío = URL oficial |
| **Token de API** | Tu clave del proveedor. Se guarda cifrada. Usa "Probar conexión" para verificarla |

---

## 14. PIN de acceso rápido

El PIN de acceso rápido es un método de login opt-in vinculado al dispositivo donde fue activado. Solo aparece en móvil (pantalla menor a 992 px). No es una credencial portátil: si cambias de dispositivo o borras las cookies deberás reactivarlo desde Configuración.

> **Nota:** el PIN no reemplaza tu contraseña. La necesitas para activarlo y eliminarlo. Es un acceso conveniente para el mismo dispositivo, no una alternativa de seguridad.

### Activar el PIN

1. Inicia sesión con tu email y contraseña desde tu dispositivo móvil.
2. Ve a **Configuración → Seguridad → PIN de acceso rápido**.
3. Confirma tu contraseña actual cuando se solicite.
4. Elige un PIN de 8 dígitos (no puede ser secuencia ni todos iguales).
5. Pulsa **Guardar PIN**.

La próxima vez que abras la pantalla de login en ese dispositivo, aparecerá el campo de PIN automáticamente.

### Ingresar con PIN

1. Abre la página de login desde el móvil donde activaste el PIN.
2. Escribe tu PIN de 8 dígitos en el campo que aparece.
3. Pulsa **Ingresar con PIN**.
4. Si tienes 2FA activo, serás redirigido a la verificación TOTP como de costumbre.

### Eliminar el PIN

Ve a Configuración → Seguridad → PIN de acceso rápido y pulsa **Eliminar**. Se pedirá tu contraseña para confirmar. El PIN y todos los dispositivos autorizados quedan revocados.

> **Importante:** la autorización del dispositivo expira a los 90 días de inactividad. Si el PIN expiró en ese dispositivo, deberás reactivarlo desde Configuración. Siempre podrás iniciar sesión con tu contraseña.
