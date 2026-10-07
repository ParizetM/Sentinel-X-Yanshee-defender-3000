"""
Détecteur d'anomalies Sentinel-X : deux modèles par capteur + décision en flux.

Pour chaque capteur (température, humidité, gaz) :
  - Isolation Forest (non supervisé) : appris sur du fonctionnement normal
    uniquement, il signale tout comportement inhabituel, y compris un
    incident jamais vu ;
  - Random Forest (supervisé) : appris sur des incidents simulés étiquetés
    par la vérité terrain, il reconnaît le type d'incident (fuite lente,
    fuite rapide, surchauffe, humidité) et reste formel quand l'incident
    est installé, là où l'Isolation Forest sature.

Indice de risque d'un capteur = max des deux modèles, normalisés pour que
  0 = seconde normale typique, 1 = seuil d'anomalie.
Les deux seuils sont appris sur des données normales de validation
(taux de faux positifs visé), jamais codés à la main sur une valeur.

AnomalyModel   : charge les modèles, calcule risque et diagnostic.
Decision       : anti-rebond (start / escalate / end), partagé avec evaluate.py.
StreamDetector : traite les messages MQTT un par un, par boîtier.
"""

from __future__ import annotations

import warnings
from collections import deque
from dataclasses import dataclass, field
from pathlib import Path
from typing import Deque, Dict, Optional

import joblib
import numpy as np
import pandas as pd
import sklearn

from features import BUFFER_S, FEATURE_INFO, FEATURES, GROUPS, WARMUP_S, LongReference, compute_features

DEFAULT_MODEL = Path(__file__).resolve().parent / "models" / "anomaly_model.joblib"

# Anti-rebond : il faut N secondes anormales d'affilée pour lever une alerte,
# et M secondes normales d'affilée pour la clore.
CONSECUTIVE_TO_RAISE = 8
CONSECUTIVE_TO_CLEAR = 20

ALERT_TYPES = {"temperature": "temperature_drift", "humidity": "humidity_drift", "gas": "gas_drift"}

# Diagnostics : ceux qui justifient le niveau « critical » dès leur détection
CRITICAL_DIAGNOSES = {"fuite_rapide"}
DIAGNOSIS_LABELS = {
    "surchauffe": "Surchauffe en cours",
    "fuite_lente": "Fuite de gaz lente",
    "fuite_rapide": "Fuite de gaz franche",
    "humidite": "Hausse d'humidité anormale",
    "anomalie_inconnue": "Comportement inhabituel",
}
DIAGNOSIS_SENSORS = {"surchauffe": "temperature", "fuite_lente": "gas", "fuite_rapide": "gas", "humidite": "humidity"}


