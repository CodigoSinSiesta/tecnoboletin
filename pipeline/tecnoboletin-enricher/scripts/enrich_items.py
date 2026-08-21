#!/usr/bin/env python3
"""enrich_items.py (v2) -- enriquece items extraidos (sin descartar contenido).

Uso:
    enrich_items.py <items.json de extract_items.py> --date YYYY-MM-DD \
        [--carry-metadata-from <enriched.json v1 anterior>] \
        [--llm hermes|none] [--work-dir DIR]

Reemplaza a classify_batch.py. Diferencias clave respecto al v1:

1. NO genera un `resumen_2_lineas` que sustituye el contenido del boletin.
   Los campos ricos (que_es, por_que_importa, madurez_senales,
   accion_sugerida) se CONSERVAN tal como los extrajo extract_items.py; el
   unico retoque es una limpieza mecanica ligera (tidy_text) mas, con
   --llm hermes, UNA sola llamada batcheada a `hermes -z` (Hermes Agent
   CLI, MiniMax-M3 -- ver hermes_client.py) que pule gramatica/claridad de
   TODOS los items del dia a la vez. Nunca una llamada por item: cada
   invocacion de `hermes -z` levanta un agente completo (~15-40s), asi que
   se batchea para que el runtime sea razonable (1 llamada/dia en este
   paso, otra en synthesize_article.py).

2. La `clasificacion` (tipo/idioma/autor/medio/tema_principal/
   temas_secundarios/confianza) es metadata SECUNDARIA. Si se pasa
   --carry-metadata-from con un enriched.json v1 ya existente para la misma
   fecha, se hace join por URL y se conserva esa clasificacion tal cual
   (ya es correcta, no hace falta reclasificar). Si no hay metadata previa,
   se aplica un fallback deterministico best-effort (ver
   `guess_clasificacion`) y se marca `confianza` baja para senalar que es
   heuristico -- no se pide clasificacion nueva via LLM (no aporta lo
   suficiente para justificar otra llamada batcheada).

3. `relacion_grafo` se anota con `primera_mencion` (graph_crossref.py) --
   consulta determinista, no LLM. El pulido de por_que_importa puede
   apoyarse en esa fecha si el prompt la referencia (ver
   synthesize_article.py, que es donde de verdad se explota esto).

Backend LLM: `--llm hermes` (default) invoca `hermes -z` -- Hermes Agent
CLI ya configurado en este runtime con MiniMax-M3, el mismo mecanismo que
usa con exito el cron del boletin original todos los dias (no requiere
Ollama ni el SDK de Pi Agent, que esta roto -- ver SKILL.md, "Estado del
backend LLM"). Si `hermes` no esta disponible, el script lo reporta
explicitamente por stderr (nunca asume "no hay backend" en silencio) y
degrada a --llm none (el contenido extraido/tidy se conserva sin pulido
LLM adicional -- sigue siendo valido, solo le falta esa capa).
"""
from __future__ import annotations

import argparse
import json
import re
import sys
import unicodedata
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from graph_crossref import GraphIndex  # noqa: E402
from hermes_client import call_hermes, hermes_available, parse_json_lenient, strip_cjk  # noqa: E402

ALLOWED_TIPOS = {"blog", "paper", "repo", "video", "podcast", "noticia", "docs", "otro"}

POLISH_INSTRUCTIONS = """Eres un editor de espanol tecnico. Recibes un JSON con items de un \
boletin de tendencias IA/dev. Cada item tiene "que_es" y, si aplica, \
"por_que_importa" ya escritos.

Tu trabajo: pulir gramatica, puntuacion y claridad de esos campos -- SIN \
anadir hechos, cifras, nombres o afirmaciones que no esten ya en el \
texto. No resumas ni acortes el contenido salvo redundancia obvia. Si un \
campo ya esta bien escrito, devuelvelo igual (no cambies por cambiar). Si \
un campo llega vacio ("") o no existe en el item de entrada, devuelvelo \
vacio -- no inventes contenido nuevo para rellenarlo.

No uses ninguna herramienta. Responde EXCLUSIVAMENTE con un JSON (sin \
fences de markdown, sin comentarios, termina siempre cerrando el array \
con ]) con esta forma exacta:

[{"idx": 0, "que_es": "...", "por_que_importa": "..."}, ...]

Un objeto por cada idx de entrada, en el mismo orden, sin omitir ninguno. \
Si un item de entrada no trae por_que_importa, incluye el campo igualmente \
con cadena vacia.

ITEMS:
"""


