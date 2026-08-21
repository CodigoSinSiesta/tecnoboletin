#!/usr/bin/env python3
"""synthesize_article.py -- pasa el borrador del dia por 3 lentes de
critica editorial y reescribe por_que_importa antes de publicar.

Reemplaza a review.py. Diseno acordado con Alejandro:

- Las 3 lentes (rigor_tecnico, claridad_accesibilidad, relevancia_editorial)
  son CRITERIOS DE REVISION, no personas. Ver
  references/criterios-revision.md y templates/lente-sistema.md.
- Se aplican sobre el borrador del dia (todos los hallazgos + su relacion
  con el grafo, con `primera_mencion` cuando el cruce determinista la
  encontro) en UNA SOLA llamada a `hermes -z` -- el modelo aplica
  internamente los 3 criterios y devuelve directamente el
  por_que_importa reescrito, ya mejorado. No se piden ni se guardan las 3
  criticas por separado: el objetivo de "no persistir reviews.json" se
  cumple por construccion (nunca se le pide al modelo un texto de critica
  aparte, solo el resultado ya incorporado).
- Backend: `hermes -z` (Hermes Agent CLI, MiniMax-M3 -- ver
  hermes_client.py). Ninguna llamada por item: 1 llamada batcheada por
  dia sobre todos los items de seccion=hallazgo_principal (los de radar
  secundario no pasan por este paso, su por_que_importa esta vacio por
  diseno -- ver extract_items.py).

Uso:
    synthesize_article.py --date YYYY-MM-DD --enriched <enriched.json> \
        [--llm hermes|none] [--work-dir DIR] --out <enriched.json final>
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from hermes_client import call_hermes, hermes_available, parse_json_lenient, strip_cjk  # noqa: E402

LENTES = ["rigor_tecnico", "claridad_accesibilidad", "relevancia_editorial"]

CRITIQUE_INSTRUCTIONS = """Eres el editor final de un boletin tecnico en espanol (Codigo Sin \
Siesta). Recibes un JSON con hallazgos de un boletin: idx, que_es, \
por_que_importa, madurez_senales, y relacion_grafo (triples con \
`primera_mencion` = fecha de un boletin anterior donde ya se cubrio ese \
nodo/concepto, si existe alguna).

Aplica INTERNAMENTE estos 3 criterios a cada item (no expliques el \
proceso ni los critiques por separado, solo aplica el resultado \
reescribiendo por_que_importa):

1. RIGOR TECNICO: claims sin sustento, clasificacion incoherente, falta \
de contexto tecnico necesario para entender por que importa.
2. CLARIDAD/ACCESIBILIDAD: jerga sin glosar, frases que solo se entienden \
haciendo click al link, redaccion criptica.
3. RELEVANCIA EDITORIAL: por que le importa esto a un lector de Codigo \
Sin Siesta de forma CONCRETA (no generica), y si la relacion con el \
grafo/boletines previos esta bien explicitada. Si algun triple de \
relacion_grafo trae `primera_mencion`, la reescritura de por_que_importa \
DEBE mencionar esa fecha concreta de forma natural (ej. "ya cubrimos esto \
el 2026-07-16 con X"), en vez de una referencia vaga tipo "el boletin de \
ayer".

Reescribe por_que_importa de cada item incorporando mejoras reales segun \
esos 3 criterios -- SIN inventar hechos, cifras o citas que no esten ya \
en el item (que_es, madurez_senales o el propio por_que_importa \
original). Si te falta un dato para cumplir un criterio, sé honesto \
sobre la limitacion en vez de inventarlo.

No uses ninguna herramienta. Responde EXCLUSIVAMENTE con un JSON (sin \
fences de markdown, sin comentarios, termina siempre cerrando el array \
con ]) con esta forma exacta:

[{"idx": 0, "por_que_importa": "..."}, ...]

Un objeto por cada idx de entrada, mismo orden, ninguno omitido.

