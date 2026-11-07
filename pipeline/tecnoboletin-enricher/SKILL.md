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

## Fail-closed

- Extraer del Markdown original antes de confiar en `enriched.json`; el JSON publicado permite detectar síntomas, no distinguir por sí solo un fallo del parser de un campo que nunca estuvo en la fuente.
- Comparar conteos por sección y campos relevantes por item. Clasificar vacíos como bug del parser, falta legítima en la fuente o formato no soportado.
- Mantener el gate estricto para publicar, pero no aplicar requisitos de una generación moderna universalmente a datos históricos. No inventar metadata ausente ni relajar gates sin documentar schemas y agregar regresiones.
- Probar formatos representativos: h4 sin numerar, h3 numerado, etiquetas antiguas (`Una frase`, `Acción`), texto explicativo en radar y relaciones en bullets. Ver `references/historical-bulletin-audit.md`.
- Antes de publicar reparaciones, ejecutar tests, validación de calidad del JSON completo y build. Informar por separado días auditados, reparados, publicados y pendientes.

Esta entrada de clase proporciona los pasos críticos para auditorías históricas y evita que una revisión superficial del JSON dispare regeneraciones masivas inseguras.