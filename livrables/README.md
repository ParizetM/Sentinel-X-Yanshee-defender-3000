# Livrables Workshop2026-M1-G7

| Fichier | État |
|---|---|
| `Workshop2026-M1-G7-Dossier.pdf` | Prêt, avec des éléments à compléter (voir ci-dessous). Le poster A3 est en dernière page. |
| `Workshop2026-M1-G7-Pres.pptx` | Prêt. Notes orateur calées sur le chrono. Diapo 12 à compléter après le pentest. |
| `Workshop2026-M1-G7-Poster-A3.pdf` | Prêt (également inclus dans le dossier). |
| `SCRIPT_ORAL.md` | Ce qu'il faut dire, diapo par diapo, avec le chrono, la checklist de démo et les questions probables du jury. |
| `Workshop2026-M1-G7-Code.zip` | Hors dépôt (c'est l'archive du dépôt lui-même) : dans `Workshop-2026/Workshop2026-M1-G7/`. |
| `VidDrop-H264-79s-A-RACCOURCIR-A-60s.mp4` (hors dépôt, même dossier) | Réencodé en H.264, mais **79 s** : à couper à 60 s maximum, puis renommer `Workshop2026-M1-G7-VidDrop.mp4`. |

## À compléter dans le dossier, puis régénérer

Modifier `sources/dossier.html`, puis lancer `sources/build_pdf.sh` (Chrome + pypdf).

- Section 07 : la latence d'inférence YOLO mesurée (`____ ms`).
- Section 11.3 : les tableaux du pentest croisé.
- Sections 06, 09 et 12 : les captures du dashboard et de Zabbix, et les photos du boîtier et de la gravure (déposer les images dans `sources/img/` et remplacer les cadres pointillés `todo-box` par des balises `<img>`).

La présentation se régénère avec `sources/pptx/deck.js` (pptxgenjs), ou se modifie directement dans PowerPoint.
