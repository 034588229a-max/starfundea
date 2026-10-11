#!/usr/bin/env bash
# 安裝測試相依（第一次執行一次即可）
set -e
cd "$(dirname "$0")/.."
pip install playwright zxing-cpp pillow 2>/dev/null || pip install --break-system-packages playwright zxing-cpp pillow
python3 -m playwright install chromium || true
command -v pdftoppm >/dev/null || echo '請安裝 poppler（pdftoppm）：macOS brew install poppler；Ubuntu sudo apt install poppler-utils'
mkdir -p tests/vendor && cd tests/vendor
for p in html2canvas@1.4.1 jspdf@2.5.1; do
  n=${p/@/-}
  [ -d "$n" ] || { npm pack "$p" --silent >/dev/null && tar xzf "$n.tgz" && mv package "$n" && rm "$n.tgz"; }
done
echo '完成。執行：python3 tests/integration_e2e.py && python3 tests/tools_e2e.py'
