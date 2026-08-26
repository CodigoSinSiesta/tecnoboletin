#!/usr/bin/env python3
"""extract_items.py (v2) -- extrae items de un .md de boletin sin LLM.

Uso: extract_items.py <path_md>
Output (stdout): JSON {"version":2, "source": "...", "items": [...], "resumen_ejecutivo": "..."}

NO toca el .md. Solo lee. Determinista: no inventa contenido, solo parsea.

Diferencia con v1: en vez de un "descripcion_raw" unico, extrae los campos
estructurados que el boletin origen ya trae por hallazgo (que_es,
por_que_importa, madurez_senales, relacion_grafo, accion_sugerida). Si el
boletin no los trae (radar secundario suele ser mas corto), quedan vacios
-- nunca se inventan.

El formato real de los boletines (~/obsidian-vault/Research/Boletines/) ha
variado con el tiempo:
  - Encabezados de hallazgo: "#### N. [titulo](url) - sub" | "#### N. `slug` - sub"
    | "### slug - sub" (sin numerar, plano, sin link)
  - URL: en el link del encabezado, o en un bullet "- URL: https://..." separado,
    o ausente (hay que inferirla del slug owner/repo)
  - Separador titulo/subtitulo: "-", "--", "—" (em dash), "–" (en dash)
  - Triples de grafo: "`src --rel--> dst`" o "`src --[rel]--> dst`", inline
    separados por " · " o en sub-bullets indentados
  - Radar secundario: bullets cortos "- **slug** (stars, push, lang, licencia)
    -- desc. Acción: **X** -- razon." (orden de negrita en "Acción" varia)

Este parser es deliberadamente tolerante: reconoce las variantes por
contenido normalizado (minúsculas, sin acentos), no por una unica regex
rígida. Se valida por conteo contra enriched.json existentes -- ver
scripts/validate_extraction.py.
"""
from __future__ import annotations

import argparse
import json
import re
import sys
import unicodedata
from pathlib import Path


def strip_accents(s: str) -> str:
    return "".join(c for c in unicodedata.normalize("NFD", s) if unicodedata.category(c) != "Mn")


_CJK_RE = re.compile(r"[\u4e00-\u9fff]+")


def strip_cjk(text: str) -> str:
    """Quita fugas aisladas de caracteres CJK que a veces trae el .md origen
    (ver hermes_client.py -- mismo problema, misma solucion, duplicada aqui
    a proposito para que extract_items.py siga siendo un parser autonomo sin
    LLM y sin dependencias cruzadas). No traduce -- solo elimina el ruido no
    en espanol; si el bloque es CJK legitimo y sustancial (p.ej. una cita
    larga), igual se recorta, que es preferible a colar texto no-espanol en
    un boletin en espanol."""
    if not text or not _CJK_RE.search(text):
        return text
    cleaned = _CJK_RE.sub("", text)
    return re.sub(r"\s+", " ", cleaned).strip(" ,.-\u2014\u2013")



def norm(s: str) -> str:
    return strip_accents(s).lower().strip()


HEADER_RE = re.compile(r"^(#{2,6})\s+(.*)$")

# Nombres de secciones top-level conocidas (para delimitar hallazgos/radar sin
# depender del nivel de encabezado -- en algunos boletines los items usan el
# mismo nivel ### que las secciones).
KNOWN_SECTIONS = [
    "resumen ejecutivo",
    "hallazgos principales",
    "radar secundario",
    "grafo actualizado",
    "ideas de contenido",
    "candidatos para exploracion",
    "candidatos para exploraci",  # variante con tilde ya stripeada distinto
]


def is_known_section(text: str) -> str | None:
    t = norm(text)
    for name in KNOWN_SECTIONS:
        if name in t:
            return name
    return None


