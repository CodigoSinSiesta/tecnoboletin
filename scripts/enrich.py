#!/usr/bin/env python3
"""
enrich.py — ENRIQUECE el último boletín entregado.
FASE 2: este script se activa 1h después del boletín de Telegram.

Lee apps/web/src/content/boletines/<último>.md, extrae items,
llama a Ollama con DeepSeek-V4-Pro, genera <último>.enriched.json.

No modifica el .md. Solo escribe el .enriched.json adyacente.

Uso:
    python3 scripts/enrich.py [--latest | --boletin YYYY-MM-DD]
"""
import argparse
import sys


def main() -> int:
    parser = argparse.ArgumentParser(description="Enriquece boletines (fase 2).")
    group = parser.add_mutually_exclusive_group()
    group.add_argument("--latest", action="store_true", help="Enriquecer el boletín más reciente.")
    group.add_argument("--boletin", type=str, help="Enriquecer un boletín específico (YYYY-MM-DD).")
    args = parser.parse_args()

    print("enrich.py: pendiente fase 2", file=sys.stdout)
    return 0


if __name__ == "__main__":
    sys.exit(main())
