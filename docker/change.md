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