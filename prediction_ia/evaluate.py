"""
Évaluation du détecteur : génère reports/evaluation.md, metrics.json et les graphiques.

Mesure exactement ce que fera le service (mêmes features, mêmes modèles,
même anti-rebond), sur des données jamais vues à l'entraînement :

  1. Fausses alertes : heures de fonctionnement normal simulé.
  2. Scénarios d'incident (plusieurs tirages chacun) : délai de détection,
     diagnostic, comparaison au firmware et avance sur le seuil critique
     (40 °C ou +150 de gaz réel au-dessus de l'air propre).
  3. Enregistrements réels (telemetry.jsonl, data/*.jsonl) : chronologie des
     alertes IA face aux niveaux du firmware.

Exemple :
  python evaluate.py
  python evaluate.py --runs 20 --normal-hours 48
"""

from __future__ import annotations

import argparse
import glob
import json
from pathlib import Path
from typing import List, Optional

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402

from common import SCRIPT_DIR, load_jsonl, split_segments  # noqa: E402
from detector import DIAGNOSIS_LABELS, AnomalyModel, decide  # noqa: E402
from features import compute_features  # noqa: E402
from simulate import CRITICAL_GAS_EXCESS, CRITICAL_TEMP, simulate  # noqa: E402

REPORT_DIR = SCRIPT_DIR / "reports"
SCENARIOS = {
    "surchauffe": "Surchauffe lente (+0,3 à 0,8 °C/min)",
    "fuite_lente": "Fuite de gaz lente (+5 à 20 /min)",
    "fuite_rapide": "Fuite de gaz franche (+150 à 700 en quelques s)",
    "humidite": "Hausse d'humidité (+6 à 35 %)",
    "demo": "Scénario de démo : chauffe lente + micro-dérive de gaz",
}
EVAL_SEED = 20_000      # graines jamais utilisées par train.py
ONSET_S = 600
DURATION_S = 2700


def run(model: AnomalyModel, df: pd.DataFrame):
    feats = compute_features(df)
    assessed = model.assess(feats)
    return feats, assessed, decide(assessed)


def first(index: pd.Index) -> Optional[int]:
    return int(index[0]) if len(index) else None


def evaluate_normal(model: AnomalyModel, hours: int) -> dict:
    alerts: List[dict] = []
    seconds = 0
    for i in range(hours):
        df = simulate(3600, seed=EVAL_SEED + i, scenario="normal")
        _, assessed, events = run(model, df)
        seconds += int(assessed["risk"].notna().sum())
        for _, e in events[events["kind"] == "start"].iterrows():
            alerts.append({"hour": i, "t": int(e["index"]), "sensor": e["sensor"], "diagnosis": e["diagnosis"]})
    return {"hours": seconds / 3600, "false_alerts": len(alerts),
            "false_alerts_per_hour": len(alerts) / (seconds / 3600), "alerts": alerts}


def evaluate_scenario(model: AnomalyModel, name: str, runs: int):
    rows, example = [], None
    for i in range(runs):
        df = simulate(DURATION_S, seed=EVAL_SEED + 1000 * (list(SCENARIOS).index(name) + 1) + i,
                      scenario=name, onset_s=ONSET_S)
        feats, assessed, events = run(model, df)
        starts = events[events["kind"] == "start"]
        after = starts[starts["index"] >= ONSET_S]
        detected = int(after["index"].iloc[0]) if len(after) else None
        diag_events = events[(events["index"] >= ONSET_S) & events["kind"].isin(["start", "diagnosis"])]
        known = diag_events[diag_events["diagnosis"].isin(list(DIAGNOSIS_LABELS)[:-1])]
        critical_level = events[(events["index"] >= ONSET_S) & (events["level"] == "critical")]
        firmware = first(df.index[(df.index >= ONSET_S) & df["gas_level"].isin(["eleve", "alerte"])])
        critical = first(df.index[df["critical"]])
        rows.append({
            "run": i,
            "false_alert_before": int((starts["index"] < ONSET_S).sum()),
            "ia_delay_s": None if detected is None else detected - ONSET_S,
            "diagnosis": known["diagnosis"].iloc[0] if len(known) else (after["diagnosis"].iloc[0] if len(after) else None),
            "diagnosis_delay_s": None if not len(known) else int(known["index"].iloc[0]) - ONSET_S,
            "critical_level_delay_s": None if not len(critical_level) else int(critical_level["index"].iloc[0]) - ONSET_S,
            "firmware_delay_s": None if firmware is None else firmware - ONSET_S,
            "critical_reached_s": None if critical is None else critical - ONSET_S,
            "lead_vs_critical_s": None if (critical is None or detected is None) else critical - detected,
            "flagged_after_onset": round(float((assessed["risk"].iloc[ONSET_S:] >= 1).mean()), 3),
        })
        if example is None:
            example = (df, feats, assessed, events)
    return pd.DataFrame(rows), example


