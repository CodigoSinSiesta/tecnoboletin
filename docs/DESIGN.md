# Sistema de diseño — Tecnoboletín

Rediseño de agosto 2026 (segunda iteración), a partir de las maquetas del proyecto
*UI Mockups Tecnoboletin* de Claude Design. Sustituye a la dirección "zine con carácter"
anterior. Feedback que lo motiva, literal del usuario: demasiado texto en bloque y difícil
de escanear, el grafo 3D desconectado del boletín, poca personalidad de marca, ruido de
colores en la paleta, y densidad que pierde la señal.

Dirección elegida: **1a "Blueprint diario"** (lectura editorial con el mapa del grafo
siempre a la vista) **+ la consola de triaje de 1b** como vista alternativa del mismo
boletín. Solo diseño/frontend: no toca contenido, datos ni la pipeline de enriquecimiento.

## Paleta — slate-900, un acento, tres estados

El sistema anterior tenía cinco acentos con propósito semántico (ámbar/violeta/azul/
rosa/verde). En la práctica cada tarjeta mezclaba tres o cuatro y el color dejó de
significar nada — ese era el "ruido". El sistema nuevo separa dos preguntas que antes
compartían canal:

- **¿Qué es esto?** → lo dice la *jerarquía* (tamaño, posición, numeración), nunca el color.
- **¿Qué hago con esto?** → lo dice el *color de estado*, y solo él.

| Rol | Token | Hex | Significado fijo |
|---|---|---|---|
| Marca / navegación / "leer" | `--color-accent` (+ `soft/dim/deep/deepest`) | `#3B82F6` y familia | Identidad, enlaces, énfasis. |
| Estado ACTÚA | `--color-go` | `#34D399` | explorar / probar |
| Estado VIGILA | `--color-warn` | `#FBBF24` | vigilar / madurez dudosa |
| Estado ALERTA | `--color-alert` | `#F87171` | alerta honesta / riesgo / descartado |

Superficies en un solo gradiente de profundidad slate: `#0B1220` (lienzo) → `#0F172A`
(elevado) → `#152033` (tarjeta), con `--color-rail` (`#0D1424`) para columnas laterales
de consola, que bajan en vez de subir. Texto en cuatro niveles (`text/body/muted/muted-dim`);
`--color-body` (`#CBD5E1`) es nuevo: el cuerpo de lectura ya no usa `muted`.

Los tokens antiguos `--color-radar` y `--color-violet` se conservan como alias dentro de
la familia azul para no romper páginas sin rediseñar.

Todos los tokens van bajo `--color-*` porque Tailwind v4 solo genera utilidades para
namespaces reconocidos en `@theme`. El CSS propio va en `@layer base/components`: sin
capa explícita ganaría a cualquier utilidad de Tailwind y `class="dot w-1.5"` no podría
ajustar un componente.

## Firma visual

Dos elementos puramente decorativos, y solo estos dos, en todas las pantallas:

- **`.brand-rule`** — filete superior de 3px con degradado de tres azules.
- **`.csi-dot`** — punto azul que late (respeta `prefers-reduced-motion`) junto al
  breadcrumb monoespaciado `código sin siesta / tecnoboletín / …`.

## Tipografía

- **Space Grotesk** — titulares, labels de sección, numeración.
- **Inter** — UI y cuerpo corto.
- **JetBrains Mono** — nombres de repo, métricas, edges, chrome de consola, badges.
  Gana peso respecto al sistema anterior: los identificadores de repo son contenido
  de primera clase y se componen siempre en mono.
- **IBM Plex Serif** — solo el markdown de boletines sin enriquecer (`.prose-read`).

## Patrones

- **Badge de estado** (`.badge--go/warn/alert/read`): fondo translúcido + borde. La única
  variante sólida es `.badge--pick` (azul): el pick editorial es la única señal que puede
  pesar más que el estado.
- **Hallazgo** (`.finding`): canaleta izquierda de 46px con número + punto de estado; el
  ojo baja por la canaleta y escanea el boletín sin leer.
- **Recorte + ampliar** (`.clamp-2/3` + `.expand`): todo cuerpo largo se recorta a 2-3
  líneas y se amplía con un `<details>` sin JavaScript. Es la respuesta directa a
  "demasiado texto en bloque": el texto completo sigue ahí, pero ya no es el default.
- **Chips de grafo** (`.gchip`): cada hallazgo lista sus relaciones; borde discontinuo +
  «nuevo» si la relación entra hoy al grafo, borde sólido + fecha si ya se cubrió. Es la
  conexión boletín↔grafo dentro de la propia página.
