#!/usr/bin/env bash
# Paired Copilot experiment for management evidence.
# Run the same prompt twice: once direct, once through TrimP.
set -euo pipefail

MODE="${1:-}"
PROMPT="${2:-Review this repository and summarize its architecture, main risks, and the three highest-value improvements. Do not modify files.}"
MODEL="${COPILOT_MODEL:-gpt-5-mini}"

if [[ "$MODE" != "baseline" && "$MODE" != "TrimP" ]]; then
  echo "Usage: $0 baseline|TrimP \"prompt\"" >&2
  exit 2
fi

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
STAMP="$(date -u +%Y%m%dT%H%M%SZ)"
OUT_DIR="${TRIMP_EXPERIMENT_DIR:-$HOME/.trimp/experiments}"
mkdir -p "$OUT_DIR"
OUT="$OUT_DIR/${STAMP}-${MODE}.json"

if [[ "$MODE" == "TrimP" ]]; then
  export COPILOT_MODEL="$MODEL"
  "$ROOT_DIR/scripts/TrimP-copilot" -p "$PROMPT" --allow-all-tools --allow-all-paths --stream off --output-format json >"$OUT"
else
  copilot --model "$MODEL" -p "$PROMPT" --allow-all-tools --allow-all-paths --stream off --output-format json >"$OUT"
fi

echo "Saved $MODE result to $OUT"
