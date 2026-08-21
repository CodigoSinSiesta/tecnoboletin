#!/usr/bin/env python3
"""export_graph.py -- vuelca knowledge_graph.{nodes,edges} de state.json al
formato {nodes:[...], links:[...]} que consume 3d-force-graph, dejando el
resultado en el repo del sitio para que se publique junto al resto de datos.

Deterministico, sin LLM. No inventa nada: los nodos referenciados solo como
id de un edge (sin entrada propia en el dict de nodos) se marcan
synthetic=true con name/type inferidos por heuristica de patron de id, nunca
con datos de negocio (stars, descripcion, etc.) que no existen en la fuente.
"""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path

STATE_PATH = Path.home() / ".hermes/data/codigosinsiesta-trends/state.json"
BOLETINES_DIR = Path.home() / "proyectos/tecnoboletin/apps/web/src/data/boletines"
OUT_PATH = Path.home() / "proyectos/tecnoboletin/apps/web/public/data/knowledge-graph.json"

REPO_SLUG_RE = re.compile(r"^[\w.-]+/[\w.-]+$")
DATE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")
MD_NOISE_RE = re.compile(r"\*\*|`")


def infer_type_and_name(node_id: str) -> tuple[str, str]:
    if ":" in node_id:
        prefix, rest = node_id.split(":", 1)
        return prefix, rest.replace("_", " ").replace("-", " ")
    if REPO_SLUG_RE.match(node_id):
        return "repo", node_id
    return "concept", node_id.replace("_", " ").replace("-", " ")


PREFIXES = ("repo:", "concept:", "company:", "tool:", "framework:", "protocol:")


def build_alias_map(node_ids: set[str], endpoint_ids: set[str]) -> dict[str, str]:
    """Los edges a veces referencian la misma entidad con y sin prefijo de tipo
    (p.ej. 'anthropics/claude-code' vs 'repo:anthropics/claude-code'), lo que
    parte un nodo real en dos. Canonicaliza: (1) al id que existe en el dict de
    nodos si solo una forma existe ahi; (2) entre endpoints que solo aparecen en
    edges, a la forma prefijada (conserva el tipo). Si ambas formas tienen ficha
    propia en el dict, no toca nada."""
    aliases: dict[str, str] = {}
    for nid in node_ids:
        if ":" in nid:
            prefix, bare = nid.split(":", 1)
            if f"{prefix}:" in PREFIXES and bare not in node_ids:
                aliases[bare] = nid
        else:
            for prefix in PREFIXES:
                cand = prefix + nid
                if cand not in node_ids:
                    aliases[cand] = nid
    for eid in endpoint_ids:
        if ":" not in eid or eid in node_ids or eid in aliases:
            continue
        prefix, bare = eid.split(":", 1)
        if f"{prefix}:" in PREFIXES and bare in endpoint_ids and bare not in node_ids and bare not in aliases:
            aliases[bare] = eid
    return aliases


def normalize_edge(raw: dict, aliases: dict[str, str]) -> dict | None:
    src = raw.get("src") or raw.get("source") or raw.get("from")
    dst = raw.get("dst") or raw.get("target") or raw.get("to")
    rel = raw.get("rel") or raw.get("relation")
    if not src or not dst or not rel:
        return None
    src = aliases.get(src, src)
    dst = aliases.get(dst, dst)
    edge = {"source": src, "target": dst, "rel": rel}
    if "added" in raw:
        edge["added"] = raw["added"]
    if "note" in raw:
        edge["note"] = raw["note"]
    if "confidence" in raw:
        edge["confidence"] = raw["confidence"]
    return edge


def collect_appearances() -> tuple[dict[str, list[dict]], dict[str, set[str]]]:
    """Recorre los enriched.json ya publicados y construye, por id de nodo:
    - apariciones como protagonista: el nodo ES el item del boletin
      (fecha, titulo del item, seccion, y su que_es como resumen)
    - fechas en las que se le menciona como destino de una relacion
    Todo sale literal de los boletines publicados; no se inventa nada."""
    protagonist: dict[str, list[dict]] = {}
    mentioned: dict[str, set[str]] = {}
    if not BOLETINES_DIR.exists():
        return protagonist, mentioned
    for day_dir in sorted(BOLETINES_DIR.iterdir()):
        if not day_dir.is_dir() or not DATE_RE.match(day_dir.name):
            continue
        enriched = day_dir / "enriched.json"
        if not enriched.exists():
            continue
        try:
            data = json.loads(enriched.read_text())
        except json.JSONDecodeError:
            continue
        date = data.get("date", day_dir.name)
        for item in data.get("items", []):
            titulo = item.get("titulo") or ""
            seccion = item.get("seccion") or ""
            que_es = (item.get("contenido") or {}).get("que_es") or ""
            own_ids: set[str] = set()
            for rel in item.get("relacion_grafo") or []:
                src = rel.get("src")
                dst = rel.get("dst")
                if src:
                    own_ids.add(src)
                if dst:
                    mentioned.setdefault(dst, set()).add(date)
            if REPO_SLUG_RE.match(titulo):
                own_ids.add(f"repo:{titulo}")
            for oid in own_ids:
                protagonist.setdefault(oid, []).append(
                    {
                        "date": date,
                        "titulo": titulo,
                        "seccion": seccion,
                        "resumen": MD_NOISE_RE.sub("", que_es)[:280],
                    }
                )
    return protagonist, mentioned


