#!/usr/bin/env python3
# /// script
# requires-python = ">=3.10"
# dependencies = []
# ///
"""Panel de cuentas de Claude Code · dibuja en un HTML qué perfiles de Claude Code hay en
esta máquina, con qué cuenta está logueado cada uno, qué queda aislado, dónde derivaron las
skills y qué está pendiente. Solo LEE. No usa internet, no pide claves, no cambia nada.

  python panel-cuentas.py                  # deja el HTML en la carpeta actual
  python panel-cuentas.py --salida x.html  # dónde dejar el HTML
  python panel-cuentas.py --anonimo        # tapa mails y nombre de usuario (para compartir)
  python panel-cuentas.py --json           # además, un JSON con todo lo encontrado
  python panel-cuentas.py --origen-skills ~/mis-skills

Funciona en Windows (junctions), macOS y Linux (symlinks). Doc: README.md de este repo.
"""
import argparse
import datetime as dt
import hashlib
import html
import json
import os
import sys
from pathlib import Path

for _f in (sys.stdout, sys.stderr):
    try:
        _f.reconfigure(encoding="utf-8", errors="replace")
    except (AttributeError, ValueError):
        pass

CASA = Path.home()
SEP = chr(92)  # separador de Windows, sin pelear con los escapes
HOY = dt.date.today()
VERSION = "0.1"
# Carpeta de skills compartidas, si usás una. Se cambia con --origen-skills.
ORIGEN_SKILLS = CASA / ".agents" / "skills"
LANZADORES = CASA / ".local" / "bin"


# ─────────────────────────────── lectura ───────────────────────────────