def strip_accents(s: str) -> str:
    return "".join(c for c in unicodedata.normalize("NFD", s) if unicodedata.category(c) != "Mn")


def tidy_text(s: str) -> str:
    """Limpieza mecanica ligera: NO reescribe contenido, solo normaliza
    espacios, quita envoltorios markdown sueltos y fugas de CJK (ver
    hermes_client.strip_cjk). Determinista, sin LLM."""
    if not s:
        return s
    t = s.strip()
    t = strip_cjk(t)
    t = re.sub(r"\s+", " ", t)
    if t.startswith("*") and t.count("*") % 2 == 1:
        t = t[1:].strip()
    if t.endswith("*") and t.count("*") % 2 == 1:
        t = t[:-1].strip()
    t = t.strip(" -—–")
    return t


def guess_clasificacion(item: dict) -> dict:
    """Fallback determinista sin LLM: heuristica minima, confianza baja.
    Nunca inventa autor/medio (quedan null)."""
    url = item.get("url", "")
    titulo = item.get("titulo", "")
    tipo = "repo" if "github.com" in url else "otro"
    tema = re.sub(r"[^a-z0-9]+", "-", titulo.lower()).strip("-")[:40] or "sin-tema"
    return {
        "tipo": tipo,
        "idioma": "en",
        "autor": None,
        "medio": None,
        "tema_principal": tema or "sin-tema",
        "temas_secundarios": [],
        "confianza": 0.4,
    }


def load_carry_metadata(path: Path | None) -> dict[str, dict]:
    if not path or not path.exists():
        return {}
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return {}
    out = {}
    for it in data.get("items", []):
        url = it.get("url")
        c = it.get("clasificacion")
        if url and c:
            out[url] = c
    return out


def batch_polish(items: list[dict], date: str, work_dir: Path, timeout: int) -> tuple[dict[int, dict], str]:
    """UNA llamada a hermes -z para pulir que_es/por_que_importa de TODOS
    los items del dia. Devuelve ({idx: {que_es, por_que_importa}}, motivo)
    -- dict vacio + motivo si fallo (el caller conserva el texto original,
    nunca bloquea la pipeline)."""
    payload = [
        {
            "idx": it["idx"],
            "que_es": it["contenido"]["que_es"],
            "por_que_importa": it["contenido"].get("por_que_importa", ""),
        }
        for it in items
    ]
    prompt = POLISH_INSTRUCTIONS + json.dumps(payload, ensure_ascii=False, indent=2)

    raw = call_hermes(prompt, work_dir, tag=f"{date}.polish", timeout=timeout)
    if raw is None:
        return {}, "hermes -z fallo o no disponible (ver stderr arriba)"

    parsed = parse_json_lenient(raw)
    if not isinstance(parsed, list):
        return {}, f"respuesta no parseable como lista JSON (primeros 200 chars: {raw[:200]!r})"

    result: dict[int, dict] = {}
    for entry in parsed:
        if not isinstance(entry, dict) or "idx" not in entry:
            continue
        try:
            idx = int(entry["idx"])
        except (TypeError, ValueError):
            continue
        que_es = strip_cjk(str(entry.get("que_es", "")).strip())
        por_que = strip_cjk(str(entry.get("por_que_importa", "")).strip())
        result[idx] = {"que_es": que_es, "por_que_importa": por_que}

    missing = [it["idx"] for it in items if it["idx"] not in result]
    motivo = f"{len(result)}/{len(items)} items pulidos" + (f"; faltantes: {missing}" if missing else "")
    return result, motivo