class AnomalyModel:
    def __init__(self, bundle: dict) -> None:
        self.groups = bundle["groups"]
        self.meta = bundle.get("meta", {})
        if {g: m["features"] for g, m in self.groups.items()} != GROUPS:
            raise RuntimeError("Le modèle a été entraîné avec d'autres features : relancer train.py")

    @classmethod
    def load(cls, path: Path = DEFAULT_MODEL) -> "AnomalyModel":
        if not Path(path).is_file():
            raise RuntimeError(f"Modèle introuvable : {path} (lancer d'abord python train.py)")
        model = cls(joblib.load(path))
        trained_with = model.meta.get("sklearn")
        if trained_with and trained_with != sklearn.__version__:
            warnings.warn(f"Modèle entraîné avec scikit-learn {trained_with}, version installée "
                          f"{sklearn.__version__} : relancer python train.py sur cette machine (≈ 30 s)")
        return model

    def assess(self, feats: pd.DataFrame) -> pd.DataFrame:
        """
        Évalue chaque ligne de features. Colonnes produites, par capteur <g> :
          <g>_if (risque Isolation Forest), <g>_rf (probabilité d'incident Random Forest),
          <g>_class (type d'incident le plus probable), <g>_risk (max normalisé),
          <g>_critical ; puis la synthèse : risk, sensor, critical, diagnosis.
        Les lignes incomplètes (démarrage) restent à NaN.
        """
        out = pd.DataFrame(index=feats.index)
        for name, g in self.groups.items():
            X = feats[g["features"]]
            ok = X.notna().all(axis=1).to_numpy()
            if_risk = np.full(len(X), np.nan)
            rf_p = np.full(len(X), np.nan)
            rf_class = np.full(len(X), None, dtype=object)
            if ok.any():
                values = X.loc[ok].to_numpy()
                scores = g["if_model"].score_samples(values)
                if_risk[ok] = (g["if_median"] - scores) / (g["if_median"] - g["if_threshold"])
                proba = g["rf_model"].predict_proba(values)
                classes = list(g["rf_model"].classes_)
                normal = classes.index("normal")
                rf_p[ok] = 1.0 - proba[:, normal]
                incident = proba.copy()
                incident[:, normal] = -1
                rf_class[ok] = np.array(classes, dtype=object)[incident.argmax(axis=1)]
            rf_risk = rf_p / g["rf_threshold"]
            out[f"{name}_if"] = if_risk
            out[f"{name}_rf"] = rf_p
            out[f"{name}_class"] = rf_class
            out[f"{name}_risk"] = np.fmax(if_risk, rf_risk)
            out[f"{name}_critical"] = (if_risk >= g["if_critical_risk"]) | (
                (rf_risk >= 1.0) & np.isin(rf_class, list(CRITICAL_DIAGNOSES)))

        risk_cols = [f"{g}_risk" for g in self.groups]
        complete = out[risk_cols].notna().all(axis=1)
        out["risk"] = out[risk_cols].max(axis=1).where(complete)
        sensor = out[risk_cols].fillna(-1).to_numpy().argmax(axis=1)
        names = np.array(list(self.groups), dtype=object)
        out["sensor"] = np.where(complete, names[sensor], None)
        out["critical"] = False
        out["diagnosis"] = None
        for name in self.groups:
            mine = (out["sensor"] == name).to_numpy()
            out.loc[mine, "critical"] = out.loc[mine, f"{name}_critical"].astype(bool)
            rf_says = (out[f"{name}_rf"] / self.groups[name]["rf_threshold"]) >= 1.0
            diag = np.where(rf_says, out[f"{name}_class"], "anomalie_inconnue")
            out.loc[mine, "diagnosis"] = diag[mine]
        return out

    def explain(self, feats_row: pd.Series, assessed_row: pd.Series, diagnosis: Optional[str] = None) -> dict:
        """Ce qui a déclenché : capteur, diagnostic et feature la plus éloignée du normal."""
        diagnosis = diagnosis or assessed_row["diagnosis"]
        sensor = DIAGNOSIS_SENSORS.get(diagnosis, assessed_row["sensor"])
        g = self.groups[sensor]
        z = ((feats_row[g["features"]] - pd.Series(g["mean"])) / pd.Series(g["std"])).abs()
        feature = str(z.idxmax())
        _, label, fmt = FEATURE_INFO[feature]
        return {
            "sensor": sensor,
            "diagnosis": diagnosis,
            "diagnosis_label": DIAGNOSIS_LABELS.get(diagnosis, diagnosis),
            "rf_probability": round(float(assessed_row[f"{sensor}_rf"]), 3),
            "if_risk": round(float(assessed_row[f"{sensor}_if"]), 3),
            "feature": feature,
            "label": label,
            "value": round(float(feats_row[feature]), 3),
            "value_str": fmt.format(feats_row[feature]),
            "z": round(float(z[feature]), 1),
        }


class Decision:
    """
    Anti-rebond sur la suite des indices de risque d'un boîtier. Partagé par
    le service en direct et par evaluate.py, pour que l'évaluation mesure
    exactement ce que fera le service.

    Événements : "start" (alerte levée), "escalate" (passage en critical),
    "diagnosis" (le Random Forest confirme le type d'incident en cours
    d'alerte), "end" (retour à la normale).
    """

    def __init__(self, raise_n: int = CONSECUTIVE_TO_RAISE, clear_n: int = CONSECUTIVE_TO_CLEAR) -> None:
        self.raise_n = raise_n
        self.clear_n = clear_n
        self.bad = 0
        self.good = 0
        self.active = False
        self.level = "warning"
        self.diagnosis: Optional[str] = None
        self._candidate: Optional[str] = None
        self._candidate_n = 0

    def step(self, risk: float, critical: bool, diagnosis: Optional[str] = None) -> Optional[str]:
        """risk : indice max des capteurs. Renvoie le type d'événement ou None."""
        outlier = risk >= 1.0
        if outlier:
            self.bad, self.good = self.bad + 1, 0
        else:
            self.good, self.bad = self.good + 1, 0
        level = "critical" if (outlier and critical) else "warning"

        if not self.active:
            if outlier and self.bad >= self.raise_n:
                self.active, self.level, self.diagnosis = True, level, diagnosis
                self._candidate, self._candidate_n = None, 0
                return "start"
            return None

        # Diagnostic confirmé : même type d'incident connu pendant raise_n secondes
        confirmed = False
        if outlier and diagnosis not in (None, "anomalie_inconnue") and diagnosis != self.diagnosis:
            if diagnosis == self._candidate:
                self._candidate_n += 1
            else:
                self._candidate, self._candidate_n = diagnosis, 1
            if self._candidate_n >= self.raise_n:
                self.diagnosis, confirmed = diagnosis, True
                self._candidate, self._candidate_n = None, 0
        else:
            self._candidate, self._candidate_n = None, 0

        if level == "critical" and self.level != "critical":
            self.level = "critical"
            return "escalate"
        if confirmed:
            return "diagnosis"
        if self.good >= self.clear_n:
            self.active = False
            return "end"
        return None


