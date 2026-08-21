#!/usr/bin/env python3
"""clean_cjk.py — detecta caracteres CJK leak en archivos de la skill.

Pitfall #17 heredado de parallel-repo-explore-bulletin:
write_file/patch pueden dejar glyphs CJK (感受, 扮演, 报告) en español.

Uso: clean_cjk.py <file...>
Exit code: 0 si limpio, 1 si CJK encontrado, 2 si error.
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path


def cjk_in_text(text: str) -> set[str]:
    return {ch for ch in text if 0x4E00 <= ord(ch) <= 0x9FFF}


def main() -> int:
    parser = argparse.ArgumentParser(description="Detecta CJK en archivos")
    parser.add_argument("files", type=Path, nargs="+", help="Archivos a chequear")
    args = parser.parse_args()

    any_dirty = False
    for path in args.files:
        if not path.exists():
            print(f"SKIP (no existe): {path}", file=sys.stderr)
            continue
        try:
            content = path.read_text(encoding="utf-8")
        except UnicodeDecodeError:
            print(f"SKIP (no utf-8): {path}", file=sys.stderr)
            continue

        cjk = cjk_in_text(content)
        if cjk:
            any_dirty = True
            print(f"DIRTY {path}: CJK chars found: {sorted(cjk)}", file=sys.stderr)
        else:
            print(f"OK {path}", file=sys.stderr)

    return 1 if any_dirty else 0


if __name__ == "__main__":
    sys.exit(main())
