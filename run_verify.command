#!/usr/bin/env bash
# ============================================================================
# 新架构端到端验证一键脚本（双击即运行）
# 说明：
#   - 自动在项目根创建 .venv 隔离环境（兼容 Homebrew PEP 668）
#   - 对 test/1..4 全量图片+Excel 跑 OCR + 三层匹配 + 报告
#   - 若存在 GEMINI_API_KEY / credentials.json.gemini.api_key 则启用 LLM 兜底
#   - 输出：test/<N>/report.json + test/<N>/report.md
# ============================================================================

set -eu

# 1. 切到脚本所在目录（项目根）
cd "$(dirname "$0")"
PROJECT_ROOT="$(pwd)"
SKILL_DIR="$PROJECT_ROOT/skills/medical-exam-checker"
CHECK_SCRIPT="$SKILL_DIR/scripts/check.py"
CREDENTIALS="$SKILL_DIR/config/credentials.json"
VENV_DIR="$PROJECT_ROOT/.venv"
REQUIREMENTS="$SKILL_DIR/requirements.txt"

echo "[INFO][Verify:main] Project root: $PROJECT_ROOT"

# 2. 检测系统 Python（仅用于创建 venv）
if command -v python3 >/dev/null 2>&1; then
  SYS_PY=python3
elif command -v python >/dev/null 2>&1; then
  SYS_PY=python
else
  echo "[ERROR][Verify:main] Python not found. Install via: brew install python"
  exit 1
fi
echo "[INFO][Verify:main] System Python: $($SYS_PY --version 2>&1)"

# 3. 创建 / 复用项目 venv（隔离依赖，兼容 PEP 668）
if [ ! -x "$VENV_DIR/bin/python" ]; then
  echo "[INFO][Verify:main] Creating venv at $VENV_DIR ..."
  $SYS_PY -m venv "$VENV_DIR" || {
    echo "[ERROR][Verify:main] venv create failed. Try: $SYS_PY -m pip install --user virtualenv"
    exit 1
  }
fi
VENV_PY="$VENV_DIR/bin/python"
echo "[INFO][Verify:main] Venv Python: $($VENV_PY --version 2>&1)"

# 4. 依赖自检 + 安装（仅在缺失时安装；装在 venv 内，不碰系统）
if ! $VENV_PY -c "import fuzzywuzzy, pandas, requests, openpyxl" 2>/dev/null; then
  echo "[INFO][Verify:main] Installing dependencies into venv ..."
  $VENV_PY -m pip install --upgrade pip >/dev/null 2>&1 || true
  $VENV_PY -m pip install -r "$REQUIREMENTS" || {
    echo "[ERROR][Verify:main] Dependency install failed. Check network."
    exit 1
  }
else
  echo "[INFO][Verify:main] Dependencies already present."
fi

# 5. LLM 开关检测
LLM_ARGS=(--llm-provider gemini)
if [ -n "${GEMINI_API_KEY:-}" ]; then
  echo "[INFO][Verify:main] GEMINI_API_KEY detected from env."
elif [ -f "$CREDENTIALS" ] && $VENV_PY -c "
import json, sys
d = json.load(open('$CREDENTIALS'))
k = d.get('gemini', {}).get('api_key', '')
sys.exit(0 if k and 'YOUR_' not in k else 1)
" 2>/dev/null; then
  echo "[INFO][Verify:main] Gemini key found in credentials.json."
else
  echo "[WARN][Verify:main] No Gemini key found; falling back to rule+fuzzy only."
  LLM_ARGS=(--no-llm)
fi

# 6. 逐个 test 目录跑
for N in 1 2 3 4; do
  TEST_DIR="$PROJECT_ROOT/test/$N"
  [ -d "$TEST_DIR" ] || { echo "[WARN][Verify:main] Skip missing $TEST_DIR"; continue; }

  XLSX=$(ls "$TEST_DIR"/*.xlsx 2>/dev/null | head -1)
  IMAGES_EXIST=()
  for f in "$TEST_DIR"/*.jpeg "$TEST_DIR"/*.jpg "$TEST_DIR"/*.png; do
    [ -f "$f" ] && IMAGES_EXIST+=("$f")
  done

  if [ -z "${XLSX:-}" ] || [ ${#IMAGES_EXIST[@]} -eq 0 ]; then
    echo "[WARN][Verify:main] Skip $TEST_DIR (no xlsx or images)"
    continue
  fi

  echo ""
  echo "======================================================================"
  echo "[INFO][Verify:main] test/$N — Excel: $(basename "$XLSX")  Images: ${#IMAGES_EXIST[@]}"
  echo "======================================================================"

  $VENV_PY "$CHECK_SCRIPT" \
    --excel "$XLSX" \
    --images "${IMAGES_EXIST[@]}" \
    --ocr-cache-dir "$TEST_DIR/.ocr_cache" \
    --llm-cache-dir "$TEST_DIR/.llm_cache" \
    --output "$TEST_DIR/report.json" \
    --markdown "$TEST_DIR/report.md" \
    "${LLM_ARGS[@]}"
done

echo ""
echo "======================================================================"
echo "[INFO][Verify:main] DONE. Reports at: test/<N>/report.json + report.md"
echo "======================================================================"
echo "Press any key to close..."
read -n 1 -s
