"""Tests du pipeline de maintenance prédictive (lancer : python -m pytest tests)."""

import sys
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from anomaly_service import build_alert  # noqa: E402
from common import flatten_record, split_segments  # noqa: E402
from detector import DEFAULT_MODEL, AnomalyModel, Decision, StreamDetector  # noqa: E402
from features import FEATURES, compute_features  # noqa: E402
from firmware_gas import FirmwareGas  # noqa: E402
from simulate import simulate, to_message  # noqa: E402

needs_model = pytest.mark.skipif(not DEFAULT_MODEL.is_file(), reason="lancer python train.py d'abord")


# --- Firmware ---------------------------------------------------------------

def run_firmware(levels_per_second):
    gas = FirmwareGas()
    out = []
    for t, level in enumerate(levels_per_second):
        for _ in range(10):
            gas.sample(level)
        gas.update(warmed_up=t >= 60)
        out.append(gas.level)
    return out


def test_firmware_detects_fast_leak():
    levels = run_firmware([300] * 120 + [700] * 30)
    assert levels[100] == "normal"
    assert levels[-1] == "alerte"


def test_firmware_absorbs_slow_leak():
    # +12/min pendant 20 min : la référence suit, le firmware ne voit jamais rien
    levels = run_firmware([300] * 120 + [300 + 0.2 * t for t in range(1200)])
    assert set(levels[60:]) == {"normal"}


# --- Données ----------------------------------------------------------------

def test_flatten_record_firmware_format():
    rec = flatten_record({"device": "esp-01", "uptime_s": 10, "temperature": 26.0, "humidity": None,
                          "gas": {"raw": 273, "baseline": None, "level": "chauffe"}, "presence": True})
    assert rec["gas_raw"] == 273.0 and rec["gas_baseline"] is None and rec["humidity"] is None
    assert rec["presence"] is True


def test_split_segments_reboot_and_duplicates():
    rows = [{"device": "esp-01", "uptime_s": u, "temperature": 20.0, "humidity": 40.0, "gas_raw": 300.0,
             "gas_baseline": 300.0, "gas_level": "normal", "source_file": "f"}
            for u in [100, 101, 103, 102, 103, 104, 5, 6, 7]]
    segs = split_segments(pd.DataFrame(rows))
    assert [list(s.index) for s in segs] == [[100, 101, 102, 103, 104], [5, 6, 7]]


# --- Features : direct == entraînement --------------------------------------

@needs_model
def test_stream_features_match_batch():
    df = simulate(500, seed=3, scenario="fuite_lente", onset_s=200)
    batch = compute_features(df.set_index("uptime_s"))
    detector = StreamDetector(AnomalyModel.load())
    for row in df.to_dict("records"):
        detector.update(flatten_record(to_message(row)))
    state = detector.devices["esp-sim"]
    live = detector._features_last(state)
    np.testing.assert_allclose(live[FEATURES].to_numpy(float), batch.iloc[-1][FEATURES].to_numpy(float), rtol=1e-6)


# --- Décision -----------------------------------------------------------------

def test_decision_debounce_and_end():
    d = Decision(raise_n=3, clear_n=4)
    kinds = [d.step(r, False) for r in [1.5, 1.5, 0.2, 1.5, 1.5, 1.5, 1.2, 0.1, 0.1, 0.1, 0.1]]
    assert kinds[:5] == [None] * 5            # un retour sous le seuil remet le compteur à zéro
    assert kinds[5] == "start"
    assert kinds[-1] == "end"


def test_decision_escalate_and_diagnosis():
    d = Decision(raise_n=2, clear_n=5)
    assert d.step(1.2, False, "anomalie_inconnue") is None
    assert d.step(1.2, False, "anomalie_inconnue") == "start"
    assert d.step(1.3, False, "fuite_lente") is None
    assert d.step(1.3, False, "fuite_lente") == "diagnosis"
    assert d.diagnosis == "fuite_lente"
    assert d.step(1.9, True, "fuite_lente") == "escalate"
    assert d.level == "critical"


# --- Bout en bout -------------------------------------------------------------

def stream(df):
    detector = StreamDetector(AnomalyModel.load())
    return [r for r in (detector.update(flatten_record(to_message(row))) for row in df.to_dict("records"))
            if r["event"]]


@needs_model
def test_end_to_end_slow_leak_detected_before_firmware():
    df = simulate(900, seed=11, scenario="fuite_lente", onset_s=300)
    events = stream(df)
    starts = [r["event"] for r in events if r["event"]["kind"] == "start"]
    assert starts, "fuite lente non détectée"
    assert starts[0]["uptime_s"] - df["uptime_s"].iloc[300] < 300
    assert starts[0]["alert_type"] == "gas_drift"
    assert set(df["gas_level"]) == {"normal"}   # le firmware, lui, n'a rien vu


@needs_model
def test_end_to_end_quiet_on_normal():
    events = stream(simulate(900, seed=12345, scenario="normal"))
    assert not [r for r in events if r["event"]["kind"] == "start"]


@needs_model
def test_alert_matches_api_schema():
    df = simulate(400, seed=5, scenario="fuite_rapide", onset_s=200)
    event = next(r["event"] for r in stream(df) if r["event"]["kind"] == "start")
    alert = build_alert(event)
    assert alert["source"] == "ia_anomaly"
    assert alert["level"] in {"warning", "critical"}
    assert alert["device_id"] == "esp-sim" and alert["message"]
    assert alert["payload"]["diagnosis"] in {"fuite_rapide", "anomalie_inconnue"}