def decide(assessed: pd.DataFrame, raise_n: int = CONSECUTIVE_TO_RAISE,
           clear_n: int = CONSECUTIVE_TO_CLEAR) -> pd.DataFrame:
    """Applique Decision à une série complète (hors ligne). Une ligne par événement."""
    decision = Decision(raise_n, clear_n)
    events = []
    for idx, risk, critical, sensor, diagnosis in zip(
            assessed.index, assessed["risk"], assessed["critical"], assessed["sensor"], assessed["diagnosis"]):
        if pd.isna(risk):
            continue
        kind = decision.step(float(risk), bool(critical), diagnosis)
        if kind:
            events.append({"index": idx, "kind": kind, "level": "info" if kind == "end" else decision.level,
                           "sensor": sensor, "diagnosis": decision.diagnosis, "risk": float(risk)})
    return pd.DataFrame(events, columns=["index", "kind", "level", "sensor", "diagnosis", "risk"])


@dataclass
class DeviceState:
    decision: Decision
    long_ref: LongReference = field(default_factory=LongReference)
    rows: Deque[dict] = field(default_factory=lambda: deque(maxlen=BUFFER_S + 30))
    last_uptime: Optional[int] = None
    started_uptime: Optional[int] = None
    peak_risk: float = 0.0
    explanation: Optional[dict] = None


class StreamDetector:
    def __init__(self, model: AnomalyModel,
                 consecutive_to_raise: int = CONSECUTIVE_TO_RAISE,
                 consecutive_to_clear: int = CONSECUTIVE_TO_CLEAR) -> None:
        self.model = model
        self.raise_n = consecutive_to_raise
        self.clear_n = consecutive_to_clear
        self.devices: Dict[str, DeviceState] = {}

    def _new_state(self) -> DeviceState:
        return DeviceState(Decision(self.raise_n, self.clear_n))

    def _features_last(self, state: DeviceState) -> Optional[pd.Series]:
        seg = pd.DataFrame(list(state.rows)).set_index("uptime_s").astype(float)
        full = range(int(seg.index.min()), int(seg.index.max()) + 1)
        seg = seg.reindex(full).ffill(limit=10)
        if len(seg) <= WARMUP_S:
            return None
        return compute_features(seg).iloc[-1]

    def update(self, record: dict) -> dict:
        """
        record : message à plat (common.flatten_record).
        Renvoie l'état courant et, si besoin, un événement à transformer en alerte.
        """
        device = record["device"]
        uptime = record.get("uptime_s")
        if device not in self.devices:
            self.devices[device] = self._new_state()
        state = self.devices[device]
        result = {"device": device, "uptime_s": uptime, "status": "warming_up",
                  "risk": None, "anomaly": False, "active": state.decision.active, "event": None}
        if uptime is None:
            return result
        uptime = int(uptime)

        if state.last_uptime is not None:
            if uptime < state.last_uptime - 10:
                # Reboot du boîtier : l'historique ne correspond plus
                self.devices[device] = state = self._new_state()
            elif uptime <= state.last_uptime:
                result["status"] = "duplicate"
                return result
        state.last_uptime = uptime
        row = {k: record.get(k) for k in ("uptime_s", "temperature", "humidity", "gas_raw", "gas_baseline")}
        row.update(state.long_ref.update(record))
        state.rows.append(row)

        feats = self._features_last(state)
        if feats is None or feats.isna().any():
            return result

        assessed = self.model.assess(feats.to_frame().T.astype(float)).iloc[0]
        risk = float(assessed["risk"])
        result.update(
            status="ok", risk=round(risk, 3), anomaly=risk >= 1.0,
            sensor=assessed["sensor"], diagnosis=assessed["diagnosis"] if risk >= 1.0 else None,
            risks={g: round(float(assessed[f"{g}_risk"]), 3) for g in self.model.groups},
            features=feats[FEATURES].round(3).to_dict(),
        )

        kind = state.decision.step(risk, bool(assessed["critical"]), assessed["diagnosis"])
        if state.decision.active:
            state.peak_risk = max(state.peak_risk, risk)
        if kind in ("start", "escalate", "diagnosis"):
            if kind == "start":
                state.started_uptime, state.peak_risk = uptime, risk
            state.explanation = self.model.explain(feats, assessed, state.decision.diagnosis)
            result["event"] = self._event(kind, device, uptime, risk, state.decision.level, state.explanation)
        elif kind == "end":
            event = self._event("end", device, uptime, risk, "info", state.explanation)
            event["duration_s"] = uptime - (state.started_uptime or uptime)
            event["peak_risk"] = round(state.peak_risk, 3)
            result["event"] = event
            state.explanation = None

        result["active"] = state.decision.active
        result["level"] = state.decision.level if state.decision.active else None
        if state.explanation:
            result["explanation"] = state.explanation
        return result

    @staticmethod
    def _event(kind: str, device: str, uptime: int, risk: float, level: str, expl: dict) -> dict:
        return {
            "kind": kind,
            "device": device,
            "uptime_s": uptime,
            "risk": round(risk, 3),
            "level": level,
            "alert_type": ALERT_TYPES[expl["sensor"]],
            "explanation": expl,
        }
