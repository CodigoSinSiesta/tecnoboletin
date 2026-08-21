#!/usr/bin/env python3
"""persist.py (v2) -- escribe el enriched.json final + edges.jsonl al REPO
(fuente de verdad real que consume la web -- ver SKILL.md) y actualiza el
state.json propio de la skill.

Reemplaza al v1: ya NO consolida reviews de perfiles (no existen mas) ni
genera reviews.json. Los edges se derivan deterministamente de
`relacion_grafo` de cada item (ya no de tema_principal/temas_secundarios
como en v1 -- esos siguen disponibles como metadata pero los edges reales
del boletin son los que trae el propio contenido editorial).

Uso: persist.py --date YYYY-MM-DD --enriched <enriched.json de enrich_items o synthesize_article>
     [--repo-data-dir ~/proyectos/tecnoboletin/apps/web/src/data/boletines]
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from datetime import datetime, timezone
from pathlib import Path

SKILL_STATE_DIR = Path("~/.hermes/data/tecnoboletin").expanduser()
SKILL_STATE_PATH = SKILL_STATE_DIR / "state.json"
DEFAULT_REPO_DATA_DIR = Path("~/proyectos/tecnoboletin/apps/web/src/data/boletines").expanduser()


def edge_id(tipo: str, *parts: str) -> str:
    parts = [p for p in parts if p]
    return f"{tipo}:" + ":".join(parts)


def build_edges(enriched: dict, date: str) -> list[dict]:
    edges = []
    for item in enriched.get("items", []):
        url = item.get("url", "")
        url_slug = re.sub(r"[^a-z0-9]+", "-", url.lower())[:60].strip("-")
        item_node = edge_id("item", url_slug or f"idx-{item['idx']}")

        edges.append({"src": edge_id("boletin", date), "dst": item_node, "rel": "menciona", "added": date})

        c = item.get("clasificacion", {})
        tema = c.get("tema_principal", "")
        if tema:
            edges.append({"src": item_node, "dst": edge_id("tema", tema), "rel": "trata", "added": date})
        for sec in c.get("temas_secundarios") or []:
            if sec:
                edges.append({"src": item_node, "dst": edge_id("tema", sec), "rel": "trata", "added": date})

        # edges reales del contenido editorial (los que el boletin origen ya trae)
        for triple in item.get("relacion_grafo", []):
            edges.append({
                "src": triple["src"],
                "dst": triple["dst"],
                "rel": triple["rel"],
                "added": date,
                "primera_mencion": triple.get("primera_mencion"),
            })
    return edges


def main() -> int:
    ap = argparse.ArgumentParser(description="Persiste enriched.json + edges.jsonl al repo y actualiza state.json de la skill")
    ap.add_argument("--date", type=str, required=True)
    ap.add_argument("--enriched", type=Path, required=True)
    ap.add_argument("--repo-data-dir", type=Path, default=DEFAULT_REPO_DATA_DIR)
    args = ap.parse_args()

    if not args.enriched.exists():
        print(f"ERROR: no encontrado {args.enriched}", file=sys.stderr)
        return 1

    enriched = json.loads(args.enriched.read_text(encoding="utf-8"))
    edges = build_edges(enriched, args.date)

    out_dir = args.repo_data_dir / args.date
    out_dir.mkdir(parents=True, exist_ok=True)

    out_enriched = out_dir / "enriched.json"
    out_enriched.write_text(json.dumps(enriched, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"Escrito: {out_enriched}", file=sys.stderr)

    out_edges = out_dir / "edges.jsonl"
    with out_edges.open("w", encoding="utf-8") as f:
        for e in edges:
            f.write(json.dumps(e, ensure_ascii=False) + "\n")
    print(f"Escrito: {out_edges} ({len(edges)} edges)", file=sys.stderr)

    # reviews.json v1 queda obsoleto -- si existe uno de una corrida anterior
    # para esta fecha, se elimina (no debe quedar huerfano en el repo).
    old_reviews = out_dir / "reviews.json"
    if old_reviews.exists():
        old_reviews.unlink()
        print(f"Eliminado (obsoleto): {old_reviews}", file=sys.stderr)

    # --- state.json propio de la skill (append-only, defensivo) ---
    SKILL_STATE_DIR.mkdir(parents=True, exist_ok=True)
    state = {}
    if SKILL_STATE_PATH.exists():
        try:
            state = json.loads(SKILL_STATE_PATH.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            state = {"_warning": "state.json corrupto en lectura previa"}

    boletines = state.setdefault("boletines_procesados", {})
    stats = enriched.get("stats", {})
    boletines[args.date] = {
        "schema_version": 2,
        "items_total": stats.get("items_total", len(enriched.get("items", []))),
        "items_hallazgo_principal": stats.get("items_hallazgo_principal"),
        "items_radar_secundario": stats.get("items_radar_secundario"),
        "edges_generados": len(edges),
        "llm_backend": stats.get("llm_backend", "none"),
        "critica_lentes_aplicada": stats.get("critica_lentes_aplicada", False),
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }
    state["last_run"] = datetime.now(timezone.utc).isoformat()
    state["last_run_at"] = args.date
    state["schema_versions"] = {"item": 2, "graph_edge": 2}
    SKILL_STATE_PATH.write_text(json.dumps(state, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"State actualizado: {SKILL_STATE_PATH}", file=sys.stderr)

    return 0


if __name__ == "__main__":
    sys.exit(main())
