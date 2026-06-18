#!/bin/bash
# SAK Trading Journal - Startup Script

# Always cd to the script's own directory first
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
cd "$SCRIPT_DIR"

echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "  📈 SAK Trading Journal - FY 2026-27"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""
echo "📂 Working directory: $SCRIPT_DIR"
echo ""

# Find best available Python (prefer 3.11/3.10 on M2 Mac)
PYTHON=""
for candidate in python3.11 python3.10 python3.9 python3; do
    if command -v "$candidate" &>/dev/null; then
        PYTHON="$candidate"
        break
    fi
done

if [ -z "$PYTHON" ]; then
    echo "❌ Python 3 not found. Install from https://python.org"
    exit 1
fi

echo "🐍 Using: $($PYTHON --version)"

# Install deps
echo "📦 Installing / verifying dependencies..."
$PYTHON -m pip install -r "$SCRIPT_DIR/requirements.txt" --quiet

if [ $? -ne 0 ]; then
    echo "❌ Dependency install failed. Try manually:"
    echo "   $PYTHON -m pip install -r requirements.txt"
    exit 1
fi

# Check Excel file
if [ ! -f "$SCRIPT_DIR/Daily_P__FY26-27_.xlsx" ]; then
    echo ""
    echo "⚠️  Excel file not found. Copy Daily_P__FY26-27_.xlsx into:"
    echo "   $SCRIPT_DIR"
    echo ""
fi

echo ""
echo "🚀 Starting app at http://localhost:8501"
echo "   Press Ctrl+C to stop."
echo ""

$PYTHON -m streamlit run "$SCRIPT_DIR/app.py" \
    --server.port=8501 \
    --server.headless=false \
    --browser.gatherUsageStats=false \
    --theme.base=dark