def leer_json(ruta: Path):
    try:
        return json.loads(ruta.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None


def clase_enlace(ruta: Path) -> tuple[str, str]:
    """('junction', destino) · ('copia', '') · ('ausente', '')"""
    if not ruta.exists():
        return "ausente", ""
    try:
        destino = os.readlink(ruta)
        return "junction", destino.replace("\\\\?\\", "")
    except OSError:
        return "copia", ""


def hallar_perfiles() -> list[Path]:
    """Toda carpeta ~/.claude o ~/.claude-* que tenga settings.json o .claude.json."""
    salida = []
    for d in sorted(CASA.glob(".claude*")):
        if not d.is_dir():
            continue
        if (d / "settings.json").exists() or (d / ".claude.json").exists():
            salida.append(d)
    return salida


def contar_hooks(settings: dict) -> tuple[int, int]:
    hooks = settings.get("hooks") or {}
    eventos = len(hooks)
    comandos = 0
    for lista in hooks.values():
        for grupo in lista if isinstance(lista, list) else []:
            comandos += len(grupo.get("hooks") or [])
    return eventos, comandos


def hooks_a_otros_perfiles(settings: dict, perfil: Path) -> list[dict]:
    """Comandos de hook que apuntan a un archivo de OTRO perfil: la dependencia invisible.

    Devuelve un registro por comando (evento, perfil ajeno, script) para poder decir
    "1 de 14" en vez de dar a entender que todo el settings.json es prestado.
    """
    fuera = []
    hooks = settings.get("hooks") or {}
    propio = str(perfil).lower()
    otros = [p for p in CASA.glob(".claude*")
             if p.is_dir() and str(p).lower() != propio]
    for evento, lista in hooks.items():
        for grupo in lista if isinstance(lista, list) else []:
            for h in grupo.get("hooks") or []:
                cmd = h.get("command") or ""
                low = cmd.lower()
                for otro in otros:
                    base = str(otro).lower()
                    # Exigir el separador: ".claude" es prefijo de ".claude-trabajo",
                    # y sin esto un hook propio se reportaría como ajeno.
                    if (base + SEP) in low or (base + "/") in low:
                        script = cmd.replace("/", SEP).split(SEP)[-1].split(chr(34))[0]
                        fuera.append({"evento": evento, "perfil": otro.name, "script": script})
                        break
    return fuera


def datos_perfil(d: Path) -> dict:
    es_default = d.name == ".claude"
    sufijo = "" if es_default else d.name.replace(".claude-", "")
    lanzador = "claude" if es_default else f"claude-{sufijo}"
    # Windows usa .cmd/.bat; macOS y Linux, un script sin extensión.
    candidatos = [] if es_default else [LANZADORES / f"{lanzador}{x}" for x in (".cmd", ".bat", "")]
    archivo_lanzador = next((c for c in candidatos if c.exists()), None)

    settings = leer_json(d / "settings.json") or {}
    # El perfil default guarda su estado en ~/.claude.json (fuera de la carpeta);
    # los perfiles con CLAUDE_CONFIG_DIR lo guardan adentro.
    estado = leer_json(CASA / ".claude.json" if es_default else d / ".claude.json") or {}
    cuenta = estado.get("oauthAccount") or {}

    proyectos_dir = d / "projects"
    sesiones = list(proyectos_dir.glob("*/*.jsonl")) if proyectos_dir.is_dir() else []
    ult = max((s.stat().st_mtime for s in sesiones), default=0)

    skills = {}
    dir_skills = d / "skills"
    if dir_skills.is_dir():
        for s in sorted(dir_skills.iterdir()):
            if s.name == "synced":
                continue
            clase, destino = clase_enlace(s)
            skills[s.name] = {"clase": clase, "destino": destino}

    eventos, comandos = contar_hooks(settings)
    raw = (d / "settings.json").read_bytes() if (d / "settings.json").exists() else b""

    return {
        "carpeta": d.name,
        "ruta": str(d),
        "lanzador": lanzador,
        "lanzador_ok": True if es_default else archivo_lanzador is not None,
        "es_default": es_default,
        "email": cuenta.get("emailAddress") or "",
        "org_tipo": cuenta.get("organizationType") or "",
        "org_rol": cuenta.get("organizationRole") or "",
        "logueado": bool(cuenta.get("emailAddress")),
        "mcp": sorted((estado.get("mcpServers") or {}).keys()),
        "proyectos": len([p for p in proyectos_dir.iterdir() if p.is_dir()]) if proyectos_dir.is_dir() else 0,
        "sesiones": len(sesiones),
        "ultima_sesion": dt.datetime.fromtimestamp(ult).strftime("%Y-%m-%d %H:%M") if ult else "",
        "settings_bytes": len(raw),
        "settings_hash": hashlib.sha256(raw).hexdigest()[:8] if raw else "",
        "hook_eventos": eventos,
        "hook_comandos": comandos,
        "hooks_prestados": hooks_a_otros_perfiles(settings, d),
        "modo_permisos": (settings.get("permissions") or {}).get("defaultMode") or "(sin fijar)",
        "skills": skills,
        "github_web": ((estado.get("githubWebConnectionStatusCache") or {}).get("status") or "—"),
        "remote_control": bool(estado.get("hasUsedRemoteControl")),
        "integracion_herdr": (d / "hooks" / "herdr-agent-state.ps1").exists(),
    }


def capa_compartida(raiz_vault: Path) -> dict:
    def git(*args):
        import subprocess
        try:
            r = subprocess.run(["git", *args], capture_output=True, text=True, timeout=10)
            return r.stdout.strip()
        except Exception:
            return ""

    return {
        "git_nombre": git("config", "--global", "user.name"),
        "git_email": git("config", "--global", "user.email"),
        "mcp_json_proyecto": (raiz_vault / ".mcp.json").exists(),
        "settings_proyecto": (raiz_vault / ".claude" / "settings.json").exists(),
        "origen_skills": sorted(p.name for p in ORIGEN_SKILLS.iterdir()) if ORIGEN_SKILLS.is_dir() else [],
    }


# ─────────────────────────────── diagnóstico ───────────────────────────────

def diagnosticar(perfiles: list[dict], compartida: dict, politica: str = "aislado") -> list[dict]:
    """Reglas deterministas. severidad: alta | media | baja

    La política cambia qué cuenta como defecto:
      aislado    (default) nada se comparte entre perfiles salvo que lo pidas.
                 Lo anómalo es que DOS perfiles apunten al mismo origen.
      compartido las skills se mantienen en un origen común y cada perfil lo
                 enlaza. Lo anómalo es una copia, que queda congelada.
    """
    out = []
    ref = next((p for p in perfiles if p["es_default"]), perfiles[0] if perfiles else None)

    # Qué destino de enlace aparece en más de un perfil: eso sí es compartir.
    destinos: dict[str, list[str]] = {}
    for p in perfiles:
        for nombre, v in p["skills"].items():
            if v["clase"] == "junction" and v["destino"]:
                destinos.setdefault(v["destino"], []).append(p["carpeta"])

    for p in perfiles:
        if not p["logueado"]:
            out.append({"sev": "alta", "perfil": p["carpeta"],
                        "que": "Perfil sin login",
                        "detalle": f"`{p['lanzador']}` arranca sin cuenta. Correrlo y hacer /login."})
        if not p["lanzador_ok"]:
            out.append({"sev": "alta", "perfil": p["carpeta"],
                        "que": "Falta el launcher",
                        "detalle": f"No hay ningún `{p['lanzador']}` en `{LANZADORES}`. Sin él hay que exportar CLAUDE_CONFIG_DIR a mano."})

        if politica == "aislado":
            compartidas = sorted(n for n, v in p["skills"].items()
                                 if v["clase"] == "junction" and len(destinos.get(v["destino"], [])) > 1)
            if compartidas:
                otros = sorted({c for n in compartidas
                                for c in destinos[p["skills"][n]["destino"]] if c != p["carpeta"]})
                out.append({"sev": "media", "perfil": p["carpeta"],
                            "que": f"{len(compartidas)} skill(s) compartidas con otro perfil",
                            "detalle": "Enlazadas al mismo origen que " + ", ".join(f"`{o}`" for o in otros) +
                                       ": " + ", ".join(f"`{c}`" for c in compartidas) +
                                       ". La política es aislar — si las querés acá, que sean copias propias."})
        else:
            copias = [k for k, v in p["skills"].items() if v["clase"] == "copia"]
            if copias:
                out.append({"sev": "media", "perfil": p["carpeta"],
                            "que": f"{len(copias)} skill(s) copiadas en vez de enlazadas",
                            "detalle": "Congeladas, no reciben actualizaciones: " + ", ".join(f"`{c}`" for c in copias)})
            if ref and p is not ref:
                faltan = sorted(set(ref["skills"]) - set(p["skills"]))
                if faltan:
                    out.append({"sev": "media", "perfil": p["carpeta"],
                                "que": f"{len(faltan)} skill(s) que el perfil de referencia sí tiene",
                                "detalle": ", ".join(f"`{f}`" for f in faltan)})

        if p["hooks_prestados"]:
            n = len(p["hooks_prestados"])
            cuales = " · ".join(f'`{h["evento"]}` → `{h["script"]}` (en `{h["perfil"]}`)'
                                for h in p["hooks_prestados"])
            out.append({# Un hook de integración prestado es una molestia; varios, un acoplamiento.
                        "sev": "baja" if n == 1 else "media",
                        "perfil": p["carpeta"],
                        "que": f"{n} de {p['hook_comandos']} comandos de hook apuntan a otro perfil",
                        "detalle": cuales +
                                   ". Funciona mientras ese perfil exista: si se limpia o se renombra, "
                                   "este hook se rompe en silencio. Se corrige instalando la integración "
                                   "dentro del perfil, o copiándole el script a su propio `hooks/`."})
        if p["logueado"] and not p["integracion_herdr"]:
            out.append({"sev": "baja", "perfil": p["carpeta"],
                        "que": "Integración de Herdr no instalada en el perfil",
                        "detalle": f'CLAUDE_CONFIG_DIR="{p["ruta"]}" herdr integration install claude'})
        if p["modo_permisos"] == "auto":
            out.append({"sev": "baja", "perfil": p["carpeta"],
                        "que": "Modo de permisos `auto`",
                        "detalle": "Edita y ejecuta sin preguntar. En repos sin reglas de proyecto, no hay red de contención."})
        if p["remote_control"]:
            out.append({"sev": "baja", "perfil": p["carpeta"],
                        "que": "Remote Control usado en este perfil",
                        "detalle": "Es el camino por el que una sesión web alcanza una terminal local."})

    if ref and politica == "compartido":
        huerfanas = sorted(set(compartida["origen_skills"]) - set(ref["skills"]))
        if huerfanas:
            out.append({"sev": "baja", "perfil": "—",
                        "que": f"{len(huerfanas)} skill(s) en el origen sin enlazar en ningún perfil",
                        "detalle": ", ".join(f"`{h}`" for h in huerfanas)})

    orden = {"alta": 0, "media": 1, "baja": 2}
    return sorted(out, key=lambda x: (orden[x["sev"]], x["perfil"]))


def anonimizar(datos: dict) -> dict:
    """Tapa todo lo que identifica: mails, nombre del usuario, nombre de cada perfil
    («trabajo» ya dice de quién es) y nombres de servidores MCP."""
    mapa = {}
    for i, p in enumerate(datos["perfiles"], 1):
        if p["email"]:
            mapa[p["email"]] = f"cuenta{i}@ejemplo.com"
        if not p["es_default"]:
            sufijo = p["carpeta"].replace(".claude-", "", 1)
            if sufijo:
                mapa[sufijo] = f"perfil{i}"
        for j, m in enumerate(p["mcp"], 1):
            mapa.setdefault(m, f"mcp-{j}")
    ge = datos["compartida"].get("git_email")
    if ge and ge not in mapa:  # si ya es el mail de un perfil, ese alias manda
        mapa[ge] = "git@ejemplo.com"
    gn = datos["compartida"].get("git_nombre")
    if gn:
        mapa[gn] = "usuario"
    mapa.setdefault(CASA.name, "usuario")
    s = json.dumps(datos, ensure_ascii=False)
    # De más largo a más corto: evita que un alias corto parta a uno que lo contiene.
    for viejo in sorted(mapa, key=len, reverse=True):
        s = s.replace(viejo, mapa[viejo])
    return json.loads(s)


# ─────────────────────────────── HTML ───────────────────────────────

CSS = """
:root{--bg:#fbfaf8;--panel:#fff;--txt:#1a1a18;--sut:#6b6a66;--bor:#e5e2dc;
--ok:#2d7a4f;--warn:#9a6a00;--bad:#b3261e;--acc:#3f5fa8;--code:#f3f1ec}
@media (prefers-color-scheme:dark){:root:not([data-theme=light]){--bg:#15161a;--panel:#1c1e23;
--txt:#e8e6e1;--sut:#9a9892;--bor:#2d3037;--ok:#6cc08b;--warn:#d9a53b;--bad:#f08b82;
--acc:#8fa9e0;--code:#23262c}}
:root[data-theme=dark]{--bg:#15161a;--panel:#1c1e23;--txt:#e8e6e1;--sut:#9a9892;--bor:#2d3037;
--ok:#6cc08b;--warn:#d9a53b;--bad:#f08b82;--acc:#8fa9e0;--code:#23262c}
*{box-sizing:border-box}
body{margin:0;background:var(--bg);color:var(--txt);font:15px/1.55 ui-sans-serif,system-ui,-apple-system,"Segoe UI",sans-serif}
.wrap{max-width:1180px;margin:0 auto;padding:40px 16px 72px}
h1{font-size:28px;margin:0 0 4px;letter-spacing:-.02em}
h2{font-size:17px;margin:40px 0 14px;letter-spacing:-.01em}
h2 .n{color:var(--sut);font-weight:400;font-size:14px;margin-left:8px}
.sub{color:var(--sut);font-size:13px;margin:0 0 8px}
code,.mono{font-family:ui-monospace,SFMono-Regular,Consolas,monospace;font-size:.88em}
code{background:var(--code);padding:1px 5px;border-radius:4px}
.grid{display:grid;gap:14px;grid-template-columns:repeat(auto-fit,minmax(310px,1fr))}
.card{background:var(--panel);border:1px solid var(--bor);border-radius:10px;padding:16px 18px}
.card h3{margin:0 0 2px;font-size:16px;display:flex;align-items:center;gap:8px;flex-wrap:wrap}
.card .ruta{color:var(--sut);font-size:12px;margin-bottom:12px}
.kv{display:grid;grid-template-columns:auto 1fr;gap:3px 12px;font-size:13px}
.kv dt{color:var(--sut)}
.kv dd{margin:0;overflow-wrap:anywhere}
.pill{font-size:11px;padding:2px 8px;border-radius:99px;border:1px solid var(--bor);color:var(--sut);white-space:nowrap}
.pill.ok{color:var(--ok);border-color:currentColor}
.pill.warn{color:var(--warn);border-color:currentColor}
.pill.bad{color:var(--bad);border-color:currentColor}
table{width:100%;border-collapse:collapse;font-size:13px;background:var(--panel);
border:1px solid var(--bor);border-radius:10px;overflow:hidden}
th,td{text-align:left;padding:9px 12px;border-bottom:1px solid var(--bor)}
th{font-weight:600;font-size:12px;color:var(--sut);text-transform:uppercase;letter-spacing:.04em}
tr:last-child td{border-bottom:0}
.c{text-align:center}
.diag{background:var(--panel);border:1px solid var(--bor);border-radius:10px;padding:2px 0}
.diag .it{display:flex;gap:12px;padding:13px 18px;border-bottom:1px solid var(--bor)}
.diag .it:last-child{border-bottom:0}
.diag .sev{flex:0 0 58px;font-size:11px;text-transform:uppercase;letter-spacing:.04em;padding-top:2px}
.sev.alta{color:var(--bad)}.sev.media{color:var(--warn)}.sev.baja{color:var(--sut)}
.diag .cuerpo{flex:1}
.diag .que{font-weight:600;margin-bottom:2px}
.diag .det{color:var(--sut);font-size:13px}
.diag .perfil{color:var(--acc);font-size:12px;font-family:ui-monospace,monospace}
footer{margin-top:48px;padding-top:18px;border-top:1px solid var(--bor);color:var(--sut);font-size:12px}
.nota{background:var(--panel);border:1px solid var(--bor);border-left:3px solid var(--acc);
border-radius:8px;padding:12px 16px;font-size:13px;color:var(--sut);margin:14px 0}
@media(max-width:560px){.wrap{padding:24px 16px 56px}h1{font-size:23px}}
"""


def e(x) -> str:
    return html.escape(str(x))


def tarjeta(p: dict) -> str:
    pill_login = ('<span class="pill ok">logueado</span>' if p["logueado"]
                  else '<span class="pill bad">sin login</span>')
    pill_lanz = ("" if p["lanzador_ok"] else '<span class="pill bad">sin launcher</span>')
    mcp = ", ".join(f"<code>{e(m)}</code>" for m in p["mcp"]) or '<span class="pill ok">ninguno</span>'
    copias = sum(1 for v in p["skills"].values() if v["clase"] == "copia")
    sk = f'{len(p["skills"])} enlazadas' if not copias else f'{len(p["skills"])} · <span class="pill warn">{copias} copiadas</span>'
    return f"""<div class="card">
<h3><code>{e(p['lanzador'])}</code> {pill_login}{pill_lanz}</h3>
<div class="ruta mono">{e(p['ruta'])}</div>
<dl class="kv">
<dt>Cuenta</dt><dd>{e(p['email']) or '—'}</dd>
<dt>Plan / rol</dt><dd>{e(p['org_tipo']) or '—'} · {e(p['org_rol']) or '—'}</dd>
<dt>MCP de usuario</dt><dd>{mcp}</dd>
<dt>Historial</dt><dd>{p['sesiones']} sesiones en {p['proyectos']} proyectos{(' · última ' + e(p['ultima_sesion'])) if p['ultima_sesion'] else ''}</dd>
<dt>Hooks</dt><dd>{p['hook_eventos']} eventos / {p['hook_comandos']} comandos</dd>
<dt>settings.json</dt><dd>{p['settings_bytes']} B · <span class="mono">{e(p['settings_hash'])}</span></dd>
<dt>Permisos</dt><dd><code>{e(p['modo_permisos'])}</code></dd>
<dt>Skills</dt><dd>{sk}</dd>
<dt>GitHub web</dt><dd>{e(p['github_web'])}</dd>
<dt>Remote Control</dt><dd>{'usado' if p['remote_control'] else 'sin usar'}</dd>
<dt>Hook de Herdr</dt><dd>{'propio' if p['integracion_herdr'] else 'prestado o ausente'}</dd>
</dl></div>"""


def matriz_skills(perfiles: list[dict], origen: list[str]) -> str:
    nombres = sorted(set(origen) | {k for p in perfiles for k in p["skills"]})
    cab = "".join(f"<th class='c'>{e(p['lanzador'])}</th>" for p in perfiles)
    filas = []
    for n in nombres:
        celdas = []
        for p in perfiles:
            v = p["skills"].get(n)
            if not v:
                celdas.append("<td class='c'><span class='pill'>—</span></td>")
            elif v["clase"] == "junction":
                celdas.append("<td class='c'><span class='pill ok'>enlace</span></td>")
            else:
                celdas.append("<td class='c'><span class='pill warn'>copia</span></td>")
        en_origen = "✓" if n in origen else "—"
        filas.append(f"<tr><td><code>{e(n)}</code></td><td class='c'>{en_origen}</td>{''.join(celdas)}</tr>")
    return f"""<table><thead><tr><th>Skill</th><th class='c'>En el origen</th>{cab}</tr></thead>
<tbody>{''.join(filas)}</tbody></table>"""


AISLAMIENTO = [
    ("Login / cuenta", "archivo de credenciales del perfil", "si"),
    ("MCP de usuario", "<code>.claude.json</code> del perfil", "si"),
    ("Historial de sesiones", "<code>projects/</code> del perfil", "si"),
    ("Plugins", "<code>plugins/</code> del perfil", "si"),
    ("Conectores de claude.ai", "atados a la cuenta", "si"),
    ("Hooks de usuario", "<code>settings.json</code> del perfil", "copia"),
    ("Skills", "<code>skills/</code> del perfil", "copia"),
    ("Hooks de proyecto", "<code>.claude/settings.json</code> del repo", "no"),
    ("Permisos, comandos, agentes", "<code>.claude/</code> del repo", "no"),
    ("MCP de proyecto", "<code>.mcp.json</code> del repo", "no"),
    ("Identidad de git", "<code>git config user.email</code>", "no"),
    ("Token de GitHub", "keyring de Windows", "no"),
    ("Sistema de archivos", "el disco", "no"),
]


def tabla_aislamiento(compartida: dict) -> str:
    marca = {"si": '<span class="pill ok">aislado</span>',
             "copia": '<span class="pill warn">copiado, no compartido</span>',
             "no": '<span class="pill bad">compartido</span>'}
    filas = "".join(f"<tr><td>{c}</td><td>{d}</td><td>{marca[m]}</td></tr>" for c, d, m in AISLAMIENTO)
    extra = (f'<div class="nota">Identidad de git en esta máquina: '
             f'<code>{e(compartida["git_nombre"])} &lt;{e(compartida["git_email"])}&gt;</code> — '
             f'la misma para todas las cuentas. En este repo '
             f'{"<b>sí</b> hay" if compartida["mcp_json_proyecto"] else "<b>no</b> hay"} '
             f'<code>.mcp.json</code> (MCP de proyecto, visible para todos los perfiles) y '
             f'{"<b>sí</b> hay" if compartida["settings_proyecto"] else "<b>no</b> hay"} '
             f'<code>.claude/settings.json</code> (hooks y permisos compartidos).</div>')
    return f"""<table><thead><tr><th>Capa</th><th>Dónde vive</th><th>Entre perfiles</th></tr></thead>
<tbody>{filas}</tbody></table>{extra}"""


def diagnostico_html(d: list[dict]) -> str:
    if not d:
        return '<div class="diag"><div class="it"><div class="sev baja">ok</div><div class="cuerpo"><div class="que">Nada que reportar.</div></div></div></div>'
    its = "".join(
        f'<div class="it"><div class="sev {x["sev"]}">{x["sev"]}</div><div class="cuerpo">'
        f'<div class="que">{e(x["que"])}</div>'
        f'<div class="det">{x["detalle"]}</div>'
        f'<div class="perfil">{e(x["perfil"])}</div></div></div>' for x in d)
    return f'<div class="diag">{its}</div>'


def construir_html(datos: dict) -> str:
    ps = datos["perfiles"]
    comp = datos["compartida"]
    diag = datos["diagnostico"]
    altas = sum(1 for x in diag if x["sev"] == "alta")
    resumen = (f'{len(ps)} perfiles · {sum(1 for p in ps if p["logueado"])} con login · '
               f'{len(diag)} observaciones' + (f' ({altas} de severidad alta)' if altas else '') +
               f' · política: {datos.get("politica", "aislado")}')
    return f"""<!DOCTYPE html>
<html lang="es"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>Panel de cuentas</title><style>{CSS}</style></head>
<body><div class="wrap">
<h1>Panel de cuentas de Claude Code</h1>
<p class="sub">{e(resumen)} · generado el {HOY.isoformat()} · v{VERSION}</p>

<h2>Perfiles<span class="n">una carpeta y un comando por cuenta</span></h2>
<div class="grid">{''.join(tarjeta(p) for p in ps)}</div>

<h2>Skills: enlace o copia<span class="n">una copia queda congelada y deriva</span></h2>
{matriz_skills(ps, comp["origen_skills"])}

<h2>Qué se aísla y qué no<span class="n">la frontera es de configuración, no de sandbox</span></h2>
{tabla_aislamiento(comp)}

<h2>Diagnóstico<span class="n">reglas deterministas sobre el estado de arriba</span></h2>
{diagnostico_html(diag)}

<footer>Generado por <code>panel-cuentas.py</code> — solo lectura, sin red. Doc: <code>README.md</code>.</footer>
</div></body></html>"""


# ─────────────────────────────── main ───────────────────────────────

def main() -> int:
    ap = argparse.ArgumentParser(description="Panel de cuentas de Claude Code (solo lectura).")
    ap.add_argument("--raiz", default=".", help="carpeta de proyecto a inspeccionar (.mcp.json, settings de proyecto); default: la actual")
    ap.add_argument("--salida", help="ruta del HTML (default: <raiz>/panel-cuentas.html)")
    ap.add_argument("--origen-skills", help="carpeta de skills compartidas (default: ~/.agents/skills)")
    ap.add_argument("--json", action="store_true", help="escribir también el JSON")
    ap.add_argument("--anonimo", action="store_true", help="tapar mails y nombre de usuario")
    ap.add_argument("--politica", choices=("aislado", "compartido"), default="aislado",
                    help="aislado (default): nada se comparte entre perfiles salvo que lo pidas. "
                         "compartido: las skills viven en un origen común y cada perfil lo enlaza.")
    a = ap.parse_args()

    raiz = Path(a.raiz).resolve()
    if a.origen_skills:
        global ORIGEN_SKILLS
        ORIGEN_SKILLS = Path(a.origen_skills).expanduser().resolve()
    perfiles = [datos_perfil(d) for d in hallar_perfiles()]
    if not perfiles:
        print("No encontré ningún perfil de Claude Code en ~/.claude*", file=sys.stderr)
        return 1
    comp = capa_compartida(raiz)
    datos = {"generado": HOY.isoformat(), "version": VERSION,
             "perfiles": perfiles, "compartida": comp,
             "politica": a.politica,
             "diagnostico": diagnosticar(perfiles, comp, a.politica)}
    if a.anonimo:
        datos = anonimizar(datos)

    salida = Path(a.salida) if a.salida else raiz / "panel-cuentas.html"
    salida.write_text(construir_html(datos), encoding="utf-8")
    print(f"✓ {salida}  ({salida.stat().st_size} bytes)")
    if a.json:
        j = salida.with_suffix(".json")
        j.write_text(json.dumps(datos, ensure_ascii=False, indent=1), encoding="utf-8")
        print(f"✓ {j}")
    for x in datos["diagnostico"]:
        if x["sev"] == "alta":
            print(f"  ! {x['perfil']}: {x['que']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