# --- Encabezados de item (dentro del bloque "Hallazgos principales") ---
ITEM_HEAD_PATTERNS = [
    # #### N. [titulo](url) - sub
    re.compile(r"^\d+\.\s*\[(?P<title>[^\]]+)\]\((?P<url>https?://[^)]+)\)\s*[-—–:]?\s*(?P<subtitle>.*)$"),
    # #### [titulo](url) - sub  (sin numerar)
    re.compile(r"^\[(?P<title>[^\]]+)\]\((?P<url>https?://[^)]+)\)\s*[-—–:]?\s*(?P<subtitle>.*)$"),
    # #### N. `slug` - sub
    re.compile(r"^\d+\.\s*`(?P<title>[^`]+)`\s*[-—–:]?\s*(?P<subtitle>.*)$"),
    # #### `slug` - sub
    re.compile(r"^`(?P<title>[^`]+)`\s*[-—–:]?\s*(?P<subtitle>.*)$"),
    # #### N. slug - sub  (plano, sin backticks ni link). El separador exige
    # espacios a ambos lados para no cortar en un guion interno del slug
    # (ej. "esengine/DeepSeek-Reasonix" no debe partirse en "DeepSeek").
    re.compile(r"^\d+\.\s*(?P<title>\S+(?:\s+\S+)*?)\s[-—–]\s(?P<subtitle>.*)$"),
    # ### slug - sub  (plano, sin numerar -- variante mas antigua)
    re.compile(r"^(?P<title>\S+(?:\s+\S+)*?)\s[-—–]\s(?P<subtitle>.*)$"),
]


def clean_title(title: str) -> str:
    return title.strip().strip("`").strip("*").strip()


def parse_item_head(text: str) -> dict:
    for pat in ITEM_HEAD_PATTERNS:
        m = pat.match(text.strip())
        if m:
            gd = m.groupdict()
            return {
                "titulo": clean_title(gd["title"]),
                "url": gd.get("url"),
                "subtitulo": gd.get("subtitle", "").strip(),
            }
    # fallback total: usa la linea entera como titulo
    return {"titulo": clean_title(text), "url": None, "subtitulo": ""}


REPO_SLUG_RE = re.compile(r"^[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+$")


def infer_github_url(slug: str) -> str | None:
    slug = slug.strip().strip("`")
    if REPO_SLUG_RE.match(slug):
        return f"https://github.com/{slug}"
    return None


# --- Labels de campos ricos dentro de un bloque de hallazgo ---
# Tolerante a 2 variantes observadas en boletines reales:
#   1. Clasica: "- **Qué es**: ..." (negrita en el label, formato del historico 2026-08-02..2026-08-11)
#   2. Sin negrita: "- Qué es: ..." (formato nuevo a partir de 2026-08-19; alguien quito la negrita
#      y esto hizo que por_que_importa llegase vacio a la fase de critica, que rechazaba cualquier
#      reescritura por ">2.5x de un string vacio" sin avisar).
# Ademas tolera un parentetico opcional tras el label en negrita (ej.
# "**Madurez/señales** (verificado GitHub API):") y un ":" opcional.
# Los labels planos deben EMPEZAR por mayuscula para no matchear bullets
# que no son labels (ej. "- algunos casos de uso: ..."). Como salvaguarda
# adicional, classify_label() filtra por frases conocidas; un label que
# matchea esta regex pero no contiene "que es" / "por que importa" / etc.
# se ignora silenciosamente.
LABEL_LINE_RE = re.compile(
    r"^-\s+"
    r"(?:"
    r"\*\*(?P<label>[^*]+)\*\*(?:\s*\([^)]*\))?"  # **Label** opcional (...)
    r"|"
    r"(?P<label_plain>[A-ZÁÉÍÓÚÑ][^:]+?)(?=\s*:|\s*$)"  # Plain label (Mayuscula inicial, hasta : o EOL)
    r")"
    r"\s*:?\s*"
    r"(?P<rest>.*)$"
)
URL_LINE_RE = re.compile(r"^-\s*\*{0,2}URL\*{0,2}\s*:\s*(?P<url>https?://\S+)", re.IGNORECASE)
NESTED_BULLET_RE = re.compile(r"^\s{2,}-\s*(?P<rest>.*)$")
TOPLEVEL_BULLET_RE = re.compile(r"^-\s*(?P<rest>.*)$")


def classify_label(label: str) -> str | None:
    n = norm(label)
    if "que es" in n:
        return "que_es"
    if "por que importa" in n:
        return "por_que_importa"
    if "madurez" in n or "senales" in n:
        return "madurez_senales"
    if "relacion" in n and "grafo" in n:
        return "relacion_grafo"
    if "accion" in n and "sugerid" in n:
        return "accion_sugerida"
    return None


TRIPLE_RE = re.compile(
    r"`?(?P<src>[A-Za-z0-9_./:-]+)`?\s*--\[?(?P<rel>[A-Za-z_]+)\]?-->\s*`?(?P<dst>[A-Za-z0-9_./:-]+)`?"
    r"(?:\s*\((?P<note>[^)]*)\))?"
)