def evaluate_real(model: AnomalyModel, paths: List[Path]):
    results = []
    for seg in split_segments(load_jsonl(paths)):
        if len(seg) < 120:
            continue
        feats, assessed, events = run(model, seg)
        t0 = int(seg.index[0])
        fw = seg["gas_level"].fillna("normal")
        transitions = fw[fw.ne(fw.shift())]
        results.append({
            "file": str(seg["source_file"].iloc[0]),
            "device": str(seg["device"].iloc[0]),
            "duration_s": len(seg),
            "seg": seg, "assessed": assessed, "events": events,
            "firmware": [(int(i) - t0, lvl) for i, lvl in transitions.items()],
            "t0": t0,
        })
    return results


def plot_timeline(path: Path, title: str, df: pd.DataFrame, assessed: pd.DataFrame, events: pd.DataFrame,
                  t0: int = 0, onset: Optional[int] = None) -> None:
    t = (df.index - t0) / 60
    fig, axes = plt.subplots(4, 1, figsize=(11, 9), sharex=True, gridspec_kw={"height_ratios": [1, 1, 1, 1.2]})
    axes[0].plot(t, df["temperature"], color="#c0392b", lw=1.2)
    axes[0].set_ylabel("Temp. (°C)")
    axes[1].plot(t, df["humidity"], color="#2980b9", lw=1.2)
    axes[1].set_ylabel("Humidité (%)")
    axes[2].plot(t, df["gas_raw"], color="#7f8c8d", lw=1.2, label="gaz (raw)")
    if "gas_baseline" in df:
        axes[2].plot(t, df["gas_baseline"], color="#16a085", lw=1, ls="--", label="référence firmware")
    fw_alert = df["gas_level"].isin(["eleve", "alerte"]).to_numpy()
    if fw_alert.any():
        axes[2].fill_between(t, 0, 1, where=fw_alert, color="#e67e22", alpha=0.25,
                             transform=axes[2].get_xaxis_transform(), label="firmware eleve/alerte")
    axes[2].set_ylabel("Gaz MQ-135")
    axes[2].legend(loc="upper left", fontsize=8)
    for sensor, color in (("temperature", "#c0392b"), ("humidity", "#2980b9"), ("gas", "#7f8c8d")):
        axes[3].plot(t, assessed[f"{sensor}_risk"].clip(upper=2.2), color=color, lw=1, label=f"risque {sensor}")
    axes[3].axhline(1.0, color="black", lw=0.8, ls=":")
    axes[3].text(t[0], 1.03, "seuil d'anomalie", fontsize=7)
    axes[3].set_ylabel("Indice de risque IA")
    axes[3].set_xlabel("Temps (min)")
    axes[3].legend(loc="upper left", fontsize=8)
    for _, e in events.iterrows():
        x = (e["index"] - t0) / 60
        color = {"start": "#e74c3c", "escalate": "#8e44ad", "diagnosis": "#27ae60", "end": "#2ecc71"}[e["kind"]]
        for ax in axes:
            ax.axvline(x, color=color, lw=1, alpha=0.7)
        label = e["kind"] if e["kind"] == "end" else f'{e["kind"]}: {e["diagnosis"]}'
        axes[3].text(x, 2.05, label, rotation=90, fontsize=7, va="top", ha="right", color=color)
    if onset is not None:
        for ax in axes:
            ax.axvline((onset - t0) / 60, color="black", lw=1.2, ls="--")
        axes[0].text((onset - t0) / 60, axes[0].get_ylim()[1], " début incident", fontsize=8, va="top")
    fig.suptitle(title)
    fig.tight_layout()
    fig.savefig(path, dpi=110)
    plt.close(fig)


