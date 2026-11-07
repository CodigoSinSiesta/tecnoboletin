#!/usr/bin/env python3
"""validate_bulletin_md.py -- contrato del boletin de tendencias (Markdown).

Valida el `<fecha>-trending.md` que escribe el cron de las 09:10 ANTES de
que lo consuma la pipeline de enriquecimiento. Determinista, sin LLM.

Dos usos:
  1. El propio agente lo ejecuta al terminar la fase 1 y corrige el
     Markdown hasta que no haya errores (autocomprobacion del prompt).
  2. tecnoboletin-daily.sh lo ejecuta como gate 0: si hay errores, aborta
     con un mensaje que nombra la tarjeta y el campo, en vez del generico
     "url vacia" que salia de dentro de la extraccion.

Errores (exit 4) = cosas que rompen la extraccion o publican basura.
Avisos (exit 0) = calidad: vocabulario del grafo, recuentos, idioma.

Uso:
    validate_bulletin_md.py <trending.md> [--json] [--strict]
    (--strict convierte los avisos en errores)
"""
from __future__ import annotations

import argparse
import json
import re
import sys
import unicodedata
from pathlib import Path

REQUIRED_SECTIONS = [
    "resumen ejecutivo",
    "hallazgos principales",
    "radar secundario",
    "grafo actualizado",
    "ideas de contenido",
    "candidatos para exploracion profunda",
]

# Labels obligatorios por tarjeta de hallazgo, en el orden del contrato.
# Se comparan por prefijo normalizado: "Por qué importa para Código Sin
# Siesta / Alejandro" y "Madurez/señales (verificado vía API)" valen.
CARD_LABELS = [
    ("url", "url"),
    ("que es", "que_es"),
    ("por que importa", "por_que_importa"),
    ("madurez/senales", "madurez_senales"),
    ("relacion con el grafo", "relacion_grafo"),
    ("accion sugerida", "accion_sugerida"),
]

ACCIONES = {"ignorar", "vigilar", "leer", "explorar", "probar"}

# Vocabulario cerrado de relaciones del grafo. Los 10 originales del prompt
# mas los 3 que el modelo usaba de forma sistematica y tienen sentido.
RELACIONES = {
    "implements", "uses", "competes_with", "complements", "solves", "enables",
    "inspired_by", "relevant_to", "risk", "article_angle",
    "extends", "integrates", "mitigates",
}

HALLAZGOS_MIN, HALLAZGOS_MAX = 3, 8
RADAR_MAX = 8

HEADER_RE = re.compile(r"^(#{2,4})\s+(.*?)\s*$")
CARD_RE = re.compile(r"^####\s+(\d+)\.\s+(.+?)\s*$")
# "- **Qué es**: x" (actual), "**Qué es:** x" (2026-10-20/21). El valor puede
# continuar en sub-bullets (p. ej. la lista de triples del grafo).
LABEL_RE = re.compile(r"^\s*(?:-\s*)?\*\*(?P<label>[^*]+?):?\*\*:?\s*(?P<value>.*)$")
BARE_URL_RE = re.compile(r"^\s*(?:-\s*)?\*\*(https://[^*\s]+)\*\*\s*$")
# Tarjetas multi-repo: "- **https://github.com/o/r** — descripcion".
URL_BULLET_RE = re.compile(r"^\s*-\s*\*\*(https://[^*\s]+)\*\*")
TRIPLE_RE = re.compile(r"`?([A-Za-z0-9_./:@-]+)`?\s+--\[?([A-Za-z_]+)\]?-->\s+`?([A-Za-z0-9_./:@-]+)`?")
HTTPS_RE = re.compile(r"https://\S+")
ADVISORY_RE = re.compile(r"\b(GHSA(?:-[23456789cfghjmpqrvwx]{4}){3}|CVE-\d{4}-\d{4,})\b", re.I)
CJK_RE = re.compile(r"[぀-ヿ㐀-䶿一-鿿가-힯]")
# "tresOCs", "unMemory": palabra en minusculas pegada a otra en mayuscula.
GLUED_RE = re.compile(r"\b(?:un|una|unos|tres|dos|del|los|las|con|por|para|que|y|de|el|la)([A-Z][a-z]{2,}|[A-Z]{2,}s?)\b")
EN_STOPWORDS = re.compile(r"\b(the|and|which|with|author's|claim|however|this is)\b", re.I)


