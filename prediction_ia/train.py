"""
Entraînement des modèles de maintenance prédictive (un couple par capteur).

  Isolation Forest : appris UNIQUEMENT sur du fonctionnement normal.
  Random Forest    : appris sur normal + incidents simulés, étiquetés par la
                     vérité terrain du simulateur (effet réel de l'incident).

Données :
  - enregistrements réels SANS manipulation (data/normal_*.jsonl par défaut),
    étiquetés « normal » ;
  - heures de fonctionnement normal simulé et scénarios d'incident
    (simulate.py, calibré sur le bruit réel des capteurs).

Seuils : fixés sur des données normales de validation jamais vues à
l'entraînement, au quantile qui donne le taux de faux positifs visé
(--fp-rate, par seconde et par capteur).

Exemples :
  python train.py
  python train.py --real data/normal_salle.jsonl
"""

from __future__ import annotations

import argparse
import glob
from datetime import datetime, timezone
from pathlib import Path

import joblib
import numpy as np
import pandas as pd
import sklearn
from sklearn.ensemble import IsolationForest, RandomForestClassifier
from sklearn.metrics import classification_report

from common import SCRIPT_DIR, load_jsonl, split_segments
from detector import DEFAULT_MODEL
from features import GROUPS, compute_features
from simulate import simulate

INCIDENTS = ("surchauffe", "fuite_lente", "fuite_rapide", "humidite", "demo")
LABEL_COLUMNS = {g: f"label_{g}" for g in GROUPS}

TRAIN_SEED = 1000
VALID_SEED = 5000
CRITICAL_MARGIN = 1.2   # « critical » : 20 % plus anormal que toute seconde normale de validation
ROW_STEP = 2            # une seconde sur deux suffit (secondes voisines quasi identiques)


def labelled(feats: pd.DataFrame, labels: pd.DataFrame) -> pd.DataFrame:
    return feats.join(labels).dropna(subset=list(feats.columns))


def real_sessions(paths, valid_ratio: float):
    """Enregistrements réels normaux → (train, validation), fin de chaque série en validation."""
    train, valid = [], []
    if not paths:
        return train, valid
    for seg in split_segments(load_jsonl(paths)):
        feats = compute_features(seg)
        labels = pd.DataFrame({c: "normal" for c in LABEL_COLUMNS.values()}, index=seg.index)
        data = labelled(feats, labels)
        cut = int(len(data) * (1 - valid_ratio))
        train.append(data.iloc[:cut])
        valid.append(data.iloc[cut:])
    return train, valid


def sim_session(seed: int, scenario: str, minutes: int) -> pd.DataFrame:
    rng = np.random.default_rng(seed)
    duration = minutes * 60
    onset = end = None
    if scenario != "normal":
        onset = int(rng.uniform(0.2, 0.4) * duration)
        # Une fois sur deux l'incident s'arrête : le modèle voit aussi le retour à la normale
        if rng.random() < 0.5:
            end = onset + int(rng.uniform(120, 900))
    sim = simulate(duration, seed=seed, scenario=scenario, onset_s=onset, end_s=end).set_index("uptime_s")
    return labelled(compute_features(sim), sim[list(LABEL_COLUMNS.values())])


