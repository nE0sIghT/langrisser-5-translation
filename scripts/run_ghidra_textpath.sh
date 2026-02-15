#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
GHIDRA_DIR="${GHIDRA_DIR:-$ROOT_DIR/external/ghidra/ghidra_12.0.3_PUBLIC}"
TEMURIN_JDK="${TEMURIN_JDK:-$ROOT_DIR/external/ghidra/jdk-21.0.10+7}"
ANALYZE="$GHIDRA_DIR/support/analyzeHeadless"
PROJECT_DIR="${PROJECT_DIR:-$ROOT_DIR/work/ghidra_proj}"
PROJECT_NAME="${PROJECT_NAME:-lang5_full_textpath}"
INPUT_EXE="${INPUT_EXE:-$ROOT_DIR/work/extracted/SLPS_018.19}"
SCRIPT_PATH="${SCRIPT_PATH:-$ROOT_DIR/scripts}"
POST_SCRIPT="${POST_SCRIPT:-GhidraDumpTextPath.java}"

if [[ ! -x "$ANALYZE" ]]; then
  echo "analyzeHeadless not found: $ANALYZE" >&2
  exit 1
fi

if [[ ! -f "$INPUT_EXE" ]]; then
  echo "Input EXE not found: $INPUT_EXE" >&2
  exit 1
fi

if [[ -x "$TEMURIN_JDK/bin/java" ]]; then
  export JAVA_HOME="$TEMURIN_JDK"
  export PATH="$JAVA_HOME/bin:$PATH"
fi

echo "JAVA_HOME=${JAVA_HOME:-<unset>}"
java -version

"$ANALYZE" \
  "$PROJECT_DIR" \
  "$PROJECT_NAME" \
  -import "$INPUT_EXE" \
  -overwrite \
  -scriptPath "$SCRIPT_PATH" \
  -postScript "$POST_SCRIPT" \
  -analysisTimeoutPerFile 1800 \
  -deleteProject

echo "Done. Dump: $ROOT_DIR/work/scen_analysis/ghidra_text_path_dump.txt"
