#!/bin/bash
# Régénère les PDF à partir des sources HTML (Chrome headless).
# Usage : ./build_pdf.sh   (depuis le dossier sources/)
set -e
cd "$(dirname "$0")"
CHROME="/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"
print() { "$CHROME" --headless=new --disable-gpu --no-pdf-header-footer --allow-file-access-from-files \
  --print-to-pdf="$2" "file://$PWD/$1" 2>/dev/null; echo "OK : $2"; }
print poster.html  ../Workshop2026-B4-G7-Poster-A3.pdf
print cover.html   ./dossier-couverture.pdf
print dossier.html ./dossier-corps.pdf
# Dossier final = corps + poster A3 en annexe
python3 - <<'PY'
from pypdf import PdfReader, PdfWriter
w = PdfWriter()
for f in ["dossier-couverture.pdf", "dossier-corps.pdf", "../Workshop2026-B4-G7-Poster-A3.pdf"]:
    for p in PdfReader(f).pages: w.add_page(p)
w.add_metadata({"/Title": "Sentinel-X - Dossier d'ingénierie - Workshop2026-B4-G7", "/Author": "Groupe 7"})
w.write("../Workshop2026-B4-G7-Dossier.pdf")
print("OK : ../Workshop2026-B4-G7-Dossier.pdf")
PY
rm -f dossier-couverture.pdf dossier-corps.pdf