- **Mapa del día** (`MiniMap.astro` + `lib/daymap.ts`): subgrafo de las relaciones del
  boletín, con layout radial *determinista* calculado en build (idéntico en cada build,
  sin simulación física), fijo en la columna derecha del boletín.
- **Consola** (triaje y grafo): tres columnas — raíl/filtros, contenido, inspector — con
  atajos de teclado documentados en la propia barra inferior.

## Pantallas

| Pantalla | Ruta | Notas |
|---|---|---|
| Boletín del día | `enriquecido/[date]` | Hero con titular (primera frase de `editorial.posicionamiento`), hallazgos, radar, mapa del día, alertas, "tu turno". J/K navega. |
| Consola de triaje | `triaje/[date]` | Columnas explorar/probar/leer/vigilar desde `accion_sugerida` normalizada; E/P/L/V/X mueven el item seleccionado. El triaje se guarda en la tabla `user_triage` (upsert por movimiento, clave user+fecha+item), así que acompaña al usuario entre dispositivos. **Solo administradores**: `fetchRole()` lee `user_profiles.role`; la barrera real es la RLS de esa tabla. |
| Ficha de repositorio | `repo/[owner]/[name]` | Nueva. Cruza el item enriquecido + señales parseadas + grafo: stat strip, diagrama "cómo funciona", posición en el ecosistema, apariciones. |
| Explorador de grafo | `grafo/` | Consola de 3 columnas; inspector con "cómo creció este nodo" (barra temporal por boletín). El JSON se sigue descargando en runtime. |
| Índice del grafo | `grafo/indice/` | Igual que antes + anclas `#id-de-nodo` (destino de los chips). Con sesión, botón «Guardar» por nodo (`user_favorites`, kind `nodo`), igual que el inspector 3D y la ficha de repo. |
| Archivo | `enriquecido/` | Cada fila muestra el reparto de estados del día en puntos de color. Con sesión iniciada, marca «✓ leído» los boletines de `user_reads` (el botón de marcar sigue en el propio boletín). |
| Usuarios | `cuenta/usuarios/` | Nueva. Lista las cuentas y da/quita el rol de administrador. Solo visible para administradores; el enlace aparece en `cuenta/` con ese rol. |

### Cuentas, roles y autorización

El sitio es estático, así que **no hay backend donde esconder una service_role key**: toda
la autorización tiene que vivir en Postgres. De ahí el diseño:

| Tabla | Para qué | Quién puede |
|---|---|---|
| `user_profiles` | Espejo de `auth.users` (que PostgREST no expone) con el campo `role` | Cada cual lee su fila; los administradores leen todas y son los únicos que pueden escribir `role` |
| `user_favorites` | Boletines y nodos guardados (`kind`: `boletin` \| `nodo`) | Solo el dueño |
| `user_reads` | Boletines marcados como leídos | Solo el dueño |
| `user_triage` | Estado de triaje por item (`user_id`, `boletin_date`, `item_idx`) | Solo el dueño |

Tres decisiones que conviene no deshacer:

- **El rol vive en `user_profiles`, no en `app_metadata`.** `app_metadata` solo se escribe
  con la service_role key, que jamás puede viajar al navegador: con ella los roles solo se
  gestionarían desde el dashboard de Supabase. Con la tabla, la gestión ocurre en la
  propia web y la RLS es a la vez la barrera y el dato que lee la interfaz.
- **`is_admin(uid)` es SECURITY DEFINER.** Si la política de `user_profiles` consultara
  `user_profiles` directamente, la RLS se llamaría a sí misma (recursión infinita).
- **Un trigger impide quitar el rol al último administrador.** Sin él, un admin podría
  degradarse a sí mismo y dejar la gestión de roles inaccesible para siempre, sin backend
  que la rescatara.

El alta de perfil es automática: un trigger sobre `auth.users` crea la fila al registrarse.
Los gates de interfaz (ocultar el triaje, ocultar el enlace de usuarios) son comodidad, no
seguridad: quien los saltara se encontraría con que Postgres no le devuelve ni le acepta
nada.

## Datos: texto libre → estructura (lib/boletin.ts)

`accion_sugerida` y `madurez_senales` son texto libre del enriquecedor con formato
inconsistente entre boletines. `lib/boletin.ts` extrae de ahí el estado (verbo
normalizado), estrellas/forks/lenguaje/licencia/issues/estado y los topics, siempre con
`null` cuando el dato no está — la UI pinta "—", nunca inventa. El markdown de estos
campos se renderiza con `marked` (`lib/markdown.ts`), como en la iteración anterior.
