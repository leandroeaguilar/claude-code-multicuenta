# Decisiones de diseño y alternativas evaluadas

Por qué este repositorio aísla por defecto cada perfil de Claude Code con `CLAUDE_CONFIG_DIR` y qué pasó al probar las alternativas. Para el procedimiento de alta, verificación y uso diario, ver el **[README.md](README.md)**.

---

## 1. Por qué la postura por defecto es aislar (copia vs. enlace)

Un perfil nuevo creado con `alta-perfil.ps1` o `alta-perfil.sh` arranca **sin skills**. Cuando pedís instalar alguna (`-Skills` / `--skills`), por defecto se instala por **copia**, no por enlace simbólico ni junction.

| Política | Cómo se materializa | Qué cuesta | Qué revisar |
|---|---|---|---|
| **Aislado (default)** | Copia propia por perfil | Las copias derivan con el tiempo; hay que compararlas si querés actualizarlas | Que dos perfiles no apunten sin querer al mismo origen |
| **Compartido (`-Enlazar` / `--enlazar`)** | Un origen común (`~/.agents/skills/`), enlazado | Un perfil depende de otro; tocar el origen altera todas las cuentas a la vez | Que ninguna copia haya quedado congelada |

La copia queda congelada a propósito: **la deriva es el precio de no estar acoplado**. Si querés saber cuándo divergió una skill, podés comparar contra el origen (`diff -r` o un hash de contenido) sin que exista acoplamiento en tiempo de ejecución.

Compartir mediante `-Enlazar` / `--enlazar` es válido cuando lo elegiste explícitamente —por ejemplo, una skill propia que querés editar en un solo lugar—, no cuando ocurrió por omisión.

---

## 2. Alternativas que probé y descarté

### A. Cuentas gestionadas del IDE — funcionan, pero no aíslan

Algunos entornos (Orca, por ejemplo) traen un selector de cuentas de proveedor. **Funciona y es reversible**, pero el mecanismo es **intercambio de identidad, no aislamiento**: al activar una cuenta gestionada, se **reescriben las credenciales dentro de `~/.claude`**.

Lo medido sobre una instalación real:

- Al activar la segunda cuenta, el estado del perfil personal pasó a ese mail **conservando todos los servidores MCP y la lista entera de proyectos**. La cuenta nueva quedaba con acceso a todo lo personal.
- El efecto es **de toda la máquina**, no solo del IDE: cualquier `claude` en cualquier terminal pasaba a la otra cuenta.
- Alcanza a **sesiones ya abiertas**, en ambas direcciones, sin reiniciar.
- Al eliminar la cuenta gestionada, el login original **se restauró solo**, intacto.
- **Deja residuo:** el intercambio escribió varios MB de skills sincronizadas de la segunda cuenta dentro de la carpeta del perfil personal. Está separado por identificador de cuenta, así que es inocuo, pero es la prueba física de que el swap escribe en tu carpeta. El perfil aislado con `CLAUDE_CONFIG_DIR` no deja nada.

**Cuándo sí conviene:** para estirar créditos — seguir el mismo trabajo, con los mismos MCP, facturando a otra cuenta. Ahí compartir el entorno es deseable y además conserva las sesiones de chat al cambiar, que es lo único que el perfil aislado no da.

**Por qué se descartó acá:** el objetivo era que la cuenta de trabajo o de un cliente no vea ni toque nada personal.

---

### B. `cc-switch` — no aplica a suscripciones OAuth de Claude Code

[cc-switch](https://github.com/farion1231/cc-switch) gestiona proveedores de API, no cuentas OAuth de Claude Code. Su propio FAQ lo dice (*"After switching to it, run the Log out / Log in flow"*) y nombra el cambio entre varias cuentas oficiales **solo para Codex**.

Verificado leyendo su código:

- No hay ninguna referencia al archivo de credenciales de Claude Code.
- Su escritura para Claude es **reemplazo total** del `settings.json` con la configuración del proveedor, sin merge.
- Sirve si tu segunda cuenta es una **API key** de consola (`ANTHROPIC_API_KEY` pisa la suscripción mientras está activa), no si es otra suscripción Pro/Max/Team.

> ⚠️ **Cuidado al probarlo:** tras instalar `cc-switch`, su proveedor `default` de Claude queda en `{}` con *Apply Common Config* destildado. Un clic en esa pestaña deja tu `settings.json` global en dos caracteres (`{}`). Se evita tildando *Apply Common Config* en cada proveedor o no activando ese perfil. Además, guarda tokens OAuth (`access_token`, `refresh_token`, `id_token`) en un SQLite **sin cifrar**: si lo instalás, es superficie nueva de credenciales a proteger.

---

### C. Lo que `cc-switch` sí resuelve bien: el modelo para compartir

Aunque no sirve para cambiar de suscripción OAuth en Claude Code, su esquema SQLite es un diseño muy limpio para compartir configuración entre destinos:

| Tabla | Forma |
|---|---|
| `mcp_servers` | `id`, `server_config`, y un booleano **por destino**: `enabled_claude`, `enabled_codex`, `enabled_gemini`… |
| `skills` | `id`, coordenadas del repo (`repo_owner`, `repo_name`, `repo_branch`, `directory`), el mismo booleano por destino, más `content_hash` e `installed_at` |
| `settings` | una fila `common_config_<app>` con la configuración base compartida |
| `providers` | `meta.commonConfigEnabled` decide **por proveedor** si esa base se aplica |

Tres propiedades de ese diseño que este repositorio adopta conceptualmente:

1. **El catálogo está separado de lo activado.** Una skill vive en `~/.agents/skills/` y no entra a ningún perfil hasta que se pide explícitamente. El default es apagado.
2. **La activación es por destino**, perfil por perfil, no con una carpeta global única que todos leen a ciegas.
3. **Se materializa por copia, no por enlace** — y comparar el contenido (`diff -r` o hash) permite detectar cuándo una copia derivó **sin acoplamiento en tiempo de ejecución**.

---

## 3. Continuidad y handoff entre cuentas

Como `projects/` vive dentro de cada perfil (`~/.claude-<perfil>/projects/`), el historial de conversación es por cuenta: **no hay `--continue` ni `--resume` cruzado** entre perfiles.

Verificado en la práctica: cuando una sesión de la segunda cuenta arranca sobre el mismo repositorio, no ve la memoria episódica del otro perfil, pero reconstruye el estado leyendo el propio repositorio (`git log`, estado de tareas y bitácora del proyecto).

Por eso la forma limpia de hacer handoff entre cuentas sobre un mismo repo es usar **hooks de proyecto** (`.claude/settings.json` del repositorio), que por vivir en el repo corren igual sin importar con qué cuenta entraste:

- Un hook `Stop` que obligue a registrar el handoff al final de un archivo de bitácora del repo (`docs/BITACORA.md`).
- Un hook `SessionStart` que inyecte el último handoff al abrir sesión.

*(Alternativa no verificada para arrastrar la conversación literal: copiar el `.jsonl` de la sesión entre `~/.claude/projects/<cwd-saneado>/` y `~/.claude-<perfil>/projects/<cwd-saneado>/`, ya que la convención de nombres de carpeta es idéntica).*
