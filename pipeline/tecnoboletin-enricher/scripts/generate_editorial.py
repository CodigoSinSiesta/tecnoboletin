#!/usr/bin/env python3
"""generate_editorial.py -- genera/actualiza editorial.json de forma repetible.

Dos modos:

1. --carry-forward <editorial.json existente>
   El contenido editorial ya escrito para esta fecha es bueno (fue revisado
   y aprobado) -- se conserva tal cual, SOLO se ajusta el schema:
   `perfiles_involucrados` (referencia a Carlos/Dani/Maria, ya eliminados
   del resto de la skill) se reemplaza por `lentes_aplicadas` con los 3
   criterios de revision editorial reales (rigor_tecnico,
   claridad_accesibilidad, relevancia_editorial). Tambien repara mojibake
   UTF-8 si aparece.

2. Generacion nueva (sin --carry-forward, requiere --enriched): sintetiza
   posicionamiento / convergencia_stack_css / cruzado_grafo /
   tendencias_5_boletines / alertas / acciones_concretas a partir de los
   hallazgos_principales del enriched.json del dia (con `relacion_grafo` +
   `primera_mencion` ya anotados por graph_crossref.py) y, si existen, los
   editorial.json de los 1-2 dias previos (solo para continuidad de
   'tendencias' -- no se copian, son contexto). Backend: `hermes -z`
   (ver hermes_client.py), 1 llamada batcheada en el caso normal, 2 si el
   validador post-LLM rechaza la primera. Si no hay backend disponible,
   sale con error explicito en vez de inventar contenido editorial.

Validacion del titular (post-LLM):
   El prompt pide un `titular` de 35-85 chars escrito COMO titular: una
   sola idea, sin punto final, sin muletilla y sin enumeraciones. Se
   valida igual que el posicionamiento (1 reintento y, si vuelve a
   fallar, se deriva de la primera oracion util del posicionamiento
   cortando por frontera natural). Antes de que existiera este campo, la
   web fabricaba el titular a partir del parrafo y salian titulares de
   300+ chars o cortados a media frase.

Validacion del posicionamiento (post-LLM):
   El prompt pide 80-350 chars por parrafo y arrancar directo con la tesis
   (sin meta-comentario tipo "El boletin de hoy X"). Tras la llamada a
   hermes -z, se valida posicion + longitud. Si falla, 1 reintento con un
   patch prompt que dice que fallo y pide reescribir. Si el reintento
   tambien falla, se aplica un fallback honesto: quitar la muletilla del
   prefijo y truncar al cap defensivo. Asi NUNCA se persiste un
   posicionamiento > 900 chars ni uno que arranque por muletilla, sin
   depender del LLM.

Uso:
    generate_editorial.py --date YYYY-MM-DD --carry-forward <editorial.json> --out <editorial.json>
    generate_editorial.py --date YYYY-MM-DD --enriched <enriched.json> --repo-data-dir <dir> \
        [--llm hermes|none] [--work-dir DIR] --out <editorial.json>
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from hermes_client import call_hermes, hermes_available, parse_json_lenient, strip_cjk  # noqa: E402

LENTES = ["rigor_tecnico", "claridad_accesibilidad", "relevancia_editorial"]

# Mapa de reparacion para el mojibake UTF-8 detectado en los editorial.json
# originales (texto que se guardo como si fuera Latin-1/CP1252 cuando en
# realidad era UTF-8 -- patron "Mojibake" clasico). Se aplica solo a las
# secuencias de bytes danadas conocidas, no es un cambio de contenido.
MOJIBAKE_FIXES = {
    "├¡": "í",
    "├³": "ó",
    "├®": "é",
    "├º": "ñ",
    "├▒": "ñ",
    "├│": "ó",
    "an~ar": "añar",
    "acompan~ar": "acompañar",
}

EDITORIAL_INSTRUCTIONS = """Eres el editor de sintesis de un boletin tecnico en espanol \
(Codigo Sin Siesta, tono: calidad sobre velocidad, criterio sobre hype, cero marketing). \
Recibes el resumen ejecutivo y los hallazgos principales de HOY (con su relacion con el \
grafo de conocimiento -- `primera_mencion` es la fecha de un boletin anterior donde ya se \
cubrio ese nodo/concepto, si existe alguna), y opcionalmente un resumen breve de la sintesis \
editorial de dias previos recientes, solo como contexto de continuidad.

