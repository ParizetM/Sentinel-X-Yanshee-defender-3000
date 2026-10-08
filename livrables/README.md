# Livrables · Workshop2026-B4-G7

Dépôt sur le Drive **avant le jeudi 8 octobre, 20 h**. Nommage imposé : `Workshop2026-B4-G7-VOS_NOMS-<livrable>`, les noms étant séparés par des underscores.

| Fichier du dépôt | Nom sur le Drive | État |
|---|---|---|
| `Workshop2026-B4-G7-Dossier.pdf` | `…-Dossier.pdf` | Prêt, avec quelques éléments à compléter (voir plus bas). Le poster A3 est en dernière page. |
| `Workshop2026-B4-G7-pres.pptx` | `…-pres.pptx` | Prêt. Le nom de l'orateur est en tête des notes de chaque diapo. Diapo 12 à compléter après le pentest. |
| `Workshop2026-B4-G7-Poster-A3.pdf` | `…-Poster-A3.pdf` | Prêt. |
| (archive du dépôt) | `…-Code.zip` | Générée par `preparer_depot.sh` depuis le dernier commit, sans vidéo, avec un contrôle anti-secrets. |
| (teaser) | `…-VidDrop.mp4` | À fournir : **60 s maximum**, H.264, vertical. |
| `Documentation Infrastructure.pdf`, `Infra (ports, réseau, IP).xlsx` | `…-Documentation-Infrastructure.pdf`, `…-Infra-Reseau-Ports.xlsx` | Documents annexes (« tous les autres documents qui aideront à comprendre »). |
| `SCRIPT_ORAL.md` | Ne pas déposer | Usage interne : qui dit quoi, chrono, checklist de démo, questions du jury. |

## Préparer le dossier à déposer

```bash
./livrables/preparer_depot.sh NOM1_NOM2_NOM3_NOM4_NOM5 chemin/vers/teaser-60s.mp4
```

Le script crée `../Depot-Drive-G7/` (à côté du dépôt) avec tous les fichiers bien nommés. Il ne reste qu'à glisser son contenu dans le Drive.

## À compléter dans le dossier, puis régénérer

Modifier `sources/dossier.html`, puis lancer `sources/build_pdf.sh` (Chrome et pypdf).

- Section 07 : la latence d'inférence YOLO mesurée (`____ ms`).
- Section 11.3 : les tableaux du pentest croisé.
- Sections 06, 09 et 12 : les captures du dashboard et de Zabbix, les photos du boîtier et de la gravure (déposer les images dans `sources/img/` et remplacer les cadres pointillés `todo-box` par des `<img>`).

La présentation se régénère avec `sources/pptx/deck.js` (pptxgenjs), ou se modifie directement dans PowerPoint.

## Format de la soutenance

10 min d'oral, où chaque membre prend la parole et où la solution est démontrée, puis 15 min de questions. Le détail est dans `SCRIPT_ORAL.md`.