ITEMS:
"""


def build_payload(items: list[dict]) -> list[dict]:
    payload = []
    for it in items:
        if it["seccion"] != "hallazgo_principal":
            continue
        payload.append({
            "idx": it["idx"],
            "que_es": it["contenido"]["que_es"],
            "por_que_importa": it["contenido"]["por_que_importa"],
            "madurez_senales": it["contenido"]["madurez_senales"][:300],
            "relacion_grafo": it.get("relacion_grafo", []),
        })
    return payload


def run_critique_and_rewrite(items: list[dict], date: str, work_dir: Path, timeout: int) -> tuple[dict[int, str], str]:
    payload = build_payload(items)
    if not payload:
        return {}, "sin items hallazgo_principal, nada que criticar"

    prompt = CRITIQUE_INSTRUCTIONS + json.dumps(payload, ensure_ascii=False, indent=2)
    raw = call_hermes(prompt, work_dir, tag=f"{date}.critique", timeout=timeout)
    if raw is None:
        return {}, "hermes -z fallo o no disponible (ver stderr arriba)"

    parsed = parse_json_lenient(raw)
    if not isinstance(parsed, list):
        return {}, f"respuesta no parseable como lista JSON (primeros 200 chars: {raw[:200]!r})"

    orig_by_idx = {p["idx"]: p["por_que_importa"] for p in payload}
    result: dict[int, str] = {}
    rejected = []
    for entry in parsed:
        if not isinstance(entry, dict) or "idx" not in entry:
            continue
        try:
            idx = int(entry["idx"])
        except (TypeError, ValueError):
            continue
        text = strip_cjk(str(entry.get("por_que_importa", "")).strip())
        original = orig_by_idx.get(idx, "")
        if not text:
            continue
        # tope generoso (la reescritura elabora de verdad -- en pruebas
        # reales el ratio fue 1.5x-2x) pero con techo absoluto para
        # frenar generacion desbocada / invencion
        if len(text) > max(len(original) * 2.5, len(original) + 400) or len(text) > 1800:
            rejected.append(idx)
            continue
        result[idx] = text

    missing = [p["idx"] for p in payload if p["idx"] not in result]
    motivo = f"{len(result)}/{len(payload)} items reescritos"
    if rejected:
        motivo += f"; rechazados por longitud sospechosa: {rejected}"
    if missing:
        motivo += f"; faltantes en respuesta: {missing}"
    return result, motivo


def main() -> int:
    ap = argparse.ArgumentParser(description="Critica (3 lentes) + reescritura de por_que_importa via hermes -z")
    ap.add_argument("--date", type=str, required=True)
    ap.add_argument("--enriched", type=Path, required=True)
    ap.add_argument("--llm", choices=["hermes", "none"], default="hermes")
    ap.add_argument("--work-dir", type=Path, default=Path("~/.hermes/data/tecnoboletin/_work").expanduser())
    ap.add_argument("--timeout", type=int, default=240)
    ap.add_argument("--out", type=Path, required=True)
    args = ap.parse_args()

    if not args.enriched.exists():
        print(f"ERROR: no encontrado {args.enriched}", file=sys.stderr)
        return 1

    enriched = json.loads(args.enriched.read_text(encoding="utf-8"))
    items = enriched.get("items", [])

    llm = args.llm
    notes = ""
    if llm == "hermes":
        ok, reason = hermes_available()
        if not ok:
            print(f"AVISO: --llm hermes pedido pero no disponible ({reason}) -- synthesize_article corre en "
                  f"modo passthrough (sin critica de 3 lentes). Reportado explicitamente, no asumido en silencio.",
                  file=sys.stderr)
            llm = "none"
            notes = f"hermes no disponible: {reason}"

    applied = False
    if llm == "hermes":
        print(f"Critica + reescritura via hermes -z (1 llamada batcheada)...", file=sys.stderr)
        rewritten, motivo = run_critique_and_rewrite(items, args.date, args.work_dir, args.timeout)
        notes = motivo
        print(f"  {motivo}", file=sys.stderr)
        if rewritten:
            for it in items:
                new_text = rewritten.get(it["idx"])
                if new_text:
                    it["contenido"]["por_que_importa"] = new_text
            applied = True
        else:
            print("AVISO: la critica+reescritura no devolvio nada usable; se conserva el borrador tal cual.",
                  file=sys.stderr)

    enriched.setdefault("stats", {})["critica_lentes_aplicada"] = applied
    enriched["stats"]["critica_notes"] = notes
    enriched["stats"]["lentes"] = LENTES

    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(enriched, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"Escrito: {args.out} (critica_lentes_aplicada={applied})", file=sys.stderr)
    return 0


if __name__ == "__main__":
    sys.exit(main())