RESTRICCIONES DUREAS DE LONGITUD (no son sugerencias, son limites):

- TODOS los parrafos (posicionamiento, convergencia_stack_css, cruzado_grafo, \
tendencias_5_boletines) deben tener entre 80 y 350 chars. Por debajo de 80 es vacio, por \
encima de 350 es vaciado. Si la tesis pide mas, dividela en 2-3 frases cortas, no en una sola \
oracion larga.

- Cada parrafo arranca DIRECTO con la idea. NUNCA arranques con meta-comentario sobre el \
boletin en si. Frases prohibidas al inicio (y todas sus variantes): \
'El boletin de hoy X', 'El boletin del YYYY-MM-DD Y', 'Hoy el boletin', 'Hoy, el boletin', \
'Este boletin X', 'Hoy X', 'Hoy, X'. La primera oracion tiene que ser la tesis concreta.

- No enumeres los hallazgos uno a uno. El posicionamiento NO es un resumen por item, es la \
lectura editorial del dia (que los ata, que los separa, cual es el hilo).

- No uses conectores de relleno entre frases: 'en este sentido', 'a este respecto', 'cabe \
senalar que', 'vale la pena mencionar'. Si una frase no aporta tesis, cortala.

Escribe una sintesis editorial de HOY con exactamente estos 7 campos (JSON, un solo objeto, \
nada de markdown fences):

{
  "titular": "EL TITULAR DEL DIA (35-85 chars). Es un TITULAR, no un parrafo ni la primera \
frase del posicionamiento: una sola idea, la tesis del dia, en la menor cantidad de palabras \
posible. Reglas duras: (a) sin punto final; (b) NUNCA empieza por meta-comentario sobre el \
boletin ('El boletin de hoy', 'Hoy', 'Este boletin', 'Los seis hallazgos', 'La lectura \
editorial', 'Tres ejes', 'Hay un hilo conductor'); (c) NO enumeres ('(1)... (2)...', 'tres \
movimientos', 'a) ... b) ...') -- si necesitas enumerar es que no es un titular; (d) sin dos \
puntos partiendo la frase en dos mitades; (e) concreto: nombra el actor o la pieza real \
cuando la haya. Ejemplos buenos: 'Anthropic publica su primer harness de seguridad como \
open source', 'La memoria persistente de los agentes entra al mainstream'. Ejemplos malos: \
'El boletin de hoy gira en torno a los agentes' (muletilla), 'Tres ejes principales: (1) \
memoria...' (enumeracion), 'La capa de agentes sale del taller y entra a produccion por tres \
puertas simultaneas que conviene mirar con calma' (parrafo).",
  "posicionamiento": "1 parrafo (80-350 chars): que hace especial al boletin de hoy en su \
conjunto, cual es el hilo conductor entre los hallazgos (si lo hay). Arranca con la tesis, no \
con meta-comentario. No es un resumen de cada item, es la lectura editorial del dia.",
  "convergencia_stack_css": "1 parrafo (80-350 chars, o vacio '' si de verdad no aplica): que \
hallazgos de hoy conectan con el stack local-first / lineas editoriales ya conocidas de Codigo \
Sin Siesta. No inventes piezas del stack que no esten mencionadas en los propios hallazgos de \
hoy o en el contexto de continuidad recibido.",
  "cruzado_grafo": "1 parrafo (80-350 chars): que nodos/relaciones del grafo se refuerzan o \
aparecen por primera vez hoy, usando SOLO las `primera_mencion` reales que vienen en los datos \
-- si un item no trae primera_mencion, no le inventes una fecha ni una mencion previa.",
  "tendencias_5_boletines": "1 parrafo (80-350 chars): como encaja el boletin de hoy con el \
contexto de continuidad recibido (si no hay contexto de dias previos, dilo explicitamente en \
vez de inventar una tendencia sin base).",
  "alertas": ["lista de 0-6 strings cortos: riesgos/matices honestos sobre hallazgos de hoy \
(licencias problematicas, claims sin verificar, hype desproporcionado a la traccion real) -- \
solo si de verdad los hay, no rellenes por rellenar"],
  "acciones_concretas": [{"tipo": "explora|vigilar|comparte-hallazgo-con-CSS", "item_idx": N, \
"razon": "1-2 frases"}]
}

