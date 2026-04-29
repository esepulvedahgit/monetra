# Monetra - Changelog

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

