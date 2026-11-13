---
name: tecnoboletin-enricher
description: "Skill para enriquecer, auditar y publicar boletines diarios de tendencias IA/dev de Código Sin Siesta."
tags: [boletines, enriquecimiento, llm, editorial, cron, tecnoboletin]
metadata:
  hermes:
    category: research
---
# Tecnoboletín Enricher

Workflow para auditar, enriquecer, validar y publicar los boletines de tendencias de Código Sin Siesta. La skill canónica detallada está en `~/.hermes/skills/research/tecnoboletin-enricher/`; usa también `references/historical-bulletin-audit.md` para auditar días históricos antes de repararlos/publicarlos.

## Publicación git del cron (`~/.hermes/scripts/tecnoboletin-daily.sh`)

- El script commitea solo `apps/web/src/data/boletines/<DATE>/` y `knowledge-graph.json`; nunca `git add -A`.
- Antes de empujar comprueba si `origin/main` está **ya contenido** en HEAD (`git merge-base --is-ancestor origin/main HEAD`). Si la comprobación se invierte, el rebase se lanza incluso cuando solo vamos por delante y cualquier fichero sin commitear lo tumba con `cannot rebase: You have unstaged changes`.
- El rebase va con `--autostash` para que cambios ajenos al boletín no bloqueen la publicación, y el `push` tiene un reintento acotado (fetch + rebase + push) por si el remoto se mueve entre el fetch y el push.
- Si el árbol acumula trabajo sin commitear ajeno al cron, commitearlo o sacarlo del checkout: un árbol sucio crónico es la causa típica de fallos repetidos en días consecutivos.

## Backend LLM: por qué se degrada el enriquecido

- `hermes --version` **no es un sondeo barato**: imprime el estado de actualizaciones y, cuando caduca su caché de 6 h, consulta la red. Con un timeout de 15 s se quedaba colgado y `hermes_available()` devolvía "no disponible", lo que degradaba el día entero a `--llm none` (sin pulido ni crítica) y, en `generate_editorial.py`, abortaba la generación del editorial.
- El sondeo tolera ahora un timeout de 60 s y, si expira, deja pasar la ejecución: la llamada real (`hermes -z`, 240 s) es la que decide. Un stall del chequeo de versiones no debe apagar la capa editorial.
- `run.sh` reintenta el editorial 2 veces (fallo transitorio típico); si aun así falla, el cron publica el día sin síntesis y lo dice explícitamente en el mensaje, en vez de abortar y dejar el día sin commit ni push.
- Señal de diagnóstico: `stats.llm_backend='none'` o `stats.critica_lentes_aplicada=false` en el `enriched.json` del día, con el motivo en `stats.critica_notes`.

## Fail-closed

- Extraer del Markdown original antes de confiar en `enriched.json`; el JSON publicado permite detectar síntomas, no distinguir por sí solo un fallo del parser de un campo que nunca estuvo en la fuente.
- Comparar conteos por sección y campos relevantes por item. Clasificar vacíos como bug del parser, falta legítima en la fuente o formato no soportado.
- Mantener el gate estricto para publicar, pero no aplicar requisitos de una generación moderna universalmente a datos históricos. No inventar metadata ausente ni relajar gates sin documentar schemas y agregar regresiones.
- Probar formatos representativos: h4 sin numerar, h3 numerado, etiquetas antiguas (`Una frase`, `Acción`), texto explicativo en radar y relaciones en bullets. Ver `references/historical-bulletin-audit.md`.
- Antes de publicar reparaciones, ejecutar tests, validación de calidad del JSON completo y build. Informar por separado días auditados, reparados, publicados y pendientes.