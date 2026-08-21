# Vista humana -- draft opcional para revision rapida

Esqueleto opcional (no forma parte del pipeline critico) para generar un
vistazo rapido de un dia ya procesado, util al revisar antes de publicar.
No sustituye a `apps/web/src/data/boletines/<DATE>/{enriched.json,editorial.json}`,
que es la fuente real que consume la web.

```markdown
---
date: YYYY-MM-DD
boletin_origen: <basename>.md
items_total: N
hallazgos: M
radar: K
critica_lentes_aplicada: true|false
---

# Tecnoboletin {{ date }}

## Lectura editorial

{{ editorial.posicionamiento }}

## Hallazgos ({{ items_hallazgo_principal }})

{% for item in items if item.seccion == "hallazgo_principal" %}
### {{ item.titulo }}

**Que es**: {{ item.contenido.que_es }}
**Por que importa**: {{ item.contenido.por_que_importa }}
**Madurez**: {{ item.contenido.madurez_senales }}
**Accion sugerida**: {{ item.contenido.accion_sugerida }}
**Relacion con el grafo**:
{% for t in item.relacion_grafo %}
- `{{ t.src }} --{{ t.rel }}--> {{ t.dst }}` {% if t.primera_mencion %}(ya cubierto el {{ t.primera_mencion }}){% endif %}
{% endfor %}

{% endfor %}

## Radar secundario ({{ items_radar_secundario }})

{% for item in items if item.seccion == "radar_secundario" %}
- **{{ item.titulo }}** ({{ item.contenido.madurez_senales }}) -- {{ item.contenido.que_es }}. Accion: {{ item.contenido.accion_sugerida }}
{% endfor %}
```

## Reglas

- Idioma: espanol
- Sin CJK (CJK check obligatorio antes de persistir -- `clean_cjk.py`)
- Sin hype, sin marketing
- Sin emojis
- NO incluye ninguna seccion de "reviews" ni nombres de persona -- el
  pipeline v2 no genera ese artefacto (ver `references/criterios-revision.md`)
