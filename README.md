# Varias cuentas de Claude Code en la misma máquina

Correr dos o más suscripciones de Claude Code en la misma computadora, **sin deslogear ni relogear**, y sin que una cuenta vea los MCP, el historial ni las decisiones de confianza de la otra.

Acá está el método, el procedimiento de alta, un panel HTML que audita el montaje, y lo que descubrí probando las alternativas. Todo verificado en una máquina real, no deducido de la documentación.

**La postura por defecto es aislar:** nada se comparte entre perfiles —ni skills, ni MCP, ni hooks— salvo que lo pidas explícitamente, caso por caso. Entre dos perfiles que divergen y dos perfiles acoplados, este repo elige que divergan, y te da la herramienta para enterarte cuándo pasa.

```
┌─ claude            → ~/.claude            cuenta personal
├─ claude-trabajo    → ~/.claude-trabajo    cuenta de la empresa
└─ claude-cliente    → ~/.claude-cliente    cuenta de un cliente
```

Tres comandos, tres carpetas, una sola instalación de Claude Code. Corren en paralelo.

---

## Índice

1. [El mecanismo](#1-el-mecanismo)
2. [Alta de un perfil](#2-alta-de-un-perfil)
3. [Uso diario](#3-uso-diario)
4. [El panel de auditoría](#4-el-panel-de-auditoría)
5. [Qué se aísla y qué no](#5-qué-se-aísla-y-qué-no)
6. [Seguridad: la frontera es de configuración, no de sandbox](#6-seguridad-la-frontera-es-de-configuración-no-de-sandbox)
7. [Uso con un multiplexor (Herdr)](#7-uso-con-un-multiplexor-herdr)
8. [Alternativas que probé y descarté](#8-alternativas-que-probé-y-descarté)
9. [Handoff entre cuentas](#9-handoff-entre-cuentas)
10. [Las tres trampas](#10-las-tres-trampas)

---

## 1. El mecanismo

Claude Code lee toda su configuración de `~/.claude`. La variable de entorno **`CLAUDE_CONFIG_DIR`** reubica esa raíz: settings, credenciales, historial de sesiones, servidores MCP de usuario y plugins.

Dos valores distintos = **dos instalaciones lógicas independientes** que conviven. El binario es uno solo; lo único que cambia es de qué carpeta lee la sesión.

No hace falta ningún programa extra. Un archivo de dos líneas por cuenta alcanza:

**Windows** — `~/.local/bin/claude-trabajo.cmd`

```cmd
@echo off
setlocal
set "CLAUDE_CONFIG_DIR=%USERPROFILE%\.claude-trabajo"
claude %*
```

**macOS / Linux** — `~/.local/bin/claude-trabajo`

```sh
#!/bin/sh
CLAUDE_CONFIG_DIR="$HOME/.claude-trabajo" exec claude "$@"
```

`setlocal` (y la asignación en línea en sh) acotan la variable a ese proceso: la terminal desde la que invocás no queda contaminada.

Las plantillas están en [`plantillas/`](plantillas/).

---

## 2. Alta de un perfil

Hay un script por plataforma que hace los cuatro pasos. Toma el nombre del perfil como argumento:

```powershell
# Windows
.\alta-perfil.ps1 trabajo
```

```bash
# macOS / Linux
./alta-perfil.sh trabajo
```

Después, una sola vez:

```bash
claude-trabajo      # adentro: /login
```

### Qué hace, paso por paso

**1. Crea la carpeta y siembra los settings.**

```powershell
Copy-Item "$HOME\.claude\settings.json" "$HOME\.claude-trabajo\settings.json"
```

Se copia **solo `settings.json`** (hooks, modelo, statusLine, permisos). **Nunca el archivo de credenciales**: cada perfil hace su propio login. Copiarlo anularía el aislamiento y duplicaría un secreto.

**2. Skills: ninguna, salvo que la pidas.**

Un perfil nuevo arranca **sin skills**. Si alguna hace falta en esa cuenta, se instala por **copia**:

```powershell
.\alta-perfil.ps1 trabajo -Skills mi-skill,otra-skill
```

```bash
./alta-perfil.sh trabajo --skills mi-skill,otra-skill
```

La copia queda congelada, y eso es deliberado: **la deriva es el precio de no estar acoplado**. El panel de la sección 4 la detecta comparando contra el origen, sin que haya ningún enlace de por medio.

Si en algún caso puntual preferís el **enlace vivo** —una skill que querés mantener en un solo lugar y que todos los perfiles vean actualizada— es una decisión explícita:

```powershell
.\alta-perfil.ps1 trabajo -Skills mi-skill -Enlazar
```

El panel la va a marcar como *compartida con otro perfil*. Eso está bien: la marca para que sea una decisión visible y no un accidente.

### Las dos políticas

| | **aislado** (default) | **compartido** |
|---|---|---|
| Skills | copia propia por perfil | un origen común, enlazado |
| Qué cuesta | derivan; hay que enterarse | un perfil depende de otro |
| Qué marca el panel | que dos perfiles apunten al mismo origen | una copia congelada |
| Flag del panel | `--politica aislado` | `--politica compartido` |

Elegí una y que el panel la vigile. Las dos son defendibles; mezclarlas sin saberlo no.

> ⚠️ **Dos trampas de Windows.** `cp -r` y `Copy-Item -Recurse` **siguen** los enlaces: si copiás una carpeta que contiene junctions, te quedan copias reales sin querer. Y no corras `mklink /J` desde Git Bash — MSYS reescribe el `/J` como si fuera una ruta y el comando falla de forma confusa. PowerShell no tiene ese problema.

**3. Crea el launcher** en una carpeta del `PATH`.

**4. Login.** Una vez; queda permanente.

### Verificación

Antes del login, el perfil nuevo ya debe estar ciego a los MCP del principal:

```bash
CLAUDE_CONFIG_DIR="$HOME/.claude-trabajo" claude mcp list
# → "No MCP servers configured."
```

Si ahí aparece un servidor del perfil personal, la variable no se está aplicando y no hay aislamiento.

Después del login, comparar los dos estados. El `.claude.json` del perfil default vive en `~/.claude.json` (fuera de la carpeta); el de un perfil con `CLAUDE_CONFIG_DIR` vive **adentro**, en `<perfil>/.claude.json`:

```bash
python -c "import json,sys;d=json.load(open(sys.argv[1]));print(d['oauthAccount']['emailAddress'], list(d.get('mcpServers',{})))" ~/.claude.json
python -c "import json,sys;d=json.load(open(sys.argv[1]));print(d['oauthAccount']['emailAddress'], list(d.get('mcpServers',{})))" ~/.claude-trabajo/.claude.json
```

Los mails deben diferir y la lista de MCP del perfil nuevo debe estar vacía.

---

## 3. Uso diario

| Para trabajar con… | Comando |
|---|---|
| Cuenta personal | `claude` |
| Cuenta de trabajo | `claude-trabajo` |

No hay que "cambiar" nada: son comandos distintos. Se pueden correr **en paralelo**, en terminales distintas, cada uno con su cuenta y su historial.

Ante cualquier duda de en cuál estás, adentro de Claude: **`/status`** muestra el mail de la cuenta. Es el juez para todo este asunto.

---

## 4. El panel de auditoría

Un montaje de varios perfiles **deriva en silencio**: una skill que quedó copiada, un hook que apunta al perfil de al lado, un perfil sin login. Nada de eso avisa.

[`panel-cuentas.py`](panel-cuentas.py) recorre los perfiles y escribe un HTML autocontenido con lo que encuentra. **Solo lee**: no usa internet, no pide claves, no cambia nada. Python 3.10+, sin dependencias.

```bash
python panel-cuentas.py                  # el HTML en la carpeta actual
python panel-cuentas.py --anonimo        # tapa mails y nombre de usuario (para compartir)
python panel-cuentas.py --json           # además, el JSON crudo
python panel-cuentas.py --salida x.html  # otra ruta de salida
```

Hay un [ejemplo de salida](ejemplos/) generado con `--anonimo`.

Cuatro secciones:

- **Perfiles** — una tarjeta por cuenta: mail, plan, MCP de usuario, sesiones e historial, hooks, hash del `settings.json`, modo de permisos, estado de la conexión web de GitHub, si se usó Remote Control.
- **Skills: enlace o copia** — una matriz skill × perfil. Es la que delata la deriva.
- **Qué se aísla y qué no** — la tabla de la sección 5, con los datos vivos del repo donde lo corrés.
- **Diagnóstico** — reglas deterministas sobre todo lo anterior, por severidad.

Las reglas del diagnóstico:

| Severidad | Regla | Política |
|---|---|---|
| alta | Perfil sin login · falta el launcher | ambas |
| media | **Dos perfiles enlazados al mismo origen** | aislado |
| media | Skills copiadas · skills que el perfil de referencia sí tiene | compartido |
| media | Varios comandos de hook apuntando a otro perfil | ambas |
| baja | Un solo comando de hook apuntando a otro perfil | ambas |
| baja | Integración del multiplexor no instalada · permisos en `auto` · Remote Control usado | ambas |
| baja | Skills en el origen sin enlazar en ningún perfil | compartido |

La regla de la política `aislado` compara los **destinos** de los enlaces entre perfiles, así que un perfil solo que enlaza su propio origen no dispara nada: lo que marca es que *dos* perfiles compartan.

---

## 5. Qué se aísla y qué no

El modelo son **dos ejes independientes**: el comando trae la cuenta; la carpeta donde estás trae la configuración de proyecto.

| Capa | Dónde vive | ¿Aislado entre perfiles? |
|---|---|---|
| Login / cuenta | archivo de credenciales del perfil | **Sí** |
| MCP de usuario | `.claude.json` del perfil | **Sí** |
| Historial de sesiones | `projects/` del perfil | **Sí** |
| Plugins | `plugins/` del perfil | **Sí** |
| Conectores de la cuenta | atados a la cuenta | **Sí**, automáticamente |
| Hooks de usuario | `settings.json` del perfil | **Copiados, no compartidos** ⚠️ |
| Skills | `skills/` del perfil | **Sí** con la política default (copias propias) |
| Hooks de proyecto | `.claude/settings.json` del repo | **Compartidos** |
| Permisos, comandos, agentes | `.claude/` del repo | **Compartidos** |
| MCP de proyecto | `.mcp.json` del repo | **Compartidos** |
| Identidad de git | `git config user.email` | **Compartida** |
| Credenciales de git / GitHub | keyring del sistema | **Compartidas** |
| Sistema de archivos | el disco | **Nada aislado** |

### Los MCP, en sus tres alcances

No se comparten por **ningún** camino entre perfiles… salvo uno:

| Alcance | Dónde vive | ¿Lo ve el otro perfil? |
|---|---|---|
| Usuario | `mcpServers` del `.claude.json` del perfil | No |
| Local (por proyecto) | `projects[...]` del `.claude.json` del perfil | No |
| Proyecto | `.mcp.json` **del repo** | **Sí** |

Si un repo tiene `.mcp.json`, ese servidor lo ven todas las cuentas que trabajen esa carpeta. Es la única vía abierta, y es por diseño: es configuración del proyecto, no de la persona.

### Dos consecuencias que conviene no olvidar

**Los hooks de usuario son copias.** Al crear el perfil se copió el `settings.json`. Si después agregás o cambiás un hook en uno, **el otro no se entera**. Con tres perfiles, cada cambio hay que hacerlo tres veces o quedan divergentes.

Peor: si los hooks del `settings.json` copiado apuntan por **ruta absoluta** a scripts que viven dentro del perfil original, el perfil nuevo depende de él sin que se note. Si alguna vez renombrás o limpiás el original, se rompen los otros. Conviene que los scripts de hooks vivan en una carpeta neutral (`~/.agents/hooks/`, por ejemplo) y que ningún perfil sea el dueño.

**La identidad de git no tiene nada que ver con la cuenta de Claude.** Son ejes distintos:

| Eje | Qué decide | De dónde sale |
|---|---|---|
| Cuenta de Claude | **quién paga los tokens** | `CLAUDE_CONFIG_DIR` |
| Identidad de git | **quién firma el commit** | `git config user.email` |
| Credencial de push | **con qué token empuja** | keyring del sistema |

Trabajar un repo con la cuenta de trabajo y commitear sigue firmando con tu identidad global de git y empujando con tu token. En el historial del repo, el trabajo de una cuenta es indistinguible del de la otra. Si querés que se note, va un override por repo (`git config --local user.email …`) — pero ojo, eso aplica a *todos* los commits de ese repo, no solo a los de esa cuenta.

---

## 6. Seguridad: la frontera es de configuración, no de sandbox

Que una cuenta "no vea los MCP de la otra" significa que no tiene esas herramientas cargadas ni sus credenciales. **No significa que esté enjaulada.** Es el mismo sistema operativo, el mismo usuario, el mismo disco: la sesión de la cuenta B puede leer cualquier archivo, incluido el estado del perfil A.

Para el objetivo habitual —que la cuenta de trabajo no opere con tus herramientas ni con tu historial— alcanza y sobra. Para un modelo de amenaza donde no confiás en quien maneja la otra cuenta, **no**.

Tres cosas concretas:

**1. Desde la web, la otra cuenta no llega a tu máquina.** Las sesiones en la nube operan sobre repos de GitHub, y solo si esa cuenta tiene la conexión de GitHub autorizada. El panel reporta ese estado por perfil (`connected` / `not_connected`), que es el dato que querés mirar.

**2. Remote Control es el switch que da vuelta lo anterior.** Es el mecanismo por el que una sesión web o móvil maneja una terminal local. Si lo activás en un perfil de trabajo, quien tenga esa contraseña puede manejar esa sesión local — con tu disco y tus credenciales de git. Decidilo explícitamente en vez de dejarlo como omisión. El panel marca los perfiles donde se usó.

**3. Las credenciales de git son de la máquina, no del perfil.** Cualquier proceso corriendo como tu usuario —incluida la sesión de la otra cuenta— puede `git push`. Eso no viene de la web: viene de la sesión local. Si te importa, va una regla `deny` en el `.claude/settings.json` **del repo** (que al ser de proyecto aplica a todas las cuentas por igual) para que el push quede del lado humano.

**Y nunca copies el archivo de credenciales entre perfiles.** Cada perfil hace su `/login`. `/logout` tampoco es parte de este flujo: desloguear tira justamente lo que este montaje consigue.

---

## 7. Uso con un multiplexor (Herdr)

[Herdr](https://herdr.dev) es un multiplexor de terminales que entiende el ciclo de vida de los agentes (detecta `idle` / `working` / `blocked`). Todo lo de abajo vale para cualquier multiplexor con `--env` por panel; lo verifiqué en Herdr.

### A mano — el 99% de las veces

Abrís un panel y escribís el comando. **Eso es todo.** El multiplexor detecta el agente igual, porque el proceso es el mismo `claude`.

Para distinguirlos en pantalla, nombralos: `herdr agent rename <pane> trabajo`.

### Cuando un agente lanza a otro

`herdr agent start` existe para que un agente le abra un panel a otro agente. Ese comando arranca el binario **pelado** —no conoce tu launcher— así que la cuenta hay que pasarla al crear el panel:

```bash
herdr pane split --current --direction right --cwd "$PWD" \
  --env "CLAUDE_CONFIG_DIR=$HOME/.claude-trabajo" --no-focus
herdr agent start trabajo --kind claude --pane <pane-id-devuelto>
```

`--env` existe en `pane split`, `tab create` y `workspace create`. **No** en `worktree create`.

> ⚠️ **El entorno no se hereda.** Verificado con pruebas separadas:
>
> | Caso | ¿Tiene la variable? |
> |---|---|
> | `workspace create --env` → su panel raíz | sí |
> | `tab create` dentro de ese workspace | **no** |
> | `pane split` desde un panel que la tiene | **no** |
>
> Los paneles nacen del servidor del multiplexor, no del shell padre. **Un panel que no se creó con `--env` es la cuenta por defecto**, aunque esté al lado de uno de la otra cuenta y en la misma carpeta.

Atajo para `config.toml`, que evita el paso donde te olvidás:

```toml
[[keys.command]]
key = "prefix+alt+t"
type = "shell"
command = "herdr pane split --direction right --env CLAUDE_CONFIG_DIR=/ruta/a/.claude-trabajo"
```

Funciona sin `--pane` ni `--cwd`: sin target usa el panel enfocado, y sin `--cwd` el panel nuevo hereda el cwd de ese panel.

### Cómo verificarlo sin creerle a nadie

La CLI de Herdr responde en JSON y casi siempre hay un campo que nombra lo que pasó de verdad:

```json
{"result":{"agent":{"agent":"claude","name":"trabajo"},"argv":["claude"],"type":"agent_started"}}
```

`argv` es el comando exacto que ejecutó. Dice `claude`, no tu launcher — ahí está la prueba, sin deducir nada.

### La integración de estado se instala por perfil

El multiplexor instala un hook para saber si el agente está trabajando o bloqueado, y lo instala **en una raíz de configuración**. Si copiaste el `settings.json`, el perfil nuevo tiene el hook pero apuntando al script del original: funciona, y es exactamente la dependencia invisible de la sección 5.

Se desacopla instalándolo de verdad en el perfil, que respeta la variable:

```bash
CLAUDE_CONFIG_DIR="$HOME/.claude-trabajo" herdr integration install claude
```

---

## 8. Alternativas que probé y descarté

### Cuentas gestionadas del IDE — funcionan, pero no aíslan

Algunos entornos (Orca, por ejemplo) traen un selector de cuentas de proveedor. **Funciona y es reversible**, pero el mecanismo es **intercambio de identidad, no aislamiento**: al activar una cuenta gestionada, se **reescriben las credenciales dentro de `~/.claude`**.

Lo que medí:

- Al activar la segunda cuenta, el estado del perfil personal pasó a ese mail **conservando todos los servidores MCP y la lista entera de proyectos**. La cuenta nueva quedaba con acceso a todo lo personal.
- El efecto es **de toda la máquina**, no solo del IDE: cualquier `claude` en cualquier terminal pasaba a la otra cuenta.
- Alcanza a **sesiones ya abiertas**, en ambas direcciones, sin reiniciar.
- Al eliminar la cuenta gestionada, el login original **se restauró solo**, intacto.
- **Deja residuo**: el intercambio escribió varios MB de skills sincronizadas de la segunda cuenta dentro de la carpeta del perfil personal. Está separado por identificador de cuenta, así que es inocuo, pero es la prueba física de que el swap escribe en tu carpeta. El perfil aislado no deja nada.

**Cuándo sí conviene:** para estirar créditos — seguir el mismo trabajo, con los mismos MCP, facturando a otra cuenta. Ahí compartir el entorno es deseable, y además conserva las sesiones de chat al cambiar, que es lo único que el perfil aislado no da.

**Por qué no lo adopté:** el objetivo era que la cuenta de trabajo no toque nada personal.

### cc-switch — no puede hacerlo para Claude Code

[cc-switch](https://github.com/farion1231/cc-switch) gestiona proveedores de API, no cuentas OAuth de Claude Code. Su propio FAQ lo dice: *"After switching to it, run the Log out / Log in flow"*, y nombra el cambio entre varias cuentas oficiales **solo para Codex**.

Leyendo el código: no hay ninguna referencia al archivo de credenciales de Claude Code, y su escritura para Claude es **reemplazo total** del `settings.json` con la config del proveedor, sin merge. Sirve si tu segunda cuenta es una **API key** de la consola (`ANTHROPIC_API_KEY` anula la suscripción mientras está activa), no si es otra suscripción.

> ⚠️ Tras instalarlo, su proveedor `default` de Claude queda en `{}` con *Apply Common Config* destildado. Un clic en esa pestaña deja tu `settings.json` global en dos caracteres. Se desarma tildando *Apply Common Config* en cada proveedor, o no abriendo esa pestaña.

También guarda tokens OAuth (`access_token`, `refresh_token`, `id_token`) en un SQLite **sin cifrar**. Si lo usás, es superficie nueva a inventariar.

### Lo que cc-switch sí resuelve bien: cómo compartir

No sirve para cambiar de cuenta, pero su modelo de datos es la mejor respuesta que vi al problema de compartir configuración entre destinos. Leyendo su SQLite:

| Tabla | Forma |
|---|---|
| `mcp_servers` | `id`, `server_config`, y un booleano **por destino**: `enabled_claude`, `enabled_codex`, `enabled_gemini`… |
| `skills` | `id`, coordenadas del repo (`repo_owner`, `repo_name`, `repo_branch`, `directory`), el mismo booleano por destino, más `content_hash` e `installed_at` |
| `settings` | una fila `common_config_<app>` con la configuración base compartida |
| `providers` | `meta.commonConfigEnabled` decide **por proveedor** si esa base se aplica |

Tres propiedades que vale la pena robar:

1. **El catálogo está separado de lo activado.** Una skill o un servidor MCP se declara **una vez**, y no está en ningún destino hasta que se tilda. El default es apagado.
2. **La activación es por destino**, con un booleano, no con una carpeta compartida.
3. **Se materializa por copia, no por enlace** — y `content_hash` permite detectar que la copia derivó **sin que exista acoplamiento en tiempo de ejecución**. Nadie depende de nadie.

Eso es exactamente la política `aislado` de este repo: copias propias, y una herramienta que te avisa cuando divergen. Lo que **no** conviene imitar es cómo escribe: para Claude hace reemplazo total del `settings.json`, sin merge.

---

## 9. Handoff entre cuentas

El historial es por perfil: **no hay `--continue` ni `--resume`** de una sesión de una cuenta desde el perfil de la otra.

Lo vi en vivo: una sesión de la segunda cuenta arrancó diciendo "no hay memoria de sesiones anteriores" y reconstruyó el estado leyendo el repo (`git log`, el archivo de estado del proyecto, la lista de tareas). La memoria **existía** — en el otro perfil, del mismo día — pero esa cuenta no podía leerla.

Como fallback, reconstruir desde el repo funciona bien. Y se puede hacer mucho mejor con **hooks de proyecto**, que por ser de proyecto corren igual en todos los perfiles:

- un hook `Stop` que escriba un handoff al final de un archivo de bitácora,
- un hook `SessionStart` que lo inyecte al arrancar.

Cambiar de cuenta en la misma carpeta preserva la continuidad. Un repo sin `.claude/` no tiene nada de esto.

Alternativa para arrastrar el contexto literal: copiar el `.jsonl` de la sesión entre perfiles. La convención de carpetas es idéntica (`projects/<cwd-saneado>/`). **No lo verifiqué.**

---

## 10. Las tres trampas

1. **Compartir sin haberlo decidido.** Un `New-Item -ItemType Junction` de más, o un `cp -r` que siguió un enlace, y dos cuentas quedan atadas (o dos copias quedan congeladas) sin que nadie lo haya resuelto. Elegí la política y dejá que el panel la vigile.
2. **Los hooks que apuntan al perfil de al lado.** La copia del `settings.json` trae rutas **absolutas**. Mientras el original exista, funciona; el día que lo toques, se rompen varios perfiles a la vez. Es la fuga más silenciosa de las tres, porque no se ve en ninguna lista de skills.
3. **El panel sin `--env`** (si usás multiplexor). No hay herencia: es la cuenta por defecto, calladamente.

Las tres las detecta `panel-cuentas.py`. Esa es toda la razón por la que existe.

---

## Licencia

MIT. Ver [LICENSE](LICENSE).
