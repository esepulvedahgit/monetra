#!/usr/bin/env bash
# =============================================================================
# Monetra — Script de instalación automática
# Uso:  curl -fsSL https://raw.githubusercontent.com/esepulvedahgit/monetra/main/install.sh | bash
# Uso local (ya clonado):  bash install.sh
#
# Variables de entorno opcionales:
#   MONETRA_BRANCH   rama a clonar        (default: main)
#   REPO_URL         URL del repositorio   (default: https://github.com/esepulvedahgit/monetra.git)
# =============================================================================
set -euo pipefail

# ── Colores ──────────────────────────────────────────────────────────────────
RED='\033[0;31m'; GREEN='\033[0;32m'; YELLOW='\033[1;33m'
CYAN='\033[0;36m'; BOLD='\033[1m'; RESET='\033[0m'

info()    { echo -e "${CYAN}[INFO]${RESET}  $*"; }
ok()      { echo -e "${GREEN}[OK]${RESET}    $*"; }
warn()    { echo -e "${YELLOW}[WARN]${RESET}  $*"; }
error()   { echo -e "${RED}[ERROR]${RESET} $*" >&2; exit 1; }
header()  { echo -e "\n${BOLD}${CYAN}=== $* ===${RESET}"; }

REPO_URL="${REPO_URL:-https://github.com/esepulvedahgit/monetra.git}"
MONETRA_BRANCH="${MONETRA_BRANCH:-main}"
FRESH_ENV=false   # se actualiza a true en write_env si se genera un .env nuevo

# ── PASO 1: Dependencias ─────────────────────────────────────────────────────
require_deps() {
    header "Verificando dependencias"

    command -v git    &>/dev/null || error "git no está instalado. Instálalo con: sudo apt install git"
    command -v openssl &>/dev/null || error "openssl no está instalado. Instálalo con: sudo apt install openssl"
    command -v curl   &>/dev/null || error "curl no está instalado. Instálalo con: sudo apt install curl"
    command -v docker &>/dev/null || error "Docker no está instalado. Ver: https://docs.docker.com/engine/install/"

    if docker compose version &>/dev/null 2>&1; then
        COMPOSE_CMD="docker compose"
    elif command -v docker-compose &>/dev/null; then
        COMPOSE_CMD="docker-compose"
    else
        error "Docker Compose no está instalado. Ver: https://docs.docker.com/compose/install/"
    fi
    export COMPOSE_CMD

    docker info &>/dev/null 2>&1 || error "El daemon de Docker no está corriendo. Inícialo con: sudo systemctl start docker"

    ok "git, openssl, curl, Docker ($COMPOSE_CMD) — todo ok"
}

# ── PASO 2: Descargar / localizar el repo ────────────────────────────────────
REPO_DIR=""

fetch_repo() {
    header "Localizando repositorio"


    if [ -f "site_finanzas/Dockerfile" ]; then
        REPO_DIR="."
        info "Repo ya presente en el directorio actual."
    elif [ -f "monetra/site_finanzas/Dockerfile" ]; then
        REPO_DIR="monetra"
        info "Repo ya presente en ./monetra/."
    else
        info "Clonando $REPO_URL (rama: $MONETRA_BRANCH)..."
        git clone --branch "$MONETRA_BRANCH" "$REPO_URL" monetra
        REPO_DIR="monetra"
        ok "Repositorio descargado en ./monetra/"
    fi
}

# ── PASO 4: Generar secretos ─────────────────────────────────────────────────
gen_hex()    { openssl rand -hex "$1" | tr -d '\r\n'; }
gen_fernet() {
    # Fernet: 32 bytes en base64 url-safe (44 chars)
    # tr -d '\r\n' elimina tanto LF como CRLF (necesario en Windows/Git Bash)
    openssl rand -base64 32 | tr '+/' '-_' | tr -d '\r\n'
}

