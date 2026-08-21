#!/usr/bin/env python3
"""graph_crossref.py -- cruza triples 'relacion_grafo' contra el grafo
acumulado de codigosinsiesta-trends para anotar "primera_mencion".

No es un paso LLM: es una consulta determinista sobre
~/.hermes/data/codigosinsiesta-trends/state.json (knowledge_graph.edges),
que ya trae `added: YYYY-MM-DD` en cada edge. Para un triple
`src --rel--> dst` de un item del boletin de la fecha X, busca la fecha mas
antigua (anterior a X) en la que `dst` (o `src`) ya aparecia en el grafo
acumulado -- si existe, es la primera vez que ese nodo/concepto fue
cubierto, y se anota como `primera_mencion`. Si no hay ninguna mencion
anterior a X, `primera_mencion` queda en null (es la primera vez que
aparece, punto).

Uso como libreria:
    from graph_crossref import GraphIndex
    gi = GraphIndex.load()
    triples_anotados = gi.annotate(triples, current_date)

Uso como CLI (debug/inspeccion):
    graph_crossref.py --date YYYY-MM-DD --node concept:agent_company_os
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

TRENDS_STATE = Path("~/.hermes/data/codigosinsiesta-trends/state.json").expanduser()


class GraphIndex:
    def __init__(self, first_seen: dict[str, str], node_types: dict[str, str]):
        # first_seen: node_id -> fecha (YYYY-MM-DD) mas antigua en la que
        # aparece como src o dst de algun edge con 'added'.
        self.first_seen = first_seen
        self.node_types = node_types

    @classmethod
    def load(cls, path: Path = TRENDS_STATE) -> "GraphIndex":
        if not path.exists():
            return cls({}, {})
        try:
            state = json.loads(path.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            return cls({}, {})

        kg = state.get("knowledge_graph", {})
        edges = kg.get("edges", [])
        nodes = kg.get("nodes", {})

        first_seen: dict[str, str] = {}
        for e in edges:
            added = e.get("added")
            if not added:
                continue
            for node_id in (e.get("src"), e.get("dst")):
                if not node_id:
                    continue
                if node_id not in first_seen or added < first_seen[node_id]:
                    first_seen[node_id] = added

        node_types = {nid: n.get("type", "") for nid, n in nodes.items()}
        return cls(first_seen, node_types)

    @staticmethod
    def _normalize(node_id: str) -> str:
        """Boletines antiguos escriben triples sin prefijo de tipo
        (ej. 'thedotmack/claude-mem' en vez de 'repo:thedotmack/claude-mem').
        Si el id ya trae un prefijo conocido, se deja igual; si parece
        'owner/repo' se antepone 'repo:'; en otro caso se antepone
        'concept:' como mejor esfuerzo (es el tipo mas comun en estos
        triples para nodos sin barra)."""
        if ":" in node_id:
            return node_id
        if "/" in node_id:
            return f"repo:{node_id}"
        return f"concept:{node_id}"

    def lookup_first_seen(self, node_id: str) -> str | None:
        for candidate in (node_id, self._normalize(node_id)):
            if candidate in self.first_seen:
                return self.first_seen[candidate]
        return None

    def annotate(self, triples: list[dict], current_date: str) -> list[dict]:
        out = []
        for t in triples:
            annotated = dict(t)
            primera = None
            for node_id in (t.get("dst"), t.get("src")):
                if not node_id:
                    continue
                fs = self.lookup_first_seen(node_id)
                if fs and fs < current_date:
                    if primera is None or fs < primera:
                        primera = fs
            annotated["primera_mencion"] = primera
            out.append(annotated)
        return out


def main() -> int:
    ap = argparse.ArgumentParser(description="Inspecciona el indice de primera-mencion del grafo")
    ap.add_argument("--node", type=str, help="node id a buscar, ej. concept:agent_company_os")
    ap.add_argument("--date", type=str, default="9999-99-99", help="fecha de referencia (solo informativa aqui)")
    args = ap.parse_args()

    gi = GraphIndex.load()
    print(f"Nodos indexados: {len(gi.first_seen)}", file=sys.stderr)
    if args.node:
        fs = gi.lookup_first_seen(args.node)
        print(json.dumps({"node": args.node, "first_seen": fs}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    sys.exit(main())
