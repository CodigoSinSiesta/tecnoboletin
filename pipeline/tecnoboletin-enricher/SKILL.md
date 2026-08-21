---
name: tecnoboletin-enricher
description: Skill para enriquecer los boletines diarios de Codigo Sin Siesta. Lee el ultimo .md del vault, extrae los campos ricos que ya trae (que es, por que importa, madurez, relacion con el grafo, accion sugerida), los conserva y pule (sin sustituirlos por un resumen generico), cruza la relacion con el grafo contra el historial acumulado, pasa el borrador del dia por 3 lentes de critica editorial (en memoria, nunca se publican) y publica UN articulo por boletin. Pensada para ejecutarse via cron 1h despues del boletin, o modo batch sobre los ultimos N boletines.
tags: [boletines, enriquecimiento, llm, editorial, cron, tecnoboletin]
metadata:
  hermes:
    category: research
    related_skills: [parallel-repo-explore-bulletin, blogwatcher, codigo-sin-siesta-content]
---

# tecnoboletin-enricher

Skill hermana de `parallel-repo-explore-bulletin`. Donde aquella genera el
boletin raw con hallazgos y radar, esta toma ese boletin y lo convierte en
una pieza editorial publicable -- sin tocar el `.md` original.

## Rediseno (2026-08-13)

Esta version reemplaza el diseno original tras una revision de Alejandro
sobre lo publicado. Problemas que corrige, en orden:

1. **Ya no se pierde informacion.** El v1 reducia cada hallazgo a un
   `resumen_2_lineas` generico, descartando el "que es", "por que importa",
   "madurez/senales", "relacion con el grafo" y "accion sugerida" que el
   boletin origen ya trae escritos. v2 extrae esos campos deterministamente
   (`extract_items.py`) y los CONSERVA -- el enriquecimiento pule, no
   sustituye.
2. **Ya no hay personas sinteticas.** El v1 inventaba 3 personajes (Carlos,
   Dani, Maria) con biografia y "honestidad: N/10" que opinaban con nombre
   propio y se publicaban tal cual en la web. v2 usa 3 LENTES DE CRITICA
   explicitamente enmarcadas como criterios de revision editorial (rigor
   tecnico, claridad/accesibilidad, relevancia editorial) -- ver
   `references/criterios-revision.md`. Su feedback se usa en memoria para
   mejorar el borrador del dia y se descarta: **no existe `reviews.json`
   ni ningun artefacto equivalente.**
3. **Ya no se publica el andamiaje interno.** El v1 mostraba tres bloques
   crudos en la pagina: "Items clasificados" (tarjetas con resumen +
   confianza), "Reviews" (opiniones con nombre) y "Edges propuestos"
   (volcado de tripletas). v2 publica UN articulo por boletin: la sintesis
   editorial arriba (`editorial.json`, que ya funcionaba bien y se
   conserva), seguida de los hallazgos con su "por que importa" y
   "relacion con el grafo" pulidos como cuerpo principal (tipo/tema/
   confianza quedan como metadata discreta secundaria), y los edges del
   grafo como detalle colapsable al final.

## Estado del backend LLM (importante, leer antes de asumir cual hay)

En el runtime de Contabo (`ibid`) a fecha 2026-08-13:

- **Backend real que SI funciona: `hermes -z` (Hermes Agent CLI, ya
  configurado en este runtime con MiniMax-M3 -- `~/.hermes/config.yaml`,
  `model.provider: minimax`).** Es el mismo mecanismo que usa con exito el
  cron del boletin original todos los dias. El binario vive en
  `~/.local/bin/hermes` (normalmente NO esta en el PATH de una sesion SSH
  no interactiva -- `hermes_client.py` lo busca explicitamente ahi antes
  de rendirse). `enrich_items.py` y `synthesize_article.py` usan
  `--llm hermes` **por defecto**. Verificado en pruebas reales sobre
  2026-08-11 antes de generalizar al resto de dias: el pulido y la
  critica+reescritura cambian el texto de forma sustantiva (no un echo),
  incluyendo convertir referencias vagas ("el boletin de ayer") en fechas
  concretas del `primera_mencion` que aporta `graph_crossref.py` (ej. "que
  ya abrimos el 2026-07-16 con `stablyai/orca`").
- **Cada llamada a `hermes -z` es cara**: levanta un agente completo,
  ~15-40s incluso para un prompt corto. Por eso la pipeline BATCHEA: **1
  llamada por dia** en `enrich_items.py` (pule que_es/por_que_importa de
  TODOS los items a la vez) + **1 llamada por dia** en
  `synthesize_article.py` (critica de 3 lentes + reescritura de
  por_que_importa de todos los hallazgos a la vez). Nunca una llamada por
  item -- séria ~15-20 llamadas/dia y el runtime se dispararia.
- **Quirk observado en pruebas reales**: la respuesta de `hermes -z` con
  MiniMax-M3 llega consistentemente SIN el cierre final del array JSON
  (`]`) -- probablemente un corte de longitud de salida. `parse_json_lenient`
  en `hermes_client.py` reintenta anadiendo el cierre que falte antes de
  dar la respuesta por invalida. Tambien se observo una fuga aislada de
  caracteres CJK insertada por el propio modelo en un campo sin relacion
  (no copiada del `.md` origen) -- `strip_cjk` limpia esto en toda salida
  de LLM antes de aceptarla, y `clean_cjk.py` es el chequeo final antes de
  persistir.
- **Salvaguardas contra invencion**: el pulido rechaza respuestas vacias o
  >1.6x mas largas que el original (debe ser un cambio menor). La
  critica+reescritura permite mas elaboracion real (~1.5x-2x observado en
  pruebas) pero rechaza cualquier campo que supere 2.5x el original o 1800
  caracteres absolutos -- en la corrida real sobre los 10 dias, 3 items (2
  en 2026-08-06, 1 en 2026-08-09) fueron rechazados por este limite y se
  conservo su texto original; queda trazado en
  `stats.critica_notes` de cada `enriched.json`.
- **Ollama NO esta instalado** (`which ollama` -> nada) y la maquina tiene
  ~11GB RAM con ~8GB ya en uso por otros servicios (Hermes, Gitea/act_runner,
  etc.) -- no instalar un modelo de 14B aqui sin verificar margen primero.
  No hizo falta: `hermes -z` cubre la necesidad sin instalar nada nuevo.
- **MiniMax via Pi Agent SDK (el camino que describia la version anterior
  de este SKILL.md) esta roto y no se uso**: `node_modules/@earendil-works/pi-coding-agent`
  fallaba con `ERR_PACKAGE_PATH_NOT_EXPORTED` al invocar `scripts/classify.ts`
  -- nunca llego a ejecutarse con exito. Esos `.ts` y esa dependencia se
  ELIMINARON en este rediseno; `hermes -z` (subproceso simple, sin SDK) es
  el camino real.
- **Los 10 dias procesados con `--llm hermes` (2026-08-02 a 2026-08-11)**
  tienen `stats.llm_backend: "hermes"` y `stats.critica_lentes_aplicada: true`
  en su `enriched.json`. Si `hermes -z` deja de estar disponible en el
  futuro (binario movido, config rota, etc.), `enrich_items.py` /
  `synthesize_article.py` degradan a `--llm none` (passthrough) pero
  **reportando el motivo concreto por stderr** -- nunca asumen "no hay
  backend" en silencio. El campo `stats.critica_lentes_aplicada` en cada
  `enriched.json` deja trazado si esa capa se aplico o no.
- **Antes de activar el cron real**: el backend ya esta resuelto
  (`hermes -z`, default). Lo que falta antes de encender el cron es
  presupuestar el tiempo: 2 llamadas `hermes -z` por dia, ~15-40s cada
  una, mas el resto de la pipeline (determinista, rapida) -- unos 1-2 min
  totales por dia en la corrida real. Verificar que ese margen encaja en
  la ventana del cron (ver pitfall #8 mas abajo).

## Cuando se activa

- **Cron automatico**: encadenado 1h despues del boletin (10:10 diario) o
  via `context_from=<job_id_boletin>` -- **todavia no esta dado de alta en
  `~/.hermes/cron/jobs.json`**; el backend LLM ya esta resuelto y probado
  (`hermes -z`), falta solo decidir el alta del cron job en si.
- **Modo batch manual**: pase de los ultimos N boletines para validar la
  pipeline antes de activar cron.
- **Disparo manual**: cuando Alejandro pregunta "enriquece el ultimo
  boletin" o "procesa los N ultimos".

## Inputs / Outputs

### Input

- `~/obsidian-vault/Research/Boletines/<DATE>-trending.md` (del cron de
  tendencias). NO se toca, solo se lee.
- `~/.hermes/data/codigosinsiesta-trends/state.json` -- grafo de
  conocimiento acumulado (`knowledge_graph.nodes` / `.edges`, con
  `added: YYYY-MM-DD` por edge). Se LEE para `graph_crossref.py`; esta
  skill nunca escribe en ese fichero (es responsabilidad exclusiva del
  cron `codigosinsiesta-trends-bulletin`).

### Output (fuente de verdad real -- lo que consume la web)

**`~/proyectos/tecnoboletin/apps/web/src/data/boletines/<DATE>/`**:

- `enriched.json` -- items enriquecidos v2 (ver
  `references/item-schema.json`). Reemplaza en el sitio al `enriched.json`
  v1 (misma ruta, nuevo shape).
- `editorial.json` -- sintesis editorial del dia (titular, posicionamiento,
  convergencia con el stack, cruce con el grafo, tendencias, alertas,
  acciones concretas). El `titular` (35-85 chars, una sola idea, sin punto
  final, sin muletilla y sin enumerar) lo escribe el LLM y lo valida
  `_validate_titular`; la web lo usa tal cual. Antes de que existiera este
  campo la web lo fabricaba a partir de la primera frase del
  `posicionamiento`, que es un parrafo, y salian titulares de 300+ chars o
  cortados a media frase. Ya funcionaba bien en v1 -- se conserva el
  contenido, solo se ajusta el schema (`perfiles_involucrados` ->
  `lentes_aplicadas`).
- `edges.jsonl` -- edges derivados de `relacion_grafo` de cada item, mas
  los edges tema/boletin de siempre. Incluye `primera_mencion` cuando
  aplica.
- ~~`reviews.json`~~ -- **eliminado**. No se genera en v2 y se borra si
  quedaba de una corrida v1 anterior (lo hace `persist.py`
  automaticamente).

**IMPORTANTE -- divergencia documentada con versiones anteriores de esta
skill**: el `SKILL.md` original describia outputs en
`~/.hermes/data/tecnoboletin/{enriched,reviews,graph}/` como si esa fuera
la fuente de verdad. Eso nunca fue cierto para lo publicado: la pagina
Astro (`apps/web/src/pages/enriquecido/[date].astro`) lee exclusivamente
de `apps/web/src/data/boletines/<date>/` en el repo. `~/.hermes/data/tecnoboletin/`
se sigue usando como **directorio de trabajo/state propio de la skill**
(`_work/` para intermedios, `state.json` para tracking de que se proceso),
nunca como destino publicable. `persist.py` v2 escribe directamente al
repo.

## Metodologia (5 fases + persistencia)

Ver tambien `scripts/run.sh`, que orquesta las 5 fases end-to-end para
una fecha (patron draft-then-cp: todo se genera en `~/.hermes/data/tecnoboletin/_work/`
y solo se copia al repo si pasa el chequeo CJK).

### Fase 1 -- Deteccion e hidratacion

1. Identificar el boletin a procesar (parametro, o el mas reciente del
   vault via `ls -t`).
2. Si ya existe `apps/web/src/data/boletines/<date>/enriched.json` de una
   corrida v1 anterior, se usa como `--carry-metadata-from` (conserva la
   clasificacion tipo/tema/confianza ya hecha en vez de reclasificar) y
   `apps/web/src/data/boletines/<date>/editorial.json` como
   `--carry-forward` para el editorial (si ya fue aprobado, no se
   reescribe su contenido, solo se ajusta el schema).

### Fase 2 -- Extraccion determinista (`scripts/extract_items.py`)

Parsea el `.md` y saca items con sus campos ricos, SIN LLM. Robusto a las
variantes de formato que el boletin origen ha usado en distintas fechas
(encabezados `#### N. [titulo](url)` vs `### slug - sub` sin numerar,
triples `--rel-->` vs `--[rel]-->`, URL en el link vs en bullet aparte vs
inferida de un slug `owner/repo`). Ver cabecera del script para el detalle
de las variantes soportadas.

Output: `{idx, titulo, url, url_inferida, seccion, contenido: {que_es,
por_que_importa, madurez_senales, accion_sugerida, descripcion_raw},
relacion_grafo: [{src, rel, dst}]}` por item, mas `resumen_ejecutivo`.

**Validado por conteo** contra los 10 `enriched.json` v1 existentes
(2026-08-02 a 2026-08-11): coincide en 6/10; en los otros 4 el conteo
nuevo es MAYOR porque el v1 (generado a mano) omitio items reales del
radar secundario -- verificado leyendo el `.md` origen linea a linea. El
parser v2 es mas completo, no tiene un bug de conteo.

### Fase 3 -- Enriquecimiento (`scripts/enrich_items.py`)

- Limpieza mecanica ligera (`tidy_text`, sin LLM): normaliza espacios,
  quita envoltorios markdown sueltos y fugas de CJK.
- Con `--llm hermes` (default): UNA llamada batcheada a `hermes -z` con
  TODOS los items del dia (no una por item) que pule gramatica/claridad de
  `que_es` y `por_que_importa` (ver `templates/polish-prompt.md`) --
  rechaza automaticamente cualquier respuesta vacia o >1.6x mas larga que
  el original (senal de invencion) y limpia cualquier fuga de CJK que el
  modelo pueda introducir.
- `clasificacion` (tipo/idioma/autor/medio/tema_principal/
  temas_secundarios/confianza): se conserva del `enriched.json` v1 previo
  si existe (join por URL); si no, heuristica minima sin LLM
  (`guess_clasificacion`, confianza baja marcada explicitamente).
- `relacion_grafo` se anota con `primera_mencion` via
  `scripts/graph_crossref.py` (consulta determinista contra
  `codigosinsiesta-trends/state.json`): si el nodo destino de un triple ya
  aparecia en el grafo acumulado antes de esta fecha, se anota la fecha
  mas antigua -- eso es lo que permite decir "ya cubierto el 2026-08-04
  en concept:agent-company-os" con una fecha real, no una etiqueta suelta.

### Fase 4 -- Critica (3 lentes) + reescritura (`scripts/synthesize_article.py`)

Con `--llm hermes` (default): UNA llamada batcheada a `hermes -z` con
TODOS los hallazgos del dia (que_es, por_que_importa, madurez_senales y
relacion_grafo con `primera_mencion`), pidiendole al modelo que aplique
INTERNAMENTE 3 criterios de revision (ver `references/criterios-revision.md`
y `templates/lente-sistema.md`) y devuelva directamente el
`por_que_importa` ya reescrito -- sin pedir ni exponer las 3 criticas
como texto separado:

1. **Rigor tecnico**: claims sin sustento, clasificacion incoherente,
   falta de contexto tecnico.
2. **Claridad/accesibilidad**: jerga sin glosar, frases que solo se
   entienden con el link, redaccion criptica.
3. **Relevancia editorial**: por que le importa a un lector de CSS de
   forma concreta, y si `relacion_grafo` con `primera_mencion` se traduce
   en una fecha real ("ya cubrimos esto el 2026-07-16 con X") en vez de
   una referencia vaga ("el boletin de ayer").

Como al modelo nunca se le pide un texto de critica por separado -- solo
el resultado ya reescrito -- el objetivo de "no persistir reviews.json ni
nada equivalente" se cumple por construccion, no por disciplina de
borrado posterior. Rechaza automaticamente reescrituras que superen 2.5x
la longitud original o 1800 caracteres (limite absoluto contra
generacion desbocada) -- en la corrida real sobre los 10 dias, 3 items
fueron rechazados por esto y conservaron su texto pre-critica; ver
`stats.critica_notes`. Si no hay backend LLM, este paso corre en modo
passthrough (`stats.critica_lentes_aplicada = false`, motivo reportado en
`stats.critica_notes`) y el articulo se publica igual, solo sin esa capa.

### Fase 5 -- Editorial (`scripts/generate_editorial.py`)

- `--carry-forward <editorial.json existente>`: conserva el contenido
  (ya es bueno, revisado por Alejandro), solo ajusta el schema
  (`perfiles_involucrados` -> `lentes_aplicadas`) y repara mojibake UTF-8
  si aparece (detectado en los 10 `editorial.json` originales -- ver
  `MOJIBAKE_FIXES` en el script).
- Generacion nueva (sin carry-forward): requiere backend LLM real: cruza
  items del dia con boletines previos + el grafo + el stack conocido de
  Alejandro. Sale con error explicito si no hay backend -- nunca inventa
  sintesis editorial.

### Persistencia (`scripts/persist.py`)

Escribe `enriched.json` + `edges.jsonl` directamente a
`apps/web/src/data/boletines/<date>/` (el repo, fuente de verdad real).
Borra cualquier `reviews.json` v1 huerfano que quedara de una corrida
anterior. Actualiza el `state.json` propio de la skill en
`~/.hermes/data/tecnoboletin/state.json` (ver `references/state-schema.md`
v2) -- append-only, defensivo en lectura.

## Pitfalls (heredados y propios)

1. **CJK leak en espanol**: `scripts/clean_cjk.py` antes de cualquier
   `cp` al repo (patron heredado de `parallel-repo-explore-bulletin`,
   pitfall #17).
2. **`/tmp/` esta bloqueado**: scripts/intermedios a
   `~/.hermes/data/tecnoboletin/_work/` o `~/`. NO `/tmp/`.
3. **`python3 -c` y heredoc bloqueados** en el runtime del agente Hermes:
   escribe a fichero y ejecuta `python3 <file>`. (Nota: esta restriccion
   es del runtime del agente Hermes al operar sus propias tool calls: al
   depurar por SSH directo como humano/operador no aplica, pero los
   scripts de esta skill igual se escriben siempre a fichero por
   consistencia y reusabilidad.)
4. **`curl | python3` bloqueado**: descarga a fichero, procesa aparte.
5. **`hermes` no esta en el PATH de una sesion SSH no interactiva**:
   `hermes_client.py` lo busca explicitamente en `~/.local/bin/hermes`.
   Si se mueve o se reinstala en otra ruta, actualizar `HERMES_CANDIDATES`
   ahi. No instalar Ollama en esta maquina sin verificar margen de RAM
   primero (~11GB total, ~8GB en uso por otros servicios) -- no deberia
   hacer falta, `hermes -z` ya cubre el backend.
6. **Schema drift**: lectura defensiva en todos los scripts; nunca asumas
   que una estructura nueva es la unica que vas a ver.
7. **El LLM puede inventar metadatos o "pulir de mas"**: `enrich_items.py`
   rechaza pulidos vacios o >1.6x mas largos que el original;
   `synthesize_article.py` rechaza reescrituras >2.5x el original o >1800
   caracteres. Ambos limpian fugas de CJK del modelo (`strip_cjk`) antes
   de aceptar cualquier texto.
8. **Cada `hermes -z` es cara (~15-40s, agente completo)**: la pipeline
   batchea 1 llamada/dia por paso (2 llamadas/dia en total), nunca una
   llamada por item. Para batch de varios dias, procesa serializado (un
   `run.sh <fecha>` tras otro) -- `hermes -z` no soporta invocaciones
   paralelas fiables desde el mismo usuario.
9. **No mutar `codigosinsiesta-trends/state.json`**: es de solo lectura
   para esta skill (ver seccion Input/Output).
10. **Formato del `.md` origen varia entre fechas**: ver Fase 2 --
    `extract_items.py` es tolerante mediante deteccion de contenido
    normalizado, no una unica regex rigida. Si se agrega una fecha nueva
    con un formato no visto, correr `scripts/run.sh <fecha>` y revisar el
    `enriched.json` resultante antes de dar por buena la extraccion (no
    hay validacion automatica de conteo en produccion, solo se hizo una
    vez sobre el historico al disenar el parser).
11. **Labels de campos pueden venir con o sin negrita** (pitfall real
    descubierto en 2026-08-19): historico 2026-08-02..2026-08-14 usaba
    `- **Qué es**: ...` y `- **Por qué importa**: ...`. A partir del
    2026-08-15 alguien quito la negrita y el formato paso a `- Qué es: ...`
    / `- Por qué importa: ...`. `LABEL_LINE_RE` (scripts/extract_items.py)
    es tolerante a AMBAS variantes: acepta label en negrita `**...**` o
    label plano que empiece por mayuscula, y `classify_label()` filtra
    por frases conocidas. Si vuelve a cambiar el formato, ANADIR variante
    a la regex (no quitar las existentes -- el historico ya publicado las
    usa). Audit rapido para detectar regresiones de este tipo:
    ```bash
    python3 -c "import json; \
    d = json.loads(open('apps/web/src/data/boletines/<DATE>/enriched.json').read()); \
    print([(i['idx'], len(i['contenido'].get('por_que_importa',''))) \
           for i in d['items'] if i['seccion']=='hallazgo_principal'])"
    ```
    Si todos los `por_que_importa` salen con len 0 en un dia con campos
    en el `.md` origen, sospecha de este pitfall.

## Configuracion / Variables de entorno

| Variable | Default | Uso |
|---|---|---|
| `TECNOBOLETIN_LLM` | `hermes` | `hermes` o `none` -- backend de `enrich_items.py`/`synthesize_article.py` (ver "Estado del backend LLM"). `hermes` invoca `~/.local/bin/hermes -z` (MiniMax-M3, configurado en `~/.hermes/config.yaml`). |

## Verificacion (antes de declarar done)

- [ ] `state.json` (propio de la skill) refleja el boletin procesado
- [ ] `enriched.json` en el repo tiene `stats.items_total` coherente con
      el `.md` origen (contar encabezados de hallazgo + bullets de radar)
- [ ] Ningun item de `seccion=hallazgo_principal` con `que_es` o
      `por_que_importa` vacios si el `.md` origen si los traia
- [ ] `relacion_grafo` de al menos algunos items tiene `primera_mencion`
      no-null si el boletin no es el primero del historico
- [ ] CJK check limpio en `enriched.json` y `editorial.json`
- [ ] No existe `reviews.json` en el directorio de salida
- [ ] `grep -ri "carlos\|dani\|mar[ií]a\|honestidad"` sobre el output: sin
      resultados

## Scripts

- `scripts/extract_items.py` -- parser determinista v2 del `.md` a items
  con campos ricos
- `scripts/graph_crossref.py` -- cruce determinista contra el grafo
  acumulado (libreria + CLI de inspeccion)
- `scripts/hermes_client.py` -- backend LLM real: invoca `hermes -z`
  (Hermes Agent CLI, MiniMax-M3), parseo JSON tolerante (cierre de array
  faltante) y limpieza de fugas de CJK del modelo. Usado por
  `enrich_items.py` y `synthesize_article.py`.
- `scripts/enrich_items.py` -- conserva/pule contenido (1 llamada
  batcheada a `hermes -z` por dia), aplica cruce con el grafo, hereda
  clasificacion previa
- `scripts/synthesize_article.py` -- 3 lentes de critica + reescritura
  (1 llamada batcheada a `hermes -z` por dia; el modelo aplica los
  criterios internamente y devuelve solo el resultado, nunca una critica
  separada que haya que descartar despues)
- `scripts/generate_editorial.py` -- genera/actualiza `editorial.json`
  (carry-forward o LLM)
- `scripts/persist.py` -- escribe al repo (`enriched.json` + `edges.jsonl`)
  y actualiza el `state.json` de la skill
- `scripts/run.sh` -- orquesta las 5 fases end-to-end para una fecha
- `scripts/clean_cjk.py` -- saneo/deteccion de caracteres CJK (heredado)
- `scripts/cleanup_sess.py` -- saneo de caracteres fuera de espanol
  (heredado, complementa a `clean_cjk.py`; no cubre mojibake UTF-8 --
  para eso ver `MOJIBAKE_FIXES` en `generate_editorial.py`)

## Templates

- `templates/polish-prompt.md` -- prompt de pulido (conserva contenido,
  no lo sustituye)
- `templates/lente-sistema.md` -- system prompts de las 3 lentes de
  critica (rigor tecnico, claridad, relevancia editorial)
- `templates/enriched-vista-humana.md` -- esqueleto opcional de vista
  humana para revision rapida

## Referencias

- `references/item-schema.json` -- shape exacto del item enriquecido v2
- `references/criterios-revision.md` -- detalle de las 3 lentes de
  critica editorial (reemplaza a `perfiles.md`)
- `references/state-schema.md` -- campos y convenciones del `state.json`
  propio de la skill (v2)

## Pagina web (Astro)

- `apps/web/src/pages/enriquecido/[date].astro` -- pagina por dia:
  sintesis editorial arriba, hallazgos con "por que importa" +
  "relacion con el grafo" pulidos como cuerpo principal (tipo/tema/
  confianza como metadata discreta), edges del grafo colapsables al
  final. **Sin seccion de reviews.**
- `apps/web/src/pages/enriquecido/index.astro` -- indice de boletines. Ya
  no menciona "perfiles sinteticos".