def main() -> int:
    if not STATE_PATH.exists():
        print(f"no existe {STATE_PATH}", file=sys.stderr)
        return 1

    state = json.loads(STATE_PATH.read_text())
    kg = state.get("knowledge_graph", {})
    raw_nodes: dict = kg.get("nodes", {})
    raw_edges: list = kg.get("edges", [])

    endpoint_ids = set()
    for raw in raw_edges:
        for key in ("src", "source", "from"):
            if raw.get(key):
                endpoint_ids.add(raw[key])
        for key in ("dst", "target", "to"):
            if raw.get(key):
                endpoint_ids.add(raw[key])

    aliases = build_alias_map(set(raw_nodes.keys()), endpoint_ids)

    protagonist_raw, mentioned_raw = collect_appearances()
    protagonist: dict[str, list] = {}
    for key, apps in protagonist_raw.items():
        protagonist.setdefault(aliases.get(key, key), []).extend(apps)
    mentioned: dict[str, set] = {}
    for key, dates in mentioned_raw.items():
        mentioned.setdefault(aliases.get(key, key), set()).update(dates)

    links = []
    degree: dict[str, int] = {}
    skipped = 0
    for raw in raw_edges:
        edge = normalize_edge(raw, aliases)
        if edge is None:
            skipped += 1
            continue
        links.append(edge)
        degree[edge["source"]] = degree.get(edge["source"], 0) + 1
        degree[edge["target"]] = degree.get(edge["target"], 0) + 1

    node_ids = set(degree.keys()) | set(raw_nodes.keys())

    nodes = []
    synthetic_count = 0
    for node_id in sorted(node_ids):
        base = raw_nodes.get(node_id)
        if base:
            fallback_name = node_id.split(":", 1)[1] if ":" in node_id else node_id
            node = {
                "id": node_id,
                "name": base.get("name") or fallback_name,
                "type": base.get("type", "concept"),
                "degree": degree.get(node_id, 0),
            }
            if base.get("description"):
                node["description"] = base["description"]
            if base.get("stars") is not None:
                node["stars"] = base["stars"]
            if base.get("lang"):
                node["lang"] = base["lang"]
        else:
            inferred_type, inferred_name = infer_type_and_name(node_id)
            node = {
                "id": node_id,
                "name": inferred_name,
                "type": inferred_type,
                "degree": degree.get(node_id, 0),
                "synthetic": True,
            }
            synthetic_count += 1

        apps = protagonist.get(node_id)
        if apps:
            # Una entrada por fecha (la ultima gana), orden descendente.
            by_date: dict[str, dict] = {}
            for app in sorted(apps, key=lambda a: a["date"]):
                by_date[app["date"]] = app
            node["apariciones"] = list(by_date.values())[::-1]
            # El resumen del nodo sale literal del que_es del boletin mas
            # reciente donde fue protagonista -- no se redacta nada nuevo.
            latest = node["apariciones"][0]
            if latest.get("resumen"):
                node["resumen"] = latest["resumen"]
            for app in node["apariciones"]:
                app.pop("resumen", None)
        prot_dates = {a["date"] for a in (apps or [])}
        extra_mentions = sorted(
            (d for d in mentioned.get(node_id, set()) if d not in prot_dates),
            reverse=True,
        )
        if extra_mentions:
            node["menciones"] = extra_mentions

        nodes.append(node)

    out = {
        "generated_at": state.get("last_run_at"),
        "node_count": len(nodes),
        "link_count": len(links),
        "nodes": nodes,
        "links": links,
    }

    OUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    OUT_PATH.write_text(json.dumps(out, ensure_ascii=False, indent=None, separators=(",", ":")))

    print(
        f"OK: {len(nodes)} nodos ({synthetic_count} sinteticos), "
        f"{len(links)} enlaces ({skipped} edges omitidos por campos faltantes) "
        f"-> {OUT_PATH}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