# ── PASO 5: Escribir docker/.env ─────────────────────────────────────────────
write_env() {
    header "Configurando variables de entorno"

    ENV_FILE="$REPO_DIR/docker/.env"

    if [ -f "$ENV_FILE" ]; then
        warn "Ya existe $ENV_FILE — conservando secretos actuales."
        FRESH_ENV=false
        return 0
    fi

    info "Generando secretos automáticamente..."

    DB_PASSWORD=$(gen_hex 24)
    MYSQL_ROOT_PASSWORD=$(gen_hex 24)
    SECRET_KEY=$(gen_hex 32)
    JWT_SECRET_KEY=$(gen_hex 32)
    FIELD_ENCRYPTION_KEY=$(gen_fernet)

    cat > "$ENV_FILE" <<EOF
# === Base de datos (auto-generado por install.sh) ===
DB_NAME=monetra
DB_USER=monetra
DB_PASSWORD=${DB_PASSWORD}
MYSQL_ROOT_PASSWORD=${MYSQL_ROOT_PASSWORD}

# === Secretos de la app (auto-generados por install.sh) ===
SECRET_KEY=${SECRET_KEY}
FIELD_ENCRYPTION_KEY=${FIELD_ENCRYPTION_KEY}
JWT_SECRET_KEY=${JWT_SECRET_KEY}

# === Límites backup/restore (admin) ===
MAX_CONTENT_UPLOAD_MB=15
MAX_RESTORE_SQL_MB=500
EOF

    chmod 600 "$ENV_FILE"
    FRESH_ENV=true
    ok "docker/.env creado con secretos generados (permisos 600)."
}

# ── PASO 6: Construir imagen de producción ───────────────────────────────────
build_image() {
    header "Construyendo imagen de producción (monetra:release)"
    info "Esto puede tomar 2–5 minutos la primera vez..."
    docker build -t monetra:release "$REPO_DIR/site_finanzas"
    ok "Imagen monetra:release lista."
}

# ── PASO 7: Levantar servicios ───────────────────────────────────────────────
launch() {
    header "Levantando servicios"

    # Si los secretos son nuevos, limpiar volúmenes previos para evitar
    # "Access denied": MySQL persiste la contraseña en el volumen y no la
    # actualiza con datos existentes; secretos nuevos implica BD nueva.
    if [ "${FRESH_ENV:-false}" = "true" ]; then
        info "Limpiando volúmenes anteriores (nuevos secretos detectados)..."
        $COMPOSE_CMD \
            -f "$REPO_DIR/docker/docker-compose.prod.yml" \
            --env-file "$REPO_DIR/docker/.env" \
            down -v --remove-orphans 2>/dev/null || true
    fi

    $COMPOSE_CMD \
        -f "$REPO_DIR/docker/docker-compose.prod.yml" \
        --env-file "$REPO_DIR/docker/.env" \
        up -d
    ok "Contenedores iniciados."
}

# ── PASO 8: Esperar a que la app responda ────────────────────────────────────
wait_ready() {
    header "Esperando a que la app esté lista"
    local url="http://localhost:8085/"
    local max=24   # 24 × 5 s = 120 s
    local n=0

    info "Sondeando $url ..."
    until curl -sf -o /dev/null -w "%{http_code}" "$url" | grep -qE "^(200|302)$"; do
        n=$((n + 1))
        if [ "$n" -ge "$max" ]; then
            warn "La app no respondió en 120 s. Últimas líneas de log:"
            $COMPOSE_CMD \
                -f "$REPO_DIR/docker/docker-compose.prod.yml" \
                --env-file "$REPO_DIR/docker/.env" \
                logs --tail=30
            error "Tiempo de espera agotado. Revisa los logs de arriba."
        fi
        printf "."
        sleep 5
    done
    echo ""
    ok "La app está respondiendo."
}

# ── PASO 9: Resumen final ────────────────────────────────────────────────────
summary() {
    local access_url="http://localhost:8085"

    echo ""
    echo -e "${BOLD}${GREEN}╔══════════════════════════════════════════════════════════╗${RESET}"
    echo -e "${BOLD}${GREEN}║          Monetra instalado correctamente 🎉              ║${RESET}"
    echo -e "${BOLD}${GREEN}╚══════════════════════════════════════════════════════════╝${RESET}"
    echo ""
    echo -e "  ${BOLD}URL local:${RESET}     $access_url"
    echo -e "  ${BOLD}Configuración:${RESET} $REPO_DIR/docker/.env"
    echo ""
    echo -e "  ${YELLOW}Primer acceso:${RESET} ve a $access_url/register"
    echo -e "  El primer usuario que se registre quedará como administrador."
    echo ""
    echo -e "  ${CYAN}Comandos útiles:${RESET}"
    echo -e "    Logs:   $COMPOSE_CMD -f $REPO_DIR/docker/docker-compose.prod.yml logs -f"
    echo -e "    Parar:  $COMPOSE_CMD -f $REPO_DIR/docker/docker-compose.prod.yml down"
    echo ""
}

# ── Main ─────────────────────────────────────────────────────────────────────
main() {
    echo ""
    echo -e "${BOLD}${CYAN}Monetra — Instalación automática${RESET}"
    echo -e "Repositorio: $REPO_URL  •  Rama: $MONETRA_BRANCH"
    echo ""

    require_deps
    fetch_repo
    write_env
    build_image
    launch
    wait_ready
    summary
}

main "$@"
