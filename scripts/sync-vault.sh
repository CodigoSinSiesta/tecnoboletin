#!/usr/bin/env bash
#
# sync-vault.sh — copia los boletines .md del Obsidian vault al repo tecnoboletín
#
# Uso:
#   ./scripts/sync-vault.sh [--dry-run] [--auto-commit]
#
# Origen: $HOME/obsidian-vault/Research/Boletines/*.md
# Destino: apps/web/src/content/boletines/
#
# NO toca los .md. Solo los copia. El enriquecido (fase 2) crea .enriched.json adyacentes.

set -euo pipefail

VAULT_DIR="${HOME}/obsidian-vault/Research/Boletines"
REPO_ROOT="$(cd "$(dirname "$0")/.." && pwd)"
DEST="${REPO_ROOT}/apps/web/src/content/boletines"

DRY_RUN=0
AUTO_COMMIT=0
for arg in "$@"; do
  case "$arg" in
    --dry-run) DRY_RUN=1 ;;
    --auto-commit) AUTO_COMMIT=1 ;;
    *) echo "Argumento desconocido: $arg" >&2; exit 1 ;;
  esac
done

if [[ ! -d "$VAULT_DIR" ]]; then
  echo "ERROR: vault dir no encontrado: $VAULT_DIR" >&2
  exit 1
fi

mkdir -p "$DEST"

count=0
shopt -s nullglob
for src_md in "$VAULT_DIR"/*.md; do
  fname="$(basename "$src_md")"
  dest_md="$DEST/$fname"
  if [[ -f "$dest_md" ]] && cmp -s "$src_md" "$dest_md"; then
    continue
  fi
  echo "→ $fname"
  if [[ "$DRY_RUN" -eq 0 ]]; then
    cp "$src_md" "$dest_md"
  fi
  count=$((count + 1))
done

echo "Total sincronizados: $count"

if [[ "$count" -gt 0 && "$AUTO_COMMIT" -eq 1 && "$DRY_RUN" -eq 0 ]]; then
  cd "$REPO_ROOT"
  git add "$DEST"
  git commit -m "sync: boletines desde vault ($(date +%Y-%m-%d))"
  git push origin main
fi