item_idx en acciones_concretas DEBE ser uno de los idx reales que recibiste en los hallazgos \
de hoy -- nunca un numero inventado. Maximo 5 acciones_concretas. No inventes metricas, \
fechas ni conexiones que no esten en los datos recibidos. Si un dia tiene poco material para \
alguno de estos campos, un parrafo corto y honesto ("hoy no hay una convergencia clara con el \
stack") es preferible a rellenar con generalidades.

DATOS DE HOY:
"""


# Caps duros para los 4 parrafos. El prompt pide 80-350 (rango util), el
# cap defensivo externo (900) deja margen para respuestas que el LLM nunca
# recorta del todo. Si llega mas largo, se trunca -- la idea es NO persistir
# posicionamiento > 900 chars jamas, y forzar al LLM a recalibrar en el
# siguiente intento si esto ocurre.
POSICIONAMIENTO_MAX = 900
CONVERGENCIA_MAX = 900
CRUZADO_MAX = 900
TENDENCIAS_MAX = 900

# Rangos del validador post-LLM. Si el LLM se queda corto o se pasa, se
# considera respuesta inutil y se reintenta con un patch prompt.
POS_MIN_OK = 80
POS_MAX_OK = 600  # mas estricto que el cap defensivo: deja margen

# El titular es el unico campo con cap duro real: si no cabe en una linea
# de h1 deja de ser titular. El maximo se valida contra 110 (el prompt
# pide 85) para no rechazar por 3 chars un titular por lo demas bueno.
TITULAR_MIN_OK = 25
TITULAR_MAX_OK = 110
TITULAR_MAX = 140  # cap defensivo antes de persistir


# Patrones de muletilla que prohibe el prompt. Se validan aqui, despues de
# la respuesta, para detectar casos en los que el LLM ignoraba la instruccion.
_FILLER_PREFIXES = re.compile(
    r"^\s*(el[ \u00A0]+bolet[íi]n[ \u00A0]+(de|del)\b|"
    r"este[ \u00A0]+bolet[íi]n\b|"
    r"hoy[ \u00A0]+,?\s*el[ \u00A0]+bolet[íi]n\b|"
    r"hoy[ \u00A0]+,?\s*el\b|"
    r"hoy[ \u00A0]+,\s+|"
    r"hoy\b)",
    re.IGNORECASE,
)


def _starts_with_filler(t: str) -> bool:
    return bool(_FILLER_PREFIXES.match(t or ""))


# Marcas de que el "titular" es en realidad un parrafo o una lista.
_TITULAR_ENUMERA = re.compile(
    r"(\(\s*[1-9a-c]\s*\)|\b(?:tres|cuatro|cinco|seis|siete)\b[ \u00A0]+"
    r"(?:ejes|movimientos|hallazgos|piezas|bloques|frentes)\b|;)",
    re.IGNORECASE,
)


def _validate_titular(t: str) -> str | None:
    """Devuelve None si OK, o un string describiendo el problema."""
    t = (t or "").strip()
    if not t:
        return "vacio"
    if len(t) < TITULAR_MIN_OK:
        return f"demasiado corto ({len(t)} chars < {TITULAR_MIN_OK})"
    if len(t) > TITULAR_MAX_OK:
        return f"es un parrafo, no un titular ({len(t)} chars > {TITULAR_MAX_OK})"
    if _starts_with_filler(t):
        return "arranca con muletilla (El boletin de hoy / Hoy / ...)"
    if _TITULAR_ENUMERA.search(t):
        return "enumera o encadena clausulas; un titular es una sola idea"
    if t.endswith("."):
        return "termina en punto (un titular no lleva punto final)"
    return None


def _titular_desde_posicionamiento(pos: str) -> str:
    """Fallback sin LLM: primera oracion util del posicionamiento, cortada
    por frontera natural. Es la misma logica que la web aplicaba antes de
    que existiera este campo, y solo se usa si el LLM falla dos veces."""
    t = _strip_filler_prefix(pos or "").strip()
    if not t:
        return ""
    corte = re.search(r"(?<=[.!?])\s+(?=[A-ZÁÉÍÓÚÑ0-9])", t)
    if corte:
        t = t[: corte.start()]
    t = t.strip().rstrip(".")
    if len(t) > TITULAR_MAX_OK:
        # La ventana termina en TITULAR_MAX_OK para GARANTIZAR que el
        # resultado cabe: buscar mas alla devolvia cortes de 120+ chars
        # que el propio validador habria rechazado.
        mejor = -1
        for sep in (":", "—", ";", ", "):
            idx = t.rfind(sep, 0, TITULAR_MAX_OK)
            mejor = max(mejor, idx)
        if mejor >= 30:
            t = t[:mejor].strip().rstrip(",;:")
    # Muletillas de tesis que solo se detectan una vez aislada la frase.
    t = re.sub(r"^(?:hay[ ]+un[ ]+hilo[ ]+conductor[^:]*:|los[ ]+\w+[ ]+hallazgos[^:]*:|la[ ]+lectura[ ]+editorial[^:]*:)\s*", "", t, flags=re.IGNORECASE).strip()
    if t:
        t = t[0].upper() + t[1:]
    return t[:TITULAR_MAX]


def _validate_posicionamiento(t: str) -> str | None:
    """Devuelve None si OK, o un string describiendo el problema."""
    t = (t or "").strip()
    if not t:
        return "vacio"
    if len(t) < POS_MIN_OK:
        return f"demasiado corto ({len(t)} chars < {POS_MIN_OK})"
    if len(t) > POS_MAX_OK:
        return f"demasiado largo ({len(t)} chars > {POS_MAX_OK})"
    if _starts_with_filler(t):
        return "arranca con muletilla (El boletin de hoy / Hoy / ...)"
    return None


def _strip_filler_prefix(t: str) -> str:
    """Quita el prefijo de muletilla si esta, dejando la primera frase con
    tesis. Fallback: devuelve el texto tal cual."""
    m = _FILLER_PREFIXES.match(t)
    if not m:
        return t
    rest = t[m.end():].lstrip(" \u00A0,.;:")
    # Busca el primer final de oracion (., !, ?) seguido de espacio + mayuscula.
    sm = re.search(r"[.!?]\s+(?=[A-ZÁÉÍÓÚÑ0-9])", rest)
    if sm:
        return rest[sm.end():].lstrip()
    return rest


def fix_mojibake(text: str) -> str:
    if not isinstance(text, str):
        return text
    for bad, good in MOJIBAKE_FIXES.items():
        text = text.replace(bad, good)
    return text


def deep_fix(obj):
    if isinstance(obj, str):
        return fix_mojibake(obj)
    if isinstance(obj, list):
        return [deep_fix(x) for x in obj]
    if isinstance(obj, dict):
        return {k: deep_fix(v) for k, v in obj.items()}
    return obj


def carry_forward(date: str, src: Path) -> dict:
    data = json.loads(src.read_text(encoding="utf-8"))
    data = deep_fix(data)
    data.pop("perfiles_involucrados", None)
    data["lentes_aplicadas"] = LENTES
    data["date"] = date
    data.setdefault("version", 1)
    data["generado_por"] = "generate_editorial.py --carry-forward (contenido original conservado, schema ajustado)"
    return data


def _previous_context(repo_data_dir: Path, date: str, max_days: int = 2) -> str:
    """Resumen breve (posicionamiento + tendencias) de los 1-2 dias previos
    mas recientes que ya tengan editorial.json, para continuidad -- nunca
    se copia literal al output, solo se pasa como contexto de lectura."""
    if not repo_data_dir.exists():
        return ""
    candidates = sorted(
        (p for p in repo_data_dir.iterdir() if p.is_dir() and p.name < date and (p / "editorial.json").exists()),
        reverse=True,
    )[:max_days]
    if not candidates:
        return ""
    chunks = []
    for d in candidates:
        try:
            prev = json.loads((d / "editorial.json").read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            continue
        chunks.append(
            f"- {d.name}: {prev.get('posicionamiento', '')[:400]}"
        )
    if not chunks:
        return ""
    return "CONTEXTO DE CONTINUIDAD (dias previos, NO copiar literal):\n" + "\n".join(chunks) + "\n\n"


def build_payload(enriched: dict) -> dict:
    items = enriched.get("items", [])
    hallazgos = []
    for it in items:
        if it.get("seccion") != "hallazgo_principal":
            continue
        contenido = it.get("contenido", {})
        hallazgos.append({
            "idx": it["idx"],
            "titulo": it.get("titulo", ""),
            "que_es": contenido.get("que_es", "")[:400],
            "por_que_importa": contenido.get("por_que_importa", "")[:800],
            "relacion_grafo": it.get("relacion_grafo", []),
        })
    return {
        "date": enriched.get("date"),
        "resumen_ejecutivo": enriched.get("resumen_ejecutivo", "")[:1000],
        "radar_secundario_count": sum(1 for it in items if it.get("seccion") == "radar_secundario"),
        "hallazgos_principales": hallazgos,
    }


def _cap(text: str, limit: int) -> str:
    text = strip_cjk(str(text or "").strip())
    return text[:limit]


def run_generation(enriched_path: Path, repo_data_dir: Path, date: str, work_dir: Path, timeout: int) -> tuple[dict | None, str]:
    enriched = json.loads(enriched_path.read_text(encoding="utf-8"))
    payload = build_payload(enriched)
    if not payload["hallazgos_principales"]:
        return None, "sin hallazgos_principales en el enriched.json, nada que sintetizar"

    valid_idx = {h["idx"] for h in payload["hallazgos_principales"]}
    context = _previous_context(repo_data_dir, date)

    main_prompt = EDITORIAL_INSTRUCTIONS + context + json.dumps(payload, ensure_ascii=False, indent=2)
    retry_template = (
        "Tu respuesta anterior fue rechazada por el validador del boletin. "
        "Problema detectado: {motivo}. "
        "Reescribe UNICAMENTE el campo `posicionamiento` con las restricciones "
        "duras del prompt original aplicadas con mas rigor: 80-350 chars, "
        "arranca DIRECTO con la tesis (sin 'El boletin de hoy', 'Hoy', etc.), "
        "divide en 2-3 frases cortas si la tesis pide mas. Devuelve SOLO el "
        "campo corregido en JSON, sin markdown fences, sin campos extra. "
        "Respuesta anterior (rechazada): {previo}\n\n"
    )

    def _do_call(prompt: str) -> str | None:
        return call_hermes(prompt, work_dir, tag=f"{date}.editorial", timeout=timeout)

    def _clean_parse(raw: str | None) -> dict | None:
        if raw is None:
            return None
        parsed = parse_json_lenient(raw)
        return parsed if isinstance(parsed, dict) else None

    # Primer intento
    raw = _do_call(main_prompt)
    parsed = _clean_parse(raw)
    if parsed is None:
        return None, "hermes -z fallo o no disponible (ver stderr arriba)"

    motivo = "sintesis generada"
    pos = parsed.get("posicionamiento", "") or ""
    pos_problema = _validate_posicionamiento(pos)

    # Reintento unico si falla validacion.
    if pos_problema:
        print(f"  posicionamiento falla validador: {pos_problema} -- reintentando", file=sys.stderr)
        retry_prompt = retry_template.format(motivo=pos_problema, previo=pos[:300])
        retry_parsed = _clean_parse(_do_call(retry_prompt))
        if retry_parsed and isinstance(retry_parsed.get("posicionamiento"), str):
            pos2 = retry_parsed["posicionamiento"]
            if not _validate_posicionamiento(pos2):
                parsed = retry_parsed
                pos = pos2
                pos_problema = None
                motivo += "; posicionamiento regenerado tras 1 reintento"

    # Fallback si el reintento tampoco pasa: truncado honesto sin muletilla.
    if pos_problema:
        print(f"  posicionamiento sigue fallando ({pos_problema}); aplico fallback de truncar", file=sys.stderr)
        pos = _strip_filler_prefix(pos)
        if _starts_with_filler(pos):
            pos = pos[:300]
        pos = pos[:POSICIONAMIENTO_MAX]
        motivo += f"; fallback aplicado (validacion fallo: {pos_problema})"

    # ── Titular ──────────────────────────────────────────────────
    # Mismo trato que el posicionamiento: se valida, se reintenta una vez
    # y, si sigue fallando, se deriva del posicionamiento en vez de
    # persistir un titular-parrafo.
    titular = (parsed.get("titular") or "").strip()
    tit_problema = _validate_titular(titular)
    if tit_problema:
        print(f"  titular falla validador: {tit_problema} -- reintentando", file=sys.stderr)
        tit_retry = _clean_parse(_do_call(
            "Tu respuesta anterior traia un 'titular' invalido: " + tit_problema + ". "
            "Titular previo: " + titular[:200] + ". "
            "Devuelve SOLO {\"titular\": \"...\"} con un titular de 35-85 chars, una sola idea, "
            "sin punto final, sin muletilla ('El boletin de hoy', 'Hoy', 'Tres ejes') y sin "
            "enumerar. Sin markdown fences."
        ))
        if tit_retry and isinstance(tit_retry.get("titular"), str):
            cand = tit_retry["titular"].strip()
            if not _validate_titular(cand):
                titular = cand
                tit_problema = None
                motivo += "; titular regenerado tras 1 reintento"
    if tit_problema:
        titular = _titular_desde_posicionamiento(pos)
        motivo += f"; titular derivado del posicionamiento (validacion fallo: {tit_problema})"

    alertas = parsed.get("alertas", [])
    if not isinstance(alertas, list):
        alertas = []
    alertas = [_cap(a, 400) for a in alertas if str(a).strip()][:6]

    acciones_raw = parsed.get("acciones_concretas", [])
    if not isinstance(acciones_raw, list):
        acciones_raw = []
    acciones = []
    dropped_idx = []
    for a in acciones_raw[:5]:
        if not isinstance(a, dict):
            continue
        try:
            idx = int(a.get("item_idx"))
        except (TypeError, ValueError):
            continue
        if idx not in valid_idx:
            dropped_idx.append(idx)
            continue
        tipo = str(a.get("tipo", "")).strip() or "vigilar"
        acciones.append({"tipo": tipo, "item_idx": idx, "razon": _cap(a.get("razon", ""), 400)})

    data = {
        "version": 1,
        "date": date,
        "lentes_aplicadas": LENTES,
        "titular": _cap(titular, TITULAR_MAX),
        "posicionamiento": _cap(pos, POSICIONAMIENTO_MAX),
        "convergencia_stack_css": _cap(parsed.get("convergencia_stack_css", ""), CONVERGENCIA_MAX),
        "cruzado_grafo": _cap(parsed.get("cruzado_grafo", ""), CRUZADO_MAX),
        "tendencias_5_boletines": _cap(parsed.get("tendencias_5_boletines", ""), TENDENCIAS_MAX),
        "alertas": alertas,
        "acciones_concretas": acciones,
        "generado_por": "generate_editorial.py --llm hermes (generacion nueva)",
    }

    if dropped_idx:
        motivo += f"; item_idx invalidos descartados de acciones_concretas: {dropped_idx}"
    if not data["posicionamiento"]:
        return None, "respuesta sin 'posicionamiento' util, no se persiste editorial vacio"
    return data, motivo


def main() -> int:
    ap = argparse.ArgumentParser(description="Genera/actualiza editorial.json")
    ap.add_argument("--date", type=str, required=True)
    ap.add_argument("--carry-forward", type=Path, default=None)
    ap.add_argument("--enriched", type=Path, default=None, help="enriched.json del dia (requerido para generacion nueva)")
    ap.add_argument("--repo-data-dir", type=Path, default=None, help="apps/web/src/data/boletines (para contexto de dias previos)")
    ap.add_argument("--llm", choices=["hermes", "none"], default="hermes")
    ap.add_argument("--work-dir", type=Path, default=Path("~/.hermes/data/tecnoboletin/_work").expanduser())
    ap.add_argument("--timeout", type=int, default=240)
    ap.add_argument("--out", type=Path, required=True)
    args = ap.parse_args()

    if args.carry_forward:
        if not args.carry_forward.exists():
            print(f"ERROR: no encontrado {args.carry_forward}", file=sys.stderr)
            return 1
        data = carry_forward(args.date, args.carry_forward)
    else:
        if not args.enriched or not args.enriched.exists():
            print("ERROR: generacion nueva de editorial.json requiere --enriched <enriched.json del dia>", file=sys.stderr)
            return 2

        llm = args.llm
        if llm == "hermes":
            ok, reason = hermes_available()
            if not ok:
                print(
                    f"ERROR: --llm hermes pedido pero no disponible ({reason}) -- generacion nueva de "
                    f"editorial.json requiere backend LLM. Usa --carry-forward si ya existe un editorial.json "
                    f"aprobado para esta fecha.",
                    file=sys.stderr,
                )
                return 3

        print("Generando editorial.json via hermes -z (1 llamada batcheada)...", file=sys.stderr)
        data, motivo = run_generation(
            args.enriched, args.repo_data_dir or Path("."), args.date, args.work_dir, args.timeout
        )
        print(f"  {motivo}", file=sys.stderr)
        if data is None:
            print(f"ERROR: generacion nueva fallo: {motivo}", file=sys.stderr)
            return 4

    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"Escrito: {args.out}", file=sys.stderr)
    return 0


if __name__ == "__main__":
    sys.exit(main())