def norm(s: str) -> str:
    s = unicodedata.normalize("NFD", s.lower())
    s = "".join(c for c in s if unicodedata.category(c) != "Mn")
    return re.sub(r"\s+", " ", s).strip(" :*`")


def split_sections(lines: list[str]) -> dict[str, list[tuple[int, str]]]:
    """h3 -> lineas (con numero) hasta el siguiente h2/h3. Los h4 son hijos."""
    sections: dict[str, list[tuple[int, str]]] = {}
    current = None
    for n, line in enumerate(lines, 1):
        m = HEADER_RE.match(line)
        if m and len(m.group(1)) <= 3:
            current = norm(m.group(2)) if len(m.group(1)) == 3 else None
            if current is not None:
                sections.setdefault(current, [])
            continue
        if current is not None:
            sections[current].append((n, line))
    return sections


def find_section(sections: dict, wanted: str) -> list[tuple[int, str]] | None:
    for name, body in sections.items():
        if name.startswith(wanted):
            return body
    return None


def parse_cards(body: list[tuple[int, str]]) -> list[dict]:
    cards: list[dict] = []
    for n, line in body:
        m = CARD_RE.match(line)
        if m:
            cards.append({"num": int(m.group(1)), "head": m.group(2), "line": n, "fields": {}, "raw": []})
            continue
        if not cards:
            continue
        card = cards[-1]
        card["raw"].append(line)
        lm = LABEL_RE.match(line)
        key = None
        if lm and not BARE_URL_RE.match(line):
            label = norm(lm.group("label"))
            key = next((k for prefix, k in CARD_LABELS if label.startswith(prefix)), None)
        if key and key not in card["fields"]:
            card["fields"][key] = lm.group("value").strip()
            card["_open"] = key
        elif lm:
            card["_open"] = None
        elif line.strip() and card.get("_open") and line.lstrip().startswith("-"):
            card["fields"][card["_open"]] += " " + line.strip()
        elif not line.strip() or line.strip() == "---":
            pass
        else:
            card["_open"] = None
    return cards


def card_url(card: dict) -> tuple[str | None, bool]:
    """(url, rescatable): url https de la cabecera o del campo URL. Si solo
    hay un GHSA/CVE suelto, extract_items lo normaliza -> rescatable."""
    m = HTTPS_RE.search(card["head"])
    if m:
        return m.group(0).rstrip(").,;"), False
    for line in card["raw"]:
        m = BARE_URL_RE.match(line) or URL_BULLET_RE.match(line)
        if m:
            return m.group(1), False
    value = card["fields"].get("url", "")
    m = HTTPS_RE.search(value)
    if m:
        return m.group(0).rstrip(").,;*"), False
    if ADVISORY_RE.search(value):
        return None, True
    return None, False


