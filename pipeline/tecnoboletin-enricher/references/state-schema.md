# State schema -- tecnoboletin-enricher (v2)

`state.json` en `~/.hermes/data/tecnoboletin/`. Append-only; nunca se
borra historia; defensivo en lectura. Es el state PROPIO de la skill
(seguimiento de que se proceso y con que backend) -- no confundir con
`~/.hermes/data/codigosinsiesta-trends/state.json`, que es el grafo de
conocimiento acumulado por el cron del boletin original y que esta skill
solo LEE (nunca escribe) para el cruce de `graph_crossref.py`.

## Top-level shape (v2)

```json
{
  "version": 2,
  "last_run": "ISO 8601 UTC",
  "last_run_at": "YYYY-MM-DD",
  "schema_versions": { "item": 2, "graph_edge": 2 },
  "boletines_procesados": {
    "YYYY-MM-DD": {
      "schema_version": 2,
      "items_total": 14,
      "items_hallazgo_principal": 6,
      "items_radar_secundario": 8,
      "edges_generados": 42,
      "llm_backend": "none",
      "critica_lentes_aplicada": false,
      "timestamp": "ISO 8601 UTC"
    }
  },
  "pending_issues": []
}
```

## Cambios respecto a v1

- Eliminados: `reviews_done`, `reviews_with_feedback`, `modelo_actual` /
  `modelo_cambios` (ya no hay 3 perfiles con modelo fijo; el backend LLM
  se registra por-corrida en `llm_backend`), `rejected_acumulado` (v2 no
  descarta items silenciosamente -- si `extract_items.py` no encuentra un
  campo, queda vacio, nunca se omite el item entero).
- Nuevo: `critica_lentes_aplicada` -- trazabilidad explicita de si el paso
  de `synthesize_article.py` corrio con backend LLM real o en modo
  passthrough.

## Pitfalls manejo del state

- **Defensivo en lectura**: nunca asumas campos top-level existen.
- **Append-only**: nunca borres entradas de `boletines_procesados`.
- **No mutar el grafo de codigosinsiesta-trends**: esta skill es
  consumidora de solo lectura de ese state.json. Cualquier nodo/edge nuevo
  que un hallazgo del boletin proponga se queda en `edges.jsonl` del repo
  (para uso editorial), no se escribe de vuelta al grafo acumulado --
  eso es responsabilidad exclusiva del cron de
  `codigosinsiesta-trends-bulletin`.

## Como extender sin romper

1. Anade campo nuevo en top-level con `default` implicito (no en codigo).
2. Lee siempre con `.get('campo', default)`.
3. Cuando escribas, preserva todos los campos anteriores (full
   read-modify-write) -- `persist.py` ya lo hace.
4. Documenta el cambio en esta referencia.
