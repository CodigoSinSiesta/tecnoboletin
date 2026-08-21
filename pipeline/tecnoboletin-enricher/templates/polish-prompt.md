# Prompt de pulido -- enrich_items.py

Reemplaza a `classify-prompt.md`. Diferencia central: el prompt v1 le
pedia al LLM que GENERARA un `resumen_2_lineas` que sustituia el contenido
del boletin origen. Este prompt hace lo contrario: pide CONSERVAR el
contenido y solo pulir gramatica/claridad.

## Variables de sustitucion

Se aplica por separado a cada campo rico ya extraido
(`que_es`, `por_que_importa`) -- nunca a los dos juntos, y nunca a
`madurez_senales` ni `accion_sugerida` (esos se conservan literales, son
datos verificados/decisiones, no prosa a pulir).

- `{{TEXTO}}` -> el campo a pulir (que_es o por_que_importa), ya extraido
  deterministicamente del boletin origen por `extract_items.py`.

## Prompt (texto plano)

```
Eres un editor de espanol tecnico. Recibes un fragmento de texto ya
escrito para un boletin de tendencias IA/dev. Tu unico trabajo es pulir
gramatica, puntuacion y claridad -- SIN anadir hechos, cifras, nombres o
afirmaciones que no esten ya en el texto. No resumas, no acortes el
contenido salvo redundancia obvia. Si el texto ya esta bien, devuelvelo
igual.

TEXTO:
{{TEXTO}}

Devuelve SOLO el texto pulido, sin comillas ni comentarios.
```

## Validacion defensiva

`enrich_items.py` rechaza automaticamente cualquier respuesta del LLM que:

- venga vacia, o
- sea mas de 1.6x mas larga que el original (senal de que invento
  contenido en vez de solo pulir).

En esos casos se conserva el texto original sin pulir -- nunca se publica
un pulido sospechoso.

## Clasificacion (metadata secundaria)

La `clasificacion` (tipo/idioma/autor/medio/tema_principal/
temas_secundarios/confianza) sigue siendo util como metadata discreta
(tags/filtros), pero ya NO protagoniza el item. Si existe un
`enriched.json` v1 previo para la misma fecha, se conserva su
clasificacion tal cual (join por URL, ver `--carry-metadata-from` en
`enrich_items.py`) en vez de reclasificar. Solo se pide clasificacion
nueva vía LLM cuando no hay metadata previa que conservar.