def build_item(item: dict, date: str, carry: dict[str, dict], gi: GraphIndex, polished: dict[int, dict]) -> dict:
    contenido = item.get("contenido", {})
    que_es = tidy_text(contenido.get("que_es", ""))
    por_que_importa = tidy_text(contenido.get("por_que_importa", ""))
    madurez = tidy_text(contenido.get("madurez_senales", ""))
    accion = tidy_text(contenido.get("accion_sugerida", ""))
    descripcion_raw = tidy_text(contenido.get("descripcion_raw", ""))

    p = polished.get(item["idx"])
    if p:
        # nunca aceptar un pulido vacio quitando contenido que si existia,
        # ni uno sospechosamente mas largo (senal de invencion)
        if p["que_es"] and len(p["que_es"]) <= len(que_es) * 1.6 + 20:
            que_es = tidy_text(p["que_es"])
        if p["por_que_importa"] and len(p["por_que_importa"]) <= len(por_que_importa) * 1.6 + 20:
            por_que_importa = tidy_text(p["por_que_importa"])

    url = item.get("url", "")
    clasificacion = carry.get(url)
    if not clasificacion:
        clasificacion = guess_clasificacion(item)
    else:
        clasificacion = dict(clasificacion)
        clasificacion.pop("resumen_2_lineas", None)
        for req, default in (("tipo", "otro"), ("idioma", "en"), ("tema_principal", "sin-tema"), ("confianza", 0.5)):
            clasificacion.setdefault(req, default)
        if clasificacion["tipo"] not in ALLOWED_TIPOS:
            clasificacion["tipo"] = "otro"

    triples = gi.annotate(item.get("relacion_grafo", []), date)

    return {
        "idx": item["idx"],
        "titulo": item["titulo"],
        "url": url,
        "url_inferida": item.get("url_inferida", False),
        "seccion": item["seccion"],
        "contenido": {
            "que_es": que_es,
            "por_que_importa": por_que_importa,
            "madurez_senales": madurez,
            "accion_sugerida": accion,
            "descripcion_raw": descripcion_raw,
        },
        "relacion_grafo": triples,
        "clasificacion": clasificacion,
    }


def main() -> int:
    ap = argparse.ArgumentParser(description="Enriquece items extraidos (v2, conserva contenido)")
    ap.add_argument("path", type=Path, help="JSON de extract_items.py")
    ap.add_argument("--date", type=str, required=True)
    ap.add_argument("--carry-metadata-from", type=Path, default=None,
                     help="enriched.json v1 previo para conservar su clasificacion por URL")
    ap.add_argument("--llm", choices=["hermes", "none"], default="hermes")
    ap.add_argument("--work-dir", type=Path, default=Path("~/.hermes/data/tecnoboletin/_work").expanduser())
    ap.add_argument("--timeout", type=int, default=240)
    ap.add_argument("--out", type=Path, default=None, help="si se omite, imprime a stdout")
    args = ap.parse_args()

    if not args.path.exists():
        print(f"ERROR: no encontrado {args.path}", file=sys.stderr)
        return 1

    raw = json.loads(args.path.read_text(encoding="utf-8"))
    items = raw.get("items", [])

    llm = args.llm
    llm_notes = ""
    if llm == "hermes":
        ok, reason = hermes_available()
        if not ok:
            print(f"AVISO: --llm hermes pedido pero no disponible ({reason}) -- degradando a --llm none. "
                  f"Esto se reporta explicitamente, no se asume en silencio.", file=sys.stderr)
            llm = "none"
            llm_notes = f"hermes no disponible: {reason}"

    carry = load_carry_metadata(args.carry_metadata_from)
    gi = GraphIndex.load()

    polished: dict[int, dict] = {}
    if llm == "hermes" and items:
        print(f"Pulido batcheado via hermes -z ({len(items)} items en 1 llamada)...", file=sys.stderr)
        polished, motivo = batch_polish(items, args.date, args.work_dir, args.timeout)
        llm_notes = motivo
        print(f"  {motivo}", file=sys.stderr)
        if not polished:
            print("AVISO: el pulido batcheado no devolvio nada usable -- se conserva el texto extraido sin pulir.",
                  file=sys.stderr)

    enriched_items = [build_item(it, args.date, carry, gi, polished) for it in items]
    for it in items:
        print(f"  [{it['idx']}] {it['seccion']} · {it['titulo']}", file=sys.stderr)

    output = {
        "version": 2,
        "date": args.date,
        "boletin_origen": raw.get("source", ""),
        "resumen_ejecutivo": raw.get("resumen_ejecutivo", ""),
        "items": enriched_items,
        "stats": {
            "items_total": len(items),
            "items_hallazgo_principal": sum(1 for i in items if i["seccion"] == "hallazgo_principal"),
            "items_radar_secundario": sum(1 for i in items if i["seccion"] == "radar_secundario"),
            "llm_backend": llm,
            "llm_polish_notes": llm_notes,
            "metadata_carried_forward": bool(carry),
        },
    }

    text = json.dumps(output, ensure_ascii=False, indent=2)
    if args.out:
        args.out.parent.mkdir(parents=True, exist_ok=True)
        args.out.write_text(text, encoding="utf-8")
        print(f"Escrito: {args.out}", file=sys.stderr)
    else:
        print(text)
    return 0


if __name__ == "__main__":
    sys.exit(main())