def validate_text(text: str) -> tuple[list[str], list[str], dict]:
    errors: list[str] = []
    warnings: list[str] = []
    lines = text.splitlines()

    if not re.search(r"^##\s+Bolet[ií]n IA/dev\s+[—-]\s+\d{4}-\d{2}-\d{2}\s*$", text, re.M):
        errors.append("falta el titulo '## Boletín IA/dev — YYYY-MM-DD'")

    sections = split_sections(lines)
    for wanted in REQUIRED_SECTIONS:
        if find_section(sections, wanted) is None:
            errors.append(f"falta la seccion '### {wanted}'")

    hall = find_section(sections, "hallazgos principales") or []
    cards = parse_cards(hall)
    stats = {"hallazgos": len(cards)}
    if hall and not cards:
        errors.append("'Hallazgos principales' sin tarjetas '#### N. titulo' (formato antiguo o roto)")
    elif cards and not HALLAZGOS_MIN <= len(cards) <= HALLAZGOS_MAX:
        warnings.append(f"{len(cards)} hallazgos principales (contrato: {HALLAZGOS_MIN}-{HALLAZGOS_MAX})")

    for i, card in enumerate(cards, 1):
        tag = f"hallazgo {card['num']} (linea {card['line']}: {card['head'][:50]})"
        if card["num"] != i:
            warnings.append(f"{tag}: numeracion {card['num']}, esperado {i}")
        url, rescatable = card_url(card)
        if not url:
            if rescatable:
                warnings.append(f"{tag}: URL sin https (GHSA/CVE suelto); escribe https://github.com/advisories/GHSA-... o https://nvd.nist.gov/vuln/detail/CVE-...")
            else:
                errors.append(f"{tag}: sin URL https en la cabecera ni en '- **URL**:'")
        for _prefix, key in CARD_LABELS[1:]:
            if not card["fields"].get(key):
                errors.append(f"{tag}: falta o esta vacio '{key}'")
        accion = norm(card["fields"].get("accion_sugerida", ""))
        verbo = accion.split()[0].strip("*.,;:") if accion else ""
        if accion and verbo not in ACCIONES:
            warnings.append(f"{tag}: la accion debe empezar por {sorted(ACCIONES)} (empieza por '{verbo}')")
        rel = card["fields"].get("relacion_grafo", "")
        triples = TRIPLE_RE.findall(rel)
        if rel and not triples:
            errors.append(f"{tag}: 'Relación con el grafo' sin triples `a --rel--> b`")
        fuera = sorted({r for _, r, _ in triples if r not in RELACIONES})
        if fuera:
            warnings.append(f"{tag}: relaciones fuera del vocabulario: {fuera}")
        madurez = card["fields"].get("madurez_senales", "")
        if madurez and not re.search(r"\d", madurez) and "no verificado" not in norm(madurez):
            warnings.append(f"{tag}: madurez sin cifras ni 'no verificado'")

    radar = find_section(sections, "radar secundario") or []
    radar_items = [l for _, l in radar if re.match(r"^-\s+\S", l)]
    stats["radar"] = len(radar_items)
    if len(radar_items) > RADAR_MAX:
        warnings.append(f"radar con {len(radar_items)} items (maximo {RADAR_MAX})")
    for l in radar_items:
        if not HTTPS_RE.search(l):
            warnings.append(f"radar sin URL: {l[:70]}")
        if not re.search(r"Acci[oó]n:", l):
            warnings.append(f"radar sin 'Acción:': {l[:70]}")

    cjk = CJK_RE.findall(text)
    if cjk:
        errors.append(f"{len(cjk)} caracteres CJK en el texto (traduce o elimina)")
    glued = sorted(set(m.group(0) for m in GLUED_RE.finditer(text)))
    if glued:
        warnings.append(f"palabras pegadas: {glued[:6]}")
    en = len(EN_STOPWORDS.findall(text))
    if en >= 6:
        warnings.append(f"{en} palabras en ingles sueltas en la prosa (revisa citas y traduce)")
    stats["triples"] = len(TRIPLE_RE.findall(text))
    return errors, warnings, stats


def main() -> int:
    ap = argparse.ArgumentParser(description="Valida el contrato Markdown del boletin de tendencias")
    ap.add_argument("path", type=Path)
    ap.add_argument("--json", action="store_true")
    ap.add_argument("--strict", action="store_true", help="los avisos tambien cuentan como error")
    args = ap.parse_args()
    try:
        text = args.path.read_text(encoding="utf-8")
    except OSError as exc:
        print(f"ERROR: no se puede leer {args.path}: {exc}", file=sys.stderr)
        return 2
    errors, warnings, stats = validate_text(text)
    if args.strict:
        errors, warnings = errors + warnings, []
    if args.json:
        print(json.dumps({"ok": not errors, "errors": errors, "warnings": warnings, "stats": stats}, ensure_ascii=False, indent=2))
    else:
        for e in errors:
            print(f"ERROR: {e}")
        for w in warnings:
            print(f"AVISO: {w}")
        print(("OK" if not errors else "FALLA") + f": {args.path.name} · {stats['hallazgos']} hallazgos · {stats.get('radar', 0)} radar · {len(errors)} errores · {len(warnings)} avisos")
    return 0 if not errors else 4


if __name__ == "__main__":
    raise SystemExit(main())
