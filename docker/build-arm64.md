# Build imagen ARM64 (para VPS ARM / Apple Silicon)

## Requisitos previos (solo la primera vez)

### 1. Instalar QEMU (emulación ARM64 en máquina x86)

```bash
docker run --privileged --rm tonistiigi/binfmt --install all
```

### 2. Crear builder multiplatforma

```bash
docker buildx create --driver docker-container --name multiplatform --use
```

Verificar que quedó activo:

```bash
docker buildx ls
```

Debe aparecer `multiplatform` con `*` indicando que es el builder activo.

---

## Build de la imagen

Ejecutar desde la carpeta `docker/`:

```bash
docker buildx build --platform linux/arm64 -t monetra:<version>-arm64 --load ../site_finanzas
```

Ejemplo con versión 2.0:

```bash
docker buildx build --platform linux/arm64 -t monetra:2.0-release-arm64 --load ../site_finanzas
```

---

## Exportar imagen como archivo .tar (para transferir al VPS)

```bash
docker save monetra:2.0-arm64 -o monetra-2.0-arm64.tar
```

Luego copiar al VPS con `scp`:

```bash
scp monetra-2.0-arm64.tar usuario@ip-vps:/ruta/destino/
```

## Cargar imagen en el VPS

```bash
docker load -i monetra-2.0-arm64.tar
```

---

## Notas

- El flag `--load` carga la imagen directamente en el Docker local (no la sube a un registry).
- Si el builder `multiplatform` ya existe de una sesión anterior, activarlo con:
  ```bash
  docker buildx use multiplatform
  ```
- Si aparece `exec format error` al correr el contenedor en ARM, significa que la imagen fue compilada para amd64. Hay que repetir el build con `--platform linux/arm64`.
