@echo off
REM ───────────────────────────────────────────────────────────────────────────
REM Launcher de un perfil aislado de Claude Code (Windows).
REM
REM 1. Copiá este archivo a una carpeta del PATH, por ejemplo
REM    %USERPROFILE%\.local\bin\claude-trabajo.cmd
REM 2. Cambiá PERFIL por el nombre que elegiste.
REM
REM "setlocal" acota la variable a este proceso: la terminal desde la que lo
REM invocás no queda contaminada, así que podés tener varias cuentas abiertas
REM en paralelo sin que se pisen.
REM ───────────────────────────────────────────────────────────────────────────
setlocal
set "CLAUDE_CONFIG_DIR=%USERPROFILE%\.claude-PERFIL"
claude %*
