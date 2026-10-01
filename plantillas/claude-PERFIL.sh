#!/bin/sh
# ───────────────────────────────────────────────────────────────────────────
# Launcher de un perfil aislado de Claude Code (macOS / Linux).
#
# 1. Copiá este archivo a una carpeta del PATH, SIN extensión, por ejemplo
#    ~/.local/bin/claude-trabajo
# 2. Cambiá PERFIL por el nombre que elegiste.
# 3. chmod +x ~/.local/bin/claude-trabajo
#
# La asignación va en la misma línea del exec: la variable vive solo en ese
# proceso, así que podés tener varias cuentas abiertas en paralelo sin que se
# pisen.
# ───────────────────────────────────────────────────────────────────────────
CLAUDE_CONFIG_DIR="$HOME/.claude-PERFIL" exec claude "$@"
