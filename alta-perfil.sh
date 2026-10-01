#!/usr/bin/env bash
# Da de alta un perfil aislado de Claude Code en macOS o Linux.
#
# Crea la carpeta del perfil, le siembra el settings.json del perfil principal y
# escribe el launcher en ~/.local/bin. NO copia credenciales: el login lo hacés vos.
# Por defecto NO instala ninguna skill: la política es aislar.
# Es idempotente: si algo ya existe, lo deja como está y lo informa.
#
#   ./alta-perfil.sh trabajo
#   ./alta-perfil.sh trabajo --skills mi-skill,otra     # copias propias
#   ./alta-perfil.sh trabajo --skills mi-skill --enlazar # comparte con el origen
#   ORIGEN_SKILLS=~/mis-skills ./alta-perfil.sh trabajo
set -euo pipefail

NOMBRE=""
SKILLS=""
ENLAZAR=0
while [[ $# -gt 0 ]]; do
    case "$1" in
        --skills)  SKILLS="${2:-}"; shift 2 ;;
        --enlazar) ENLAZAR=1; shift ;;
        -h|--help) sed -n '2,12p' "$0"; exit 0 ;;
        *)         NOMBRE="$1"; shift ;;
    esac
done
if [[ ! "$NOMBRE" =~ ^[a-z0-9][a-z0-9-]*$ ]]; then
    echo "Uso: $0 <nombre-del-perfil> [--skills a,b] [--enlazar]" >&2
    exit 2
fi

PRINCIPAL="$HOME/.claude"
PERFIL="$HOME/.claude-$NOMBRE"
BIN="$HOME/.local/bin"
LAUNCHER="$BIN/claude-$NOMBRE"
ORIGEN_SKILLS="${ORIGEN_SKILLS:-$HOME/.agents/skills}"

[[ -d "$PRINCIPAL" ]] || {
    echo "No encuentro el perfil principal en $PRINCIPAL. Corré Claude Code al menos una vez antes." >&2
    exit 1
}

echo "Perfil: $PERFIL"

# ── 1. Carpeta del perfil ────────────────────────────────────────────────────
mkdir -p "$PERFIL"

# ── 2. settings.json (NUNCA las credenciales) ────────────────────────────────
if [[ -e "$PERFIL/settings.json" ]]; then
    echo "  settings.json ya existe, no lo toco"
elif [[ -f "$PRINCIPAL/settings.json" ]]; then
    cp "$PRINCIPAL/settings.json" "$PERFIL/settings.json"
    echo "  settings.json sembrado desde el perfil principal"
    echo "  ! Revisá que sus hooks no apunten por ruta absoluta a $PRINCIPAL"
else
    echo '{}' > "$PERFIL/settings.json"
    echo "  settings.json vacío (el principal no tenía uno)"
fi

# ── 3. Skills: ninguna salvo que se pidan, y por copia ──────────────────────
if [[ -z "$SKILLS" ]]; then
    echo "  sin skills (política: aislado; pedilas con --skills)"
else
    mkdir -p "$PERFIL/skills"
    IFS=',' read -r -a PEDIDAS <<< "$SKILLS"
    for s in "${PEDIDAS[@]}"; do
        s="${s// /}"
        [[ -z "$s" ]] && continue
        if [[ -e "$PERFIL/skills/$s" || -L "$PERFIL/skills/$s" ]]; then
            echo "  skill $s ya está"
        elif [[ ! -e "$ORIGEN_SKILLS/$s" ]]; then
            echo "  ! skill $s no existe en $ORIGEN_SKILLS"
        elif [[ $ENLAZAR -eq 1 ]]; then
            ln -s "$ORIGEN_SKILLS/$s" "$PERFIL/skills/$s"
            echo "  skill $s ENLAZADA (queda compartida con el origen)"
        else
            cp -R "$ORIGEN_SKILLS/$s" "$PERFIL/skills/$s"
            echo "  skill $s copiada"
        fi
    done
fi

# ── 4. Launcher ──────────────────────────────────────────────────────────────
mkdir -p "$BIN"
if [[ -e "$LAUNCHER" ]]; then
    echo "  launcher ya existe"
else
    cat > "$LAUNCHER" <<EOF
#!/bin/sh
# Perfil $NOMBRE de Claude Code: login, settings, historial y MCP aislados.
CLAUDE_CONFIG_DIR="\$HOME/.claude-$NOMBRE" exec claude "\$@"
EOF
    chmod +x "$LAUNCHER"
    echo "  launcher creado: $LAUNCHER"
fi

command -v "claude-$NOMBRE" >/dev/null 2>&1 \
    || echo "  ! $BIN no está en el PATH. Agregalo a tu perfil de shell."

# ── Verificación ─────────────────────────────────────────────────────────────
echo
echo "Verificación (antes del login no debe haber ningún MCP):"
CLAUDE_CONFIG_DIR="$PERFIL" claude mcp list || echo "  (no pude correr 'claude mcp list')"

echo
echo "Falta el login, una sola vez:"
echo "  claude-$NOMBRE      # adentro: /login"
