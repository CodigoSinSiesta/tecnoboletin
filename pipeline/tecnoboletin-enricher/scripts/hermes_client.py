#!/usr/bin/env python3
"""hermes_client.py -- backend LLM real para esta skill: invoca `hermes -z`
(Hermes Agent CLI, ya configurado en este runtime con MiniMax-M3 -- ver
~/.hermes/config.yaml, model.provider: minimax). Es el mismo mecanismo que
usa con exito el cron del boletin original todos los dias.

No requiere Ollama ni el SDK de Pi Agent (roto, ver SKILL.md). El binario
vive en ~/.local/bin/hermes, que normalmente no esta en el PATH de una
sesion SSH no interactiva -- por eso este modulo lo busca explicitamente.

Cada llamada es "one-shot" (`-z`): levanta un agente completo, tarda
~15-40s incluso para un prompt corto. Por eso la pipeline BATCHEA: una
sola llamada por dia para pulir todos los items, una sola llamada por dia
para la critica de 3 lentes + reescritura -- nunca una llamada por item.

El prompt se escribe siempre a fichero antes de invocar el binario (nunca
se pasa un string largo inline en un comando de shell) para evitar
problemas de escapado/longitud; luego se lee y se pasa como argumento de
proceso directo (subprocess con lista de argv, sin shell=True), asi que
el contenido (incluido JSON con comillas) llega intacto sin más
escapado manual.
"""
from __future__ import annotations

import json
import re
import shutil
import subprocess
import sys
import unicodedata
from pathlib import Path

HERMES_CANDIDATES = [
    Path("~/.local/bin/hermes").expanduser(),
    Path(shutil.which("hermes") or ""),
]

CJK_RE = re.compile(r"[一-鿿]+")


def find_hermes() -> Path | None:
    for candidate in HERMES_CANDIDATES:
        if candidate and candidate.exists():
            return candidate
    return None


def hermes_available() -> tuple[bool, str]:
    """Devuelve (disponible, motivo). No asume -- si no esta, dice por que."""
    binpath = find_hermes()
    if not binpath:
        return False, "binario 'hermes' no encontrado (probado ~/.local/bin/hermes y PATH)"
    try:
        proc = subprocess.run([str(binpath), "--version"], capture_output=True, text=True, timeout=15)
    except Exception as exc:
        return False, f"'hermes --version' fallo: {exc}"
    if proc.returncode != 0:
        return False, f"'hermes --version' devolvio exit {proc.returncode}: {proc.stderr.strip()[:200]}"
    return True, proc.stdout.strip().splitlines()[0] if proc.stdout.strip() else "ok"


def strip_cjk(text: str) -> str:
    """El modelo (MiniMax-M3) a veces deja una fuga aislada de caracteres
    CJK en medio de texto en espanol (visto en pruebas reales -- ver
    SKILL.md). Se elimina como ruido, igual que las fugas del .md origen
    (scripts/clean_cjk.py hace el chequeo final antes de persistir)."""
    if not text or not CJK_RE.search(text):
        return text
    cleaned = CJK_RE.sub("", text)
    return re.sub(r"\s+", " ", cleaned).strip(" ,.-—–")


def call_hermes(prompt: str, work_dir: Path, tag: str, timeout: int = 240) -> str | None:
    """Escribe el prompt a fichero, invoca `hermes -z`, devuelve stdout (o
    None si falla). No lanza excepcion -- el caller decide como degradar."""
    binpath = find_hermes()
    if not binpath:
        print("ERROR: hermes no disponible (ver hermes_available())", file=sys.stderr)
        return None

    work_dir.mkdir(parents=True, exist_ok=True)
    prompt_path = work_dir / f"{tag}.prompt.txt"
    prompt_path.write_text(prompt, encoding="utf-8")

    prompt_text = prompt_path.read_text(encoding="utf-8")
    try:
        proc = subprocess.run(
            [str(binpath), "-z", prompt_text],
            capture_output=True,
            text=True,
            timeout=timeout,
        )
    except subprocess.TimeoutExpired:
        print(f"ERROR: hermes -z timeout ({timeout}s) en {tag}", file=sys.stderr)
        return None
    except Exception as exc:
        print(f"ERROR: hermes -z fallo en {tag}: {exc}", file=sys.stderr)
        return None

    if proc.returncode != 0:
        print(f"ERROR: hermes -z exit {proc.returncode} en {tag}: {proc.stderr.strip()[:400]}", file=sys.stderr)
        return None

    out_path = work_dir / f"{tag}.response.txt"
    out_path.write_text(proc.stdout, encoding="utf-8")
    return proc.stdout


def parse_json_lenient(text: str) -> list | dict | None:
    """Parsea JSON devuelto por el modelo. Defensivo ante 3 fallos
    observados en pruebas reales:
    1. Fences de markdown (```json ... ```).
    2. Array/objeto sin el cierre final (`]`/`}`) -- visto de forma
       consistente en las respuestas de hermes -z/MiniMax-M3 en este
       runtime; probablemente un corte de longitud de salida. Se
       reintenta anadiendo el cierre que falte antes de dar por fallida
       la respuesta.
    3. Preambulo conversacional antes del JSON ("Ahora analizo los datos...       {...}") -- visto en generate_editorial.py. Se busca el primer `{` o
       `[` real y se descarta todo lo anterior antes de intentar parsear."""
    if not text:
        return None
    cleaned = text.strip()
    fence = re.match(r"^```(?:json)?\s*\n?(.*?)\n?```\s*$", cleaned, re.DOTALL)
    if fence:
        cleaned = fence.group(1).strip()

    if cleaned[:1] not in ("{", "["):
        first_brace = min(
            (i for i in (cleaned.find("{"), cleaned.find("[")) if i != -1),
            default=-1,
        )
        if first_brace > 0:
            cleaned = cleaned[first_brace:]

    for attempt in (cleaned, cleaned + "]", cleaned + "}", cleaned + "]}", cleaned + "}]"):
        try:
            return json.loads(attempt)
        except json.JSONDecodeError:
            continue
    return None