def fmt(value, suffix=" s") -> str:
    if value is None or (isinstance(value, float) and np.isnan(value)):
        return "—"
    return f"{value:.0f}{suffix}"


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--runs", type=int, default=10, help="tirages par scénario")
    parser.add_argument("--normal-hours", type=int, default=24)
    parser.add_argument("--real", nargs="*", default=None, help="enregistrements réels à rejouer")
    args = parser.parse_args()

    REPORT_DIR.mkdir(exist_ok=True)
    model = AnomalyModel.load()
    meta = model.meta
    metrics = {"model": meta}
    md = ["# Évaluation du détecteur d'anomalies Sentinel-X", "",
          f"Modèle entraîné le {meta.get('trained_at')} : "
          f"{meta.get('real_seconds', 0) / 3600:.1f} h réelles, "
          f"{meta.get('synthetic_normal_seconds', 0) / 3600:.0f} h de normal simulé, "
          f"{meta.get('synthetic_incident_seconds', 0) / 3600:.0f} h d'incidents simulés.",
          "Toutes les données ci-dessous sont **inédites** pour le modèle (graines de simulation distinctes).", ""]

    print("Fausses alertes ...")
    normal = evaluate_normal(model, args.normal_hours)
    metrics["normal"] = normal
    md += ["## 1. Fausses alertes en fonctionnement normal", "",
           f"- {normal['hours']:.1f} h de fonctionnement normal simulé (dérives de la pièce, passages près du boîtier)",
           f"- **{normal['false_alerts']} fausse(s) alerte(s), soit {normal['false_alerts_per_hour']:.2f} par heure**",
           f"- Probabilité d'une fausse alerte pendant une démo de 5 min : "
           f"{(1 - np.exp(-normal['false_alerts_per_hour'] * 5 / 60)):.1%}", ""]

    md += ["## 2. Scénarios d'incident", "",
           f"Chaque scénario est tiré {args.runs} fois (pièce, bruit et intensité différents). "
           f"L'incident commence à t = {ONSET_S} s. Valeurs : médiane [min – max].", "",
           "| Scénario | Détection IA | Diagnostic correct | Firmware (eleve/alerte) | Seuil critique atteint | Avance de l'IA sur le seuil |",
           "|---|---|---|---|---|---|"]
    metrics["scenarios"] = {}
    for name, label in SCENARIOS.items():
        print(f"Scénario {name} ...")
        table, (df, feats, assessed, events) = evaluate_scenario(model, name, args.runs)
        metrics["scenarios"][name] = table.to_dict("records")
        table.to_csv(REPORT_DIR / f"scenario_{name}.csv", index=False)

        def stat(col, suffix=" s"):
            s = table[col].dropna()
            if s.empty:
                return "jamais"
            return f"{s.median():.0f}{suffix} [{s.min():.0f} – {s.max():.0f}]"

        expected = {"demo": {"surchauffe", "fuite_lente"}}.get(name, {name})
        correct = table["diagnosis"].isin(expected).sum()
        fw_seen = table["firmware_delay_s"].notna().sum()
        md.append(f"| {label} | {stat('ia_delay_s')} ({table['ia_delay_s'].notna().sum()}/{len(table)}) "
                  f"| {correct}/{len(table)} | {stat('firmware_delay_s') if fw_seen else 'jamais'} ({fw_seen}/{len(table)}) "
                  f"| {stat('critical_reached_s')} | {stat('lead_vs_critical_s')} |")
        plot_timeline(REPORT_DIR / f"scenario_{name}.png", label, df, assessed, events, t0=0, onset=ONSET_S)

    md += ["",
           f"Seuil critique de référence (jamais utilisé pour détecter) : température ≥ {CRITICAL_TEMP:.0f} °C, "
           f"ou concentration réelle ≥ +{CRITICAL_GAS_EXCESS:.0f} au-dessus de l'air propre (seuil « eleve » du "
           "firmware appliqué à la vraie concentration). « jamais » : non atteint pendant les "
           f"{(DURATION_S - ONSET_S) // 60} min simulées.", "",
           "Graphiques : `reports/scenario_<nom>.png`. Détail par tirage : `reports/scenario_<nom>.csv`.", ""]

    real_paths = args.real if args.real is not None else (
        [str(SCRIPT_DIR / "telemetry.jsonl")] + sorted(glob.glob(str(SCRIPT_DIR / "data" / "*.jsonl"))))
    real_paths = [Path(p) for p in real_paths if Path(p).is_file() and not Path(p).name.startswith("sim_")]
    if real_paths:
        print("Enregistrements réels ...")
        md += ["## 3. Enregistrements réels", ""]
        metrics["real"] = []
        for k, res in enumerate(evaluate_real(model, real_paths)):
            ev = res["events"]
            png = f"real_{k}_{Path(res['file']).stem}.png"
            plot_timeline(REPORT_DIR / png, f"{res['file']} ({res['device']}, {res['duration_s'] // 60} min)",
                          res["seg"], res["assessed"], ev, t0=res["t0"])
            md += [f"### {res['file']} — {res['device']}, {res['duration_s'] // 60} min {res['duration_s'] % 60} s", "",
                   "| t (s) | Événement IA | Niveau | Capteur | Diagnostic |", "|---|---|---|---|---|"]
            for _, e in ev.iterrows():
                md.append(f"| {int(e['index']) - res['t0']} | {e['kind']} | {e['level']} | {e['sensor']} "
                          f"| {DIAGNOSIS_LABELS.get(e['diagnosis'], e['diagnosis'])} |")
            fw = ", ".join(f"{t} s → {lvl}" for t, lvl in res["firmware"])
            md += ["", f"Firmware : {fw}", "", f"![{res['file']}]({png})", ""]
            metrics["real"].append({"file": res["file"], "device": res["device"], "duration_s": res["duration_s"],
                                    "events": ev.assign(t=ev["index"] - res["t0"]).to_dict("records"),
                                    "firmware": res["firmware"]})

    (REPORT_DIR / "evaluation.md").write_text("\n".join(md) + "\n", encoding="utf-8")
    (REPORT_DIR / "metrics.json").write_text(json.dumps(metrics, indent=2, default=str, ensure_ascii=False),
                                             encoding="utf-8")
    print(f"Rapport : {REPORT_DIR / 'evaluation.md'}")


if __name__ == "__main__":
    main()
