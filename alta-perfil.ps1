<#
.SYNOPSIS
  Da de alta un perfil aislado de Claude Code en Windows.

.DESCRIPTION
  Crea la carpeta del perfil, le siembra el settings.json del perfil principal,
  enlaza por junction las mismas skills compartidas que tenga el principal, y
  escribe el launcher en ~/.local/bin. NO copia credenciales: el login lo hacés vos.

  Es idempotente: si algo ya existe, lo deja como está y lo informa.

.PARAMETER Nombre
  Sufijo del perfil. "trabajo" produce ~/.claude-trabajo y el comando claude-trabajo.

.PARAMETER Skills
  Qué skills instalar en el perfil. Por defecto NINGUNA: la política es aislar, y
  cada perfil arranca limpio. Se instalan por copia (quedan congeladas, a propósito).

.PARAMETER Enlazar
  En vez de copiar las skills de -Skills, enlazarlas al origen. Es compartir de
  verdad: el perfil queda acoplado al origen y el panel lo va a marcar.

.PARAMETER OrigenSkills
  Carpeta de donde salen las skills. Default: ~/.agents/skills

.EXAMPLE
  .\alta-perfil.ps1 trabajo
  .\alta-perfil.ps1 trabajo -Skills mi-skill,otra
  .\alta-perfil.ps1 trabajo -Skills mi-skill -Enlazar
#>
param(
    [Parameter(Mandatory = $true, Position = 0)]
    [ValidatePattern('^[a-z0-9][a-z0-9-]*$')]
    [string]$Nombre,

    [string[]]$Skills = @(),

    [switch]$Enlazar,

    [string]$OrigenSkills = (Join-Path $env:USERPROFILE '.agents\skills')
)

$ErrorActionPreference = 'Stop'

# La consola clásica de Windows (cp850/cp1252) no sabe pintar acentos y los deja
# ilegibles. Se fuerza UTF-8; si la consola no lo soporta, se sigue igual.
try { [Console]::OutputEncoding = [System.Text.Encoding]::UTF8 } catch {}

$principal = Join-Path $env:USERPROFILE '.claude'
$perfil    = Join-Path $env:USERPROFILE ".claude-$Nombre"
$binDir    = Join-Path $env:USERPROFILE '.local\bin'
$launcher  = Join-Path $binDir "claude-$Nombre.cmd"

if (-not (Test-Path $principal)) {
    throw "No encuentro el perfil principal en $principal. Corré Claude Code al menos una vez antes."
}

Write-Host "Perfil: $perfil" -ForegroundColor Cyan

# ── 1. Carpeta del perfil ────────────────────────────────────────────────────
New-Item -ItemType Directory -Force -Path $perfil | Out-Null

# ── 2. settings.json (NUNCA las credenciales) ────────────────────────────────
$destSettings = Join-Path $perfil 'settings.json'
if (Test-Path $destSettings) {
    Write-Host "  settings.json ya existe, no lo toco" -ForegroundColor DarkGray
} else {
    $origenSettings = Join-Path $principal 'settings.json'
    if (Test-Path $origenSettings) {
        Copy-Item $origenSettings $destSettings
        Write-Host "  settings.json sembrado desde el perfil principal" -ForegroundColor Green
        Write-Host "  ! Revisá que sus hooks no apunten por ruta absoluta a $principal" -ForegroundColor Yellow
    } else {
        '{}' | Set-Content -Path $destSettings -Encoding utf8
        Write-Host "  settings.json vacío (el principal no tenía uno)" -ForegroundColor DarkGray
    }
}

# ── 3. Skills: ninguna salvo que se pidan, y por copia ──────────────────────
if (-not $Skills) {
    Write-Host "  sin skills (política: aislado; pedilas con -Skills)" -ForegroundColor DarkGray
} else {
    $dirSkills = Join-Path $perfil 'skills'
    New-Item -ItemType Directory -Force -Path $dirSkills | Out-Null
    foreach ($s in $Skills) {
        $destino = Join-Path $dirSkills $s
        $fuente  = Join-Path $OrigenSkills $s
        if (Test-Path $destino) {
            Write-Host "  skill $s ya está" -ForegroundColor DarkGray
        } elseif (-not (Test-Path $fuente)) {
            Write-Host "  ! skill $s no existe en $OrigenSkills" -ForegroundColor Yellow
        } elseif ($Enlazar) {
            New-Item -ItemType Junction -Path $destino -Target $fuente | Out-Null
            Write-Host "  skill $s ENLAZADA (queda compartida con el origen)" -ForegroundColor Yellow
        } else {
            Copy-Item -Recurse $fuente $destino
            Write-Host "  skill $s copiada" -ForegroundColor Green
        }
    }
}

# ── 4. Launcher ──────────────────────────────────────────────────────────────
New-Item -ItemType Directory -Force -Path $binDir | Out-Null
if (Test-Path $launcher) {
    Write-Host "  launcher ya existe" -ForegroundColor DarkGray
} else {
    @"
@echo off
REM Perfil $Nombre de Claude Code: login, settings, historial y MCP aislados.
setlocal
set "CLAUDE_CONFIG_DIR=%USERPROFILE%\.claude-$Nombre"
claude %*
"@ | Set-Content -Path $launcher -Encoding ascii
    Write-Host "  launcher creado: $launcher" -ForegroundColor Green
}

if (-not (Get-Command "claude-$Nombre" -ErrorAction SilentlyContinue)) {
    Write-Host "  ! $binDir no está en el PATH. Agregalo o invocá el .cmd por ruta completa." -ForegroundColor Yellow
}

# ── Verificación ─────────────────────────────────────────────────────────────
Write-Host ""
Write-Host "Verificación (antes del login no debe haber ningún MCP):" -ForegroundColor Cyan
$env:CLAUDE_CONFIG_DIR = $perfil
try { claude mcp list } catch { Write-Host "  (no pude correr 'claude mcp list': $_)" -ForegroundColor DarkGray }
Remove-Item Env:\CLAUDE_CONFIG_DIR -ErrorAction SilentlyContinue

Write-Host ""
Write-Host "Falta el login, una sola vez:" -ForegroundColor Cyan
Write-Host "  claude-$Nombre      # adentro: /login"
