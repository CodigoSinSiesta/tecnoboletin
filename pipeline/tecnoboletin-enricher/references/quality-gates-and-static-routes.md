# Gates de calidad y fichas estáticas

## Por qué el pipeline debe fallar cerrado

Los boletines de origen cambian de formato con el tiempo. Si el extractor no reconoce etiquetas o encabezados, puede producir títulos y URLs pero dejar descripción, relevancia, métricas y relaciones vacías. El LLM de pulido está instruido para devolver vacíos cuando la entrada está vacía; eso evita inventar, pero no recupera datos perdidos. Por eso valida antes del LLM y de nuevo antes de persistir.

## Campos mínimos

- Hallazgo principal: título, una URL de GitHub, qué es, por qué importa, señales de madurez, acción y al menos una relación del grafo.
- Radar: título, URL, descripción y acción. La madurez puede faltar en formatos antiguos; si existe en el origen, conservarla.
- Findings con varios repos pueden declarar `urls_adicionales`; cada URL representa una ruta de ficha adicional y debe ser una identidad GitHub verificable.

`validate_quality.py` soporta `extraction` y `enriched`, informa los campos ausentes y devuelve código distinto de cero. `run.sh` lo ejecuta tras extracción, síntesis y CJK-check. `persist.py` repite el gate antes de tocar JSON publicable o state. Build verde no reemplaza estas comprobaciones.

## Diagnóstico de fichas `/repo/<owner>/<repo>/`

Astro genera las rutas en `apps/web/src/pages/repo/[...slug].astro:getStaticPaths()`, leyendo los `enriched.json` de `apps/web/src/data/boletines/`. El slug sale del título o de `url` mediante `repoSlug()`; no se deriva del Markdown ni del grafo. Para un 404 verifica en orden:

1. ¿Está el repo en un item del `enriched.json` procesado y publicado?
2. ¿Está presente en el listado de slugs de `repoSlugs()` y se generó `dist/repo/<owner>/<repo>/index.html`?
3. ¿Se incluyó ese JSON/código en el commit y el deploy terminó?

Para hallazgos multi-repo, conserva `urls_adicionales` y crea una ficha para cada repo; los datos de descripción pueden continuar compartiendo el hallazgo original. Un build local solo valida el artefacto local, nunca prueba que GitHub Pages ya lo desplegó.

## Pruebas de regresión

Ejecuta `python3 -m unittest discover -s pipeline/tecnoboletin-enricher/tests -v`. Casos base: formatos recientes del 20, 21, 23 y 26 de octubre; gate rojo si falta un campo; persistencia rechazada antes de escribir; y todos los repos del hallazgo múltiple conservan identidad.
