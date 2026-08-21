#!/usr/bin/env python3
"""Sanea CJK y otros caracteres fuera de español en archivos de la sesión."""
import json
import re
import sys
from pathlib import Path

REPLACEMENTS = {
    '安心感': 'confianza',
    '安': '', '心': '', '感': '',
    '会': '', '我': '',
    '需': '', '知': '', '道': '',
}

def clean_text(text):
    for old, new in REPLACEMENTS.items():
        text = text.replace(old, new)
    # Cualquier CJK restante lo marcamos
    cjk = sorted({ch for ch in text if 0x4E00 <= ord(ch) <= 0x9FFF})
    return text, cjk

if __name__ == '__main__':
    for arg in sys.argv[1:]:
        p = Path(arg)
        if p.suffix == '.json':
            d = json.loads(p.read_text(encoding='utf-8'))
            txt = json.dumps(d, ensure_ascii=False, indent=2)
            txt, cjk = clean_text(txt)
            if cjk:
                print(f'DIRTY {p}: {cjk}')
            p.write_text(txt, encoding='utf-8')
        else:
            txt = p.read_text(encoding='utf-8')
            txt, cjk = clean_text(txt)
            if cjk:
                print(f'DIRTY {p}: {cjk}')
            else:
                print(f'OK {p}')
            p.write_text(txt, encoding='utf-8')
