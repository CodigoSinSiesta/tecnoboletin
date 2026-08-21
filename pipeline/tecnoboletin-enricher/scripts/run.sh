#!/usr/bin/env bash
# run.sh (v2) -- pipeline completa de tecnoboletin-enricher sobre un boletin.
#
# Uso: run.sh <YYYY-MM-DD>
#       (sin args: usa el boletin mas reciente del vault)
#
# Escribe DIRECTAMENTE al repo (apps/web/src/data/boletines/<date>/) --
# esa es la fuente de verdad real que consume la web, no
# ~/.hermes/data/tecnoboletin/ (ver SKILL.md). Sigue el patron
# draft-then-cp: todo se genera primero en un dir de trabajo temporal en
# $HOME, se pasa el chequeo CJK, y solo entonces se copia al repo.
#
# Pasos:
#  1. extract_items.py       -> items ricos (deterministico, sin LLM)
#  2. enrich_items.py        -> conserva/pule contenido + cruce con el grafo
#  3. synthesize_article.py  -> 3 lentes de critica (en memoria) + reescritura
#  4. generate_editorial.py  -> editorial.json (carry-forward si ya existe uno aprobado)
#  5. persist.py             -> escribe enriched.json + edges.jsonl al repo
#  6. clean_cjk.py           -> validacion final

set -euo pipefail

SKILL_DIR="$(cd "$(dirname "$0")/.." && pwd)"
VAULT_DIR="${HOME}/obsidian-vault/Research/Boletines"
REPO_DATA_DIR="${HOME}/proyectos/tecnoboletin/apps/web/src/data/boletines"
WORK_DIR="${HOME}/.hermes/data/tecnoboletin/_work"
LLM_BACKEND="${TECNOBOLETIN_LLM:-hermes}"   # "hermes" o "none" -- ver SKILL.md ("Estado del backend LLM")

if [[ $# -ge 1 ]]; then
  DATE="$1"
else
  DATE="$(ls -t "${VAULT_DIR}"/*.md 2>/dev/null | head -1 | grep -oE '[0-9]{4}-[0-9]{2}-[0-9]{2}' | head -1)"
fi

if [[ -z "${DATE:-}" ]]; then
  echo "ERROR: no se pudo determinar fecha" >&2
  exit 2
fi

MD="${VAULT_DIR}/${DATE}-trending.md"
if [[ ! -f "${MD}" ]]; then
  echo "ERROR: no hay boletin para ${DATE} en ${MD}" >&2
  exit 3
fi

mkdir -p "${WORK_DIR}"
ITEMS_JSON="${WORK_DIR}/${DATE}.items.json"
ENRICHED_JSON="${WORK_DIR}/${DATE}.enriched.json"
FINAL_JSON="${WORK_DIR}/${DATE}.final.json"
EDITORIAL_JSON="${WORK_DIR}/${DATE}.editorial.json"

OLD_ENRICHED="${REPO_DATA_DIR}/${DATE}/enriched.json"
OLD_EDITORIAL="${REPO_DATA_DIR}/${DATE}/editorial.json"

echo "[1/6] Extrayendo items de ${DATE}..."
python3 "${SKILL_DIR}/scripts/extract_items.py" "${MD}" > "${ITEMS_JSON}"

echo "[2/6] Enriqueciendo (conserva contenido + cruce con el grafo)..."
CARRY_ARGS=()
if [[ -f "${OLD_ENRICHED}" ]]; then
  CARRY_ARGS=(--carry-metadata-from "${OLD_ENRICHED}")
fi
python3 "${SKILL_DIR}/scripts/enrich_items.py" "${ITEMS_JSON}" --date "${DATE}" \
  --llm "${LLM_BACKEND}" --work-dir "${WORK_DIR}" "${CARRY_ARGS[@]}" --out "${ENRICHED_JSON}"

echo "[3/6] Critica (3 lentes, 1 llamada batcheada) + reescritura..."
python3 "${SKILL_DIR}/scripts/synthesize_article.py" --date "${DATE}" --enriched "${ENRICHED_JSON}" \
  --llm "${LLM_BACKEND}" --work-dir "${WORK_DIR}" --out "${FINAL_JSON}"

echo "[4/6] editorial.json..."
if [[ -f "${OLD_EDITORIAL}" ]]; then
  python3 "${SKILL_DIR}/scripts/generate_editorial.py" --date "${DATE}" --carry-forward "${OLD_EDITORIAL}" --out "${EDITORIAL_JSON}"
else
  # Generacion nueva vale la pena intentarla pero NO debe tumbar el pipeline
  # completo si falla (set -e esta activo) -- el hallazgo/por_que_importa ya
  # persistido en FINAL_JSON es el contenido central; el editorial es una
  # capa de sintesis adicional. Si falla, se loguea y la pagina renderiza
  # sin seccion editorial, igual que el comportamiento original.
  set +e
  python3 "${SKILL_DIR}/scripts/generate_editorial.py" --date "${DATE}" --enriched "${FINAL_JSON}" \
    --repo-data-dir "${REPO_DATA_DIR}" --llm "${LLM_BACKEND}" --work-dir "${WORK_DIR}" --out "${EDITORIAL_JSON}"
  EDITORIAL_STATUS=$?
  set -e
  if [[ ${EDITORIAL_STATUS} -ne 0 ]]; then
    echo "  AVISO: generacion de editorial.json fallo (exit ${EDITORIAL_STATUS}) -- continuando sin seccion editorial." >&2
    rm -f "${EDITORIAL_JSON}"
  fi
fi

echo "[5/6] CJK check..."
CJK_ARGS=("${FINAL_JSON}")
[[ -f "${EDITORIAL_JSON}" ]] && CJK_ARGS+=("${EDITORIAL_JSON}")
python3 "${SKILL_DIR}/scripts/clean_cjk.py" "${CJK_ARGS[@]}"

echo "[6/6] Persistiendo al repo (${REPO_DATA_DIR}/${DATE}/)..."
python3 "${SKILL_DIR}/scripts/persist.py" --date "${DATE}" --enriched "${FINAL_JSON}" --repo-data-dir "${REPO_DATA_DIR}"
if [[ -f "${EDITORIAL_JSON}" ]]; then
  cp "${EDITORIAL_JSON}" "${REPO_DATA_DIR}/${DATE}/editorial.json"
  echo "Escrito: ${REPO_DATA_DIR}/${DATE}/editorial.json"
fi

echo "Done. Outputs:"
ls -la "${REPO_DATA_DIR}/${DATE}/"