def extract_triples(raw: str) -> list[dict]:
    triples = []
    seen = set()
    for m in TRIPLE_RE.finditer(raw):
        src, rel, dst = m.group("src"), m.group("rel"), m.group("dst")
        key = (src, rel, dst)
        if key in seen:
            continue
        seen.add(key)
        triples.append({"src": src, "rel": rel, "dst": dst})
    return triples


def parse_hallazgo_block(head_line: str, body_lines: list[str], idx: int) -> dict:
    head = parse_item_head(head_line)
    titulo = head["titulo"]
    url = head["url"]
    url_inferida = False

    fields: dict[str, list[str]] = {
        "que_es": [],
        "por_que_importa": [],
        "madurez_senales": [],
        "relacion_grafo": [],
        "accion_sugerida": [],
    }
    if head["subtitulo"]:
        # el subtitulo del encabezado suele ser una frase descriptiva corta;
        # si no aparece un "que_es" explicito mas abajo, sirve de fallback.
        fields.setdefault("_subtitulo", []).append(head["subtitulo"])

    current: str | None = None
    for line in body_lines:
        if not line.strip():
            continue

        m_url = URL_LINE_RE.match(line)
        if m_url and not url:
            url = m_url.group("url").rstrip(".,;:)")
            current = None
            continue

        m_label = LABEL_LINE_RE.match(line)
        if m_label:
            # LABEL_LINE_RE tiene 2 alternativas: con negrita (label) o plana
            # (label_plain). Toma la que haya capturado.
            label = m_label.group("label") or m_label.group("label_plain") or ""
            label = label.strip().strip("*").strip()
            field = classify_label(label)
            if field:
                current = field
                rest = m_label.group("rest").strip()
                if rest:
                    fields[field].append(rest)
                continue
            # bullet con label desconocido (ej. "- Para CSS: ..."): no rompe
            # el parseo, simplemente no se asocia a ningun campo conocido.
            current = None
            continue

        m_nested = NESTED_BULLET_RE.match(line)
        if m_nested and current:
            fields[current].append(m_nested.group("rest").strip())
            continue

        m_top = TOPLEVEL_BULLET_RE.match(line)
        if m_top and current:
            fields[current].append(m_top.group("rest").strip())
            continue

        # linea de continuacion sin bullet (wrap de parrafo)
        if current:
            fields[current].append(line.strip())

    que_es = strip_cjk(" ".join(fields["que_es"]).strip() or " ".join(fields.get("_subtitulo", [])).strip())
    por_que_importa = strip_cjk(" ".join(fields["por_que_importa"]).strip())
    madurez_senales = strip_cjk(" \u00b7 ".join(x for x in fields["madurez_senales"] if x).strip())
    accion_sugerida = strip_cjk(" ".join(fields["accion_sugerida"]).strip())
    relacion_raw = " · ".join(fields["relacion_grafo"])
    relacion_grafo = extract_triples(relacion_raw)

    if not url:
        inferred = infer_github_url(titulo)
        if inferred:
            url = inferred
            url_inferida = True

    item = {
        "idx": idx,
        "titulo": titulo,
        "url": url or "",
        "url_inferida": url_inferida,
        "seccion": "hallazgo_principal",
        "contenido": {
            "que_es": que_es,
            "por_que_importa": por_que_importa,
            "madurez_senales": madurez_senales,
            "accion_sugerida": accion_sugerida,
            "descripcion_raw": "" if (que_es or por_que_importa) else " ".join(fields.get("_subtitulo", [])).strip(),
        },
        "relacion_grafo": relacion_grafo,
    }
    return item


RADAR_LINE_RE = re.compile(
    r"^-\s*\*\*\s*(?:\`(?P<slug1>[^\`]+)\`|\[(?P<slug2>[^\]]+)\])\s*(?:\((?P<paren>[^)]*)\))?\s*\*\*\s*[-—–:]?\s*(?P<rest>.*)$"
)
ACCION_INLINE_RE = re.compile(
    r"(?:\*\*)?Acci[oó]n\s*:?\s*(?:\*\*)?\s*(?P<accion>[^*.—–]+)(?:\*\*)?\s*[—–-]?\s*(?P<razon>.*)$",
    re.IGNORECASE,
)


def parse_radar_line(line: str, idx: int) -> dict | None:
    m = RADAR_LINE_RE.match(line.strip())
    if not m:
        return None
    slug = (m.group("slug1") or m.group("slug2") or "").strip().strip("`")
    paren = (m.group("paren") or "").strip()
    rest = (m.group("rest") or "").strip()

    accion = ""
    que_es = rest
    m_accion = ACCION_INLINE_RE.search(rest)
    if m_accion:
        accion_word = m_accion.group("accion").strip().strip("*").strip()
        razon = m_accion.group("razon").strip().strip("*").strip(" .-—–")
        accion = (accion_word + (f" — {razon}" if razon else "")).strip()
        que_es = rest[: m_accion.start()].strip().rstrip(".").strip()

    que_es = strip_cjk(que_es)
    accion = strip_cjk(accion)
    url = None
    url_inferida = False
    inferred = infer_github_url(slug)
    if inferred:
        url = inferred
        url_inferida = True

    return {
        "idx": idx,
        "titulo": slug,
        "url": url or "",
        "url_inferida": url_inferida,
        "seccion": "radar_secundario",
        "contenido": {
            "que_es": que_es,
            "por_que_importa": "",
            "madurez_senales": paren,
            "accion_sugerida": accion,
            "descripcion_raw": "",
        },
        "relacion_grafo": [],
    }


def find_section_slice(lines: list[str], section_key: str) -> tuple[int, int] | None:
    """Devuelve (start, end) exclusivo de indices de linea para el contenido
    (sin la propia linea de encabezado) de la seccion cuyo nombre normalizado
    contiene `section_key`. None si no se encuentra."""
    headers = []
    for i, line in enumerate(lines):
        m = HEADER_RE.match(line)
        if m:
            headers.append((i, m.group(2)))

    start = None
    for i, text in headers:
        if section_key in norm(text):
            start = i
            break
    if start is None:
        return None

    end = len(lines)
    for i, text in headers:
        if i <= start:
            continue
        known = is_known_section(text)
        if known is not None:
            end = i
            break
    return (start + 1, end)


def parse(path: Path) -> dict:
    text = path.read_text(encoding="utf-8")
    lines = text.splitlines()

    # --- Resumen ejecutivo ---
    resumen_lines: list[str] = []
    rs = find_section_slice(lines, "resumen ejecutivo")
    if rs:
        for line in lines[rs[0]:rs[1]]:
            if line.strip():
                resumen_lines.append(line.strip())

    items: list[dict] = []
    seen_urls: set[str] = set()

    # --- Hallazgos principales ---
    hs = find_section_slice(lines, "hallazgos principales")
    if hs:
        block_lines = lines[hs[0]:hs[1]]
        # localizar encabezados de item dentro del bloque
        head_idxs = [i for i, line in enumerate(block_lines) if HEADER_RE.match(line)]
        boundaries = head_idxs + [len(block_lines)]
        for j, hidx in enumerate(head_idxs):
            head_text = HEADER_RE.match(block_lines[hidx]).group(2)
            body = block_lines[hidx + 1: boundaries[j + 1]]
            item = parse_hallazgo_block(head_text, body, len(items))
            if item["url"] and item["url"] in seen_urls:
                continue
            if item["url"]:
                seen_urls.add(item["url"])
            items.append(item)

    # --- Radar secundario ---
    rad = find_section_slice(lines, "radar secundario")
    if rad:
        for line in lines[rad[0]:rad[1]]:
            if not line.strip().startswith("-"):
                continue
            if re.match(r"^\s{2,}-", line):
                continue  # sub-bullet anidado, no un item nuevo
            parsed = parse_radar_line(line, len(items))
            if not parsed:
                continue
            if parsed["url"] and parsed["url"] in seen_urls:
                continue
            if parsed["url"]:
                seen_urls.add(parsed["url"])
            items.append(parsed)

    return {
        "version": 2,
        "source": path.name,
        "items": items,
        "resumen_ejecutivo": "\n".join(strip_cjk(l) for l in resumen_lines),
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Extrae items (v2, campos ricos) de un boletin .md")
    parser.add_argument("path", type=Path, help="Ruta al .md")
    args = parser.parse_args()

    if not args.path.exists():
        print(f"ERROR: archivo no encontrado: {args.path}", file=sys.stderr)
        return 1
    if not args.path.is_file():
        print(f"ERROR: no es un archivo: {args.path}", file=sys.stderr)
        return 1

    try:
        result = parse(args.path)
    except Exception as exc:  # defensivo: nunca romper por formato irregular
        print(f"ERROR parseando {args.path}: {exc}", file=sys.stderr)
        return 2

    json.dump(result, sys.stdout, ensure_ascii=False, indent=2)
    print()
    return 0


if __name__ == "__main__":
    sys.exit(main())