def sim_sessions(seed_base: int, normal_hours: float, incident_sessions: int):
    normal = [sim_session(seed_base + i, "normal", 60) for i in range(max(1, int(round(normal_hours))))]
    incidents = []
    for k, scenario in enumerate(INCIDENTS):
        for i in range(incident_sessions):
            incidents.append(sim_session(seed_base + 10_000 * (k + 1) + i, scenario, 40))
    return normal, incidents


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--real", nargs="*", default=None,
                        help="enregistrements normaux réels (défaut : data/normal_*.jsonl)")
    parser.add_argument("--synthetic-hours", type=float, default=24, help="heures de normal simulé")
    parser.add_argument("--incident-sessions", type=int, default=24, help="sessions simulées par type d'incident")
    parser.add_argument("--fp-rate", type=float, default=0.0005,
                        help="part des secondes normales de validation au-dessus du seuil (défaut 0,05 %%)")
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--out", type=Path, default=DEFAULT_MODEL)
    args = parser.parse_args()

    real_paths = args.real if args.real is not None else sorted(glob.glob(str(SCRIPT_DIR / "data" / "normal_*.jsonl")))
    real_train, real_valid = real_sessions([Path(p) for p in real_paths], valid_ratio=0.2)
    real_rows = sum(len(f) for f in real_train)
    print(f"Réel normal      : {len(real_paths)} fichier(s), {real_rows} s (+ {sum(len(f) for f in real_valid)} s validation)")

    sim_normal, sim_incidents = sim_sessions(TRAIN_SEED, args.synthetic_hours, args.incident_sessions)
    val_normal, val_incidents = sim_sessions(VALID_SEED, max(8, args.synthetic_hours / 3), max(4, args.incident_sessions // 4))
    print(f"Simulé normal    : {sum(len(f) for f in sim_normal)} s, incidents : {sum(len(f) for f in sim_incidents)} s")

    # Les secondes réelles pèsent jusqu'à 30 % du normal (sur-échantillonnées si besoin)
    normal_train = pd.concat(sim_normal + real_train)
    if real_rows:
        target = int(0.3 * len(normal_train))
        if real_rows < target:
            extra = pd.concat(real_train).sample(target - real_rows, replace=True, random_state=args.seed)
            normal_train = pd.concat([normal_train, extra])
    all_train = pd.concat([normal_train, *sim_incidents]).iloc[::ROW_STEP]
    normal_valid = pd.concat(val_normal + real_valid)
    incident_valid = pd.concat(val_incidents)

    groups = {}
    for name, feats in GROUPS.items():
        label = LABEL_COLUMNS[name]

        iso = IsolationForest(n_estimators=200, max_samples=256, random_state=args.seed, n_jobs=-1)
        iso.fit(normal_train[feats].to_numpy())
        iso.n_jobs = 1
        scores = iso.score_samples(normal_valid[feats].to_numpy())
        if_median = float(np.median(scores))
        if_threshold = float(np.quantile(scores, args.fp_rate))
        if_critical = (if_median - float(scores.min())) / (if_median - if_threshold) * CRITICAL_MARGIN

        rf = RandomForestClassifier(n_estimators=100, max_depth=8, min_samples_leaf=20,
                                    class_weight="balanced_subsample", random_state=args.seed, n_jobs=-1)
        rf.fit(all_train[feats].to_numpy(), all_train[label].to_numpy())
        rf.n_jobs = 1
        normal_idx = list(rf.classes_).index("normal")
        p_normal_valid = 1 - rf.predict_proba(normal_valid[feats].to_numpy())[:, normal_idx]
        rf_threshold = float(max(0.5, np.quantile(p_normal_valid, 1 - args.fp_rate)))

        groups[name] = {
            "features": feats,
            "if_model": iso,
            "if_median": if_median,
            "if_threshold": if_threshold,
            "if_critical_risk": float(if_critical),
            "rf_model": rf,
            "rf_threshold": rf_threshold,
            "mean": normal_train[feats].mean().to_dict(),
            "std": normal_train[feats].std().clip(lower=1e-3).to_dict(),
        }

        # Rapport du Random Forest sur des incidents de validation jamais vus
        proba = rf.predict_proba(incident_valid[feats].to_numpy())
        incident_p = 1 - proba[:, normal_idx]
        masked = proba.copy()
        masked[:, normal_idx] = -1
        pred = np.where(incident_p >= rf_threshold, rf.classes_[masked.argmax(axis=1)], "normal")
        print(f"\n[{name}] Isolation Forest : seuil {if_threshold:.3f}, critique ≥ {if_critical:.2f} "
              f"| Random Forest : seuil p ≥ {rf_threshold:.2f}")
        print(classification_report(incident_valid[label], pred, digits=3, zero_division=0))

    bundle = {
        "groups": groups,
        "meta": {
            "trained_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
            "sklearn": sklearn.__version__,
            "real_files": [Path(p).name for p in real_paths],
            "real_seconds": int(real_rows),
            "synthetic_normal_seconds": int(sum(len(f) for f in sim_normal)),
            "synthetic_incident_seconds": int(sum(len(f) for f in sim_incidents)),
            "fp_rate": args.fp_rate,
        },
    }
    args.out.parent.mkdir(parents=True, exist_ok=True)
    joblib.dump(bundle, args.out, compress=3)
    print(f"Modèle sauvegardé : {args.out} ({args.out.stat().st_size / 1e6:.1f} Mo)")


if __name__ == "__main__":
    main()
