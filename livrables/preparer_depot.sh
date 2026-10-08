#!/bin/bash
# Prépare le dossier à déposer sur le Drive, avec le nommage exigé par les coachs :
#   Workshop2026-B4-G7-VOS_NOMS-{Dossier.pdf, pres.pptx, VidDrop.mp4, Code.zip} + documents annexes
#
# Usage : ./livrables/preparer_depot.sh NOM1_NOM2_NOM3_NOM4_NOM5 [chemin/vers/teaser-60s.mp4]
# Le dossier est créé à côté du dépôt (../Depot-Drive-G7) pour ne pas versionner le zip ni la vidéo.
set -euo pipefail

NOMS="${1:-}"
VIDEO="${2:-}"
if [[ ! "$NOMS" =~ ^[A-Za-z][A-Za-z_-]*$ ]]; then
  echo "Usage : $0 NOM1_NOM2_NOM3_NOM4_NOM5 [teaser.mp4]  (lettres et underscores, sans accent ni espace)" >&2
  exit 1
fi

REPO="$(cd "$(dirname "$0")/.." && pwd)"
OUT="$(dirname "$REPO")/Depot-Drive-G7"
P="Workshop2026-B4-G7-$NOMS"
cd "$REPO"

if [[ -n "$(git status --porcelain)" ]]; then
  echo "Attention : modifications non commitées, elles ne seront pas dans le Code.zip (construit depuis HEAD)." >&2
fi

rm -rf "$OUT" && mkdir -p "$OUT"

cp livrables/Workshop2026-B4-G7-Dossier.pdf   "$OUT/$P-Dossier.pdf"
cp livrables/Workshop2026-B4-G7-pres.pptx     "$OUT/$P-pres.pptx"
cp livrables/Workshop2026-B4-G7-Poster-A3.pdf "$OUT/$P-Poster-A3.pdf"
cp "Documentation Infrastructure.pdf"         "$OUT/$P-Documentation-Infrastructure.pdf"
cp "Infra (ports, réseau, IP).xlsx"           "$OUT/$P-Infra-Reseau-Ports.xlsx"

# Archive du code : état commité, sans les vidéos
git archive --format=zip --prefix=Sentinel-X-Yanshee-defender-3000/ -o "$OUT/$P-Code.zip" HEAD -- . ':(exclude)*.mp4'
if unzip -p "$OUT/$P-Code.zip" | grep -aqE "Epsi1234|Epsi123!|EpsiWis|sentinel-x-secret-key-2026|Sentinel2026!"; then
  echo "ERREUR : un secret connu est présent dans le Code.zip, dépôt annulé." >&2
  exit 1
fi

# Vidéo : 60 s maximum, H.264
if [[ -n "$VIDEO" ]]; then
  cp "$VIDEO" "$OUT/$P-VidDrop.mp4"
  DUREE="$(mdls -raw -name kMDItemDurationSeconds "$VIDEO" 2>/dev/null || true)"
  if [[ "$DUREE" =~ ^[0-9.]+$ ]] && (( ${DUREE%.*} > 60 )); then
    echo "Attention : la vidéo dure ${DUREE%.*} s, le maximum est 60 s." >&2
  fi
else
  echo "Vidéo non fournie : relancer avec le chemin du teaser de 60 s en second argument." >&2
fi

echo "Dossier prêt : $OUT"
ls -1 "$OUT"
