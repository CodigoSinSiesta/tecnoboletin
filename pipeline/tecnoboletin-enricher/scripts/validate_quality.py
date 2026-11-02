#!/usr/bin/env python3
"""Fail closed on missing source/publishable bulletin fields."""
import argparse
import json
import sys
from pathlib import Path


def validate(data):
    errors = []
    items = data.get("items")
    if not isinstance(items, list) or not items:
        return ["no hay items"]
    for item in items:
        title = item.get("titulo", f"idx={item.get('idx', '?')}")
        content = item.get("contenido") or {}
        urls = [item.get("url", ""), *(item.get("urls_adicionales") or [])]
        if not any(str(url).strip() for url in urls):
            errors.append(f"{title}: url vacia")
        if not str(item.get("titulo", "")).strip():
            errors.append(f"{title}: titulo vacio")
        section = item.get("seccion")
        if section == "hallazgo_principal":
            required = ("que_es", "por_que_importa", "madurez_senales", "accion_sugerida")
            for field in required:
                if not str(content.get(field, "")).strip():
                    errors.append(f"{title}: {field} vacio")
            if not item.get("relacion_grafo"):
                errors.append(f"{title}: relacion_grafo vacia")
        elif section == "radar_secundario":
            for field in ("que_es", "accion_sugerida"):
                if not str(content.get(field, "")).strip():
                    errors.append(f"{title}: {field} vacio")
    return errors


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("mode", choices=("extraction", "enriched"))
    parser.add_argument("path", type=Path)
    args = parser.parse_args()
    try:
        data = json.loads(args.path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        print(f"ERROR: no se puede validar {args.path}: {exc}", file=sys.stderr)
        return 2
    errors = validate(data)
    if errors:
        print(f"ERROR: {args.mode} incompleto; " + "; ".join(errors), file=sys.stderr)
        return 4
    print(f"OK: {args.mode} valido ({len(data['items'])} items)", file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
