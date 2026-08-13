# Sistema de diseño — Tecnoboletín

Rediseño visual (agosto 2026). Dirección: **"zine con carácter"** — más personalidad y
color que el "dark tech minimal" genérico anterior, coherente con la identidad de
[Código Sin Siesta](https://codigosinsiesta.com) (el blog/newsletter padre), sin copiarla
1:1. Solo diseño/frontend: no toca contenido, datos ni la pipeline de enriquecimiento.

## Paleta — navy/índigo con acentos semánticos

El sitio anterior usaba un fondo casi negro plano (`#0c0e14`) y un único acento ámbar
para todo. El nuevo fondo (`#0a0e1a` → `#131a2e` → `#1a2340`, de más profundo a más
elevado) se acerca a la familia navy/índigo del sitio padre (que usa `#0f172a` /
`#0c1220` — confirmado inspeccionando su CSS compilado) sin ser idéntico.

Cuatro acentos, cada uno con un propósito fijo — el color comunica estructura, no decora:

| Token | Hex | Uso |
|---|---|---|
| `--color-accent` (ámbar) | `#f5b65a` | Hallazgo principal, "pick" editorial |
| `--color-violet` | `#b39ddb` | Síntesis editorial (el contenido más valioso del boletín) |
| `--color-radar` (azul) | `#6aa6ff` | Radar secundario, enlaces, acción "leer" |
| `--color-alert` (rosa) | `#fb7185` | Alertas honestas |
| `--color-go` (verde) | `#34d399` | Acción concreta "explorar / probar" |

Todos los pares texto/fondo (`--color-*` y su `--color-*-ink`) se verificaron a mano
con la fórmula de contraste relativo de WCAG: el texto principal sobre `--color-bg` da
17:1, `--color-muted` 7.8:1, `--color-muted-dim` (la variante más oscura, reservada para
metadatos pequeños) 5.3:1 — por encima del mínimo AA (4.5:1) incluso a 12px. Los "ink"
de cada badge (texto oscuro sobre acento) dan entre 8.5:1 y 11.7:1, salvo violeta, donde
blanco falla (2.4:1) y por eso su ink es oscuro (`#1c1330`, 8.8:1).

Todos los tokens de color usan el namespace `--color-*` a propósito: en Tailwind v4 solo
los namespaces reconocidos en `@theme` generan utilidades (`bg-`, `text-`, `border-`);
un token con otro nombre define una custom property pero no genera ninguna clase, y el
build pasa igual sin avisar. Se verificó tras el primer build que las clases usadas
(`bg-bg-raised`, `text-accent-ink`, etc.) tienen cuerpo de regla real en el CSS
compilado, no solo el nombre de clase en el HTML.

## Tipografía — con carácter, coherente con la marca madre

- **Space Grotesk** (`--font-display`) — titulares, labels, tags, numeración zine. Es la
  misma familia que usa el sitio padre para su hero a 80px; aquí se usa en pesos 500-800.
- **Inter** (`--font-sans`) — UI, navegación, texto corto. Igual que el sitio padre.
- **IBM Plex Serif** (`--font-serif`) — *solo* para el cuerpo de artículos largos
  (`.prose-read`): posicionamiento editorial, "por qué importa", markdown de boletines.
  El sitio padre no usa serif; aquí se conserva a propósito como diferenciador de
  "modo lectura" frente a "modo interfaz".
- **JetBrains Mono** (`--font-mono`) — nombres de repos, URLs, edges del grafo.

Antes del rediseño ninguna de estas fuentes se cargaba realmente (no había `<link>` ni
`@font-face`): los tokens existían en `global.css` pero el navegador renderizaba con la
fuente de sistema de fallback. Se añadió `<link>` + `preconnect` a Google Fonts en
`BaseLayout.astro`, pidiendo solo los pesos que se usan.

## Jerarquía — romper la monotonía de 20 tarjetas idénticas

- **Numeración zine** (`.zine-num`): número fantasma en Space Grotesk con contorno,
  antepuesto a cada hallazgo principal, como una revista.
- **Rail lateral de color** (`.zine-card`): borde izquierdo de 3px coloreado por tipo de
  contenido en vez de un border uniforme gris.
- **Pick editorial** (`.zine-card--pick`): los hallazgos que `editorial.acciones_concretas`
  marca con `tipo: "explora"` (cruce por `item_idx`) reciben fondo elevado con degradado
  sutil y un halo ámbar — es la señal editorial más fuerte que ya existe en los datos,
  mejor que "los dos primeros son grandes". Si el cruce no encuentra nada (algún boletín
  futuro sin acciones), la jerarquía hallazgo/radar de dos niveles se mantiene igual.
- **Radar secundario**: tratamiento deliberadamente más compacto y silencioso (menos
  padding, rail más fino, sin numeración grande) — es "ruido de fondo" a propósito.
- **Separadores de sección** (`.section-rule`): barra de degradado + etiqueta en vez de
  un `border-t` gris plano; el color de la barra varía por sección.
- **Ancho de línea**: `.prose-read` (70ch) para prose de página completa (centrado) y
  `.prose-card` (68ch, sin centrar) para cuerpo dentro de tarjetas — alineado con el
  título de la tarjeta, no flotando suelto en el centro. Metadatos, tags y badges siguen
  usando el ancho completo del contenedor.

## Acciones concretas — normalización de texto libre

`contenido.accion_sugerida` es texto libre generado por el enriquecedor, con formatos
inconsistentes (`explorar — …`, `**explorar**`, `: vigilar`, `sugerida: vigilar`, etc.).
Las páginas ahora extraen solo el verbo (`explorar/probar` → verde, `leer` → azul,
`vigilar` → ámbar, `ignorar` → gris outline) para el badge, y muestran el texto completo
como detalle secundario — antes el string crudo (con asteriscos literales) se pintaba
tal cual dentro de la pill.

## Limitación conocida (no corregida, fuera de alcance)

`resumen_ejecutivo` y los campos de `editorial.json` contienen markdown (`**negrita**`,
backticks) que se renderiza como texto literal vía `whitespace-pre-wrap` — no se añadió
un pipeline de markdown porque transformaría contenido, fuera del alcance de este trabajo
puramente visual.
