# Auditoría de boletines históricos

Cómo revisar días ya publicados antes de regenerar o publicar correcciones.

## Procedimiento

1. Recorrer `apps/web/src/data/boletines/*/enriched.json` y, por cada item, comprobar los campos obligatorios de su sección:
   - `hallazgo_principal`: `que_es`, `por_que_importa`, `madurez_senales`, `accion_sugerida`, una URL y `relacion_grafo` no vacía.
   - `radar_secundario`: `que_es`, `accion_sugerida` y URL.
2. Para cada día sospechoso, comparar con su Markdown de origen `~/obsidian-vault/Research/Boletines/<DATE>-trending.md` y volver a extraer con `scripts/extract_items.py`.
3. Clasificar cada vacío en una de tres causas:
   - **Bug del parser**: la fuente sí trae el campo con otra etiqueta o encabezado. Se arregla en el extractor y se añade regresión.
   - **Falta legítima en la fuente**: el Markdown nunca trajo ese dato (p. ej. radar antiguo sin acción). No se inventa; se documenta y el gate histórico lo tolera.
   - **Formato no soportado**: encabezado o estructura desconocida. Se añade patrón y regresión.
4. Escribir las regresiones con fechas reales del vault (no fixtures inventados) para que cualquier cambio futuro del parser se valide contra el histórico.

## Formatos encontrados en el histórico

- h4 numerado con enlace: `#### 1. [owner/repo](https://…) — subtítulo`.
- h4 numerado plano: `#### 1. owner/repo — subtítulo`.
- h4 sin numerar, solo slug: `#### owner/repo`.
- h3 numerado: `### 1. owner/repo — subtítulo`.
- Etiquetas con negrita y dos puntos dentro: `- **Qué es**: …`.
- Etiquetas sin negrita: `- Qué es: …`.
- Etiquetas antiguas: `- Una frase: …` (equivale a `que_es`), `- Acción: …` (equivale a `accion_sugerida`).
- Relaciones de grafo en una sola línea separadas por `·`, o en bullets sueltos bajo la etiqueta.
- Texto corrido justo después de `Radar secundario` ("Cada item lleva URL…") que no debe tratarse como item.

## Reglas

- No regenerar ni publicar un día solo porque el JSON tenga vacíos: primero determinar la causa.
- No rellenar metadata ausente con texto inventado ni con LLM sin fuente.
- Al reparar, publicar por separado (un commit por día o por bloque coherente) y verificar la URL pública después del deploy.
- Los gates de publicación modernos son más estrictos que los formatos antiguos: no aplicar el contrato actual retroactivamente a datos históricos sin documentarlo.
