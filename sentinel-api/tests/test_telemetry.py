"""Tests unitaires pour les mesures et la télémétrie capteurs (Contrat §4.4, KAN-31, KAN-33)."""

import pytest
from httpx import AsyncClient


@pytest.mark.asyncio
async def test_ingest_and_get_telemetry_and_measurements(client: AsyncClient):
    payload = {
        "device": "esp-01",
        "uptime_s": 240,
        "temperature": 21.5,
        "humidity": 48.0,
        "gas": {
            "raw": 280,
            "baseline": 250,
            "level": "normal"
        },
        "presence": True,
        "rssi": -62,
        "actuators": {
            "buzzer": "off",
            "led": "off"
        }
    }

    # Ingestion
    post_res = await client.post("/api/v1/telemetry", json=payload)
    assert post_res.status_code == 201
    assert post_res.json()["temperature"] == 21.5

    # Consultation dernière mesure
    latest_res = await client.get("/api/v1/telemetry/latest?device_id=esp-01")
    assert latest_res.status_code == 200
    assert latest_res.json()["device_id"] == "esp-01"
    assert latest_res.json()["presence"] is True

    # Consultation endpoint officiel du contrat §4.4 : /api/v1/measurements
    meas_res = await client.get("/api/v1/measurements?device_id=esp-01&limit=10")
    assert meas_res.status_code == 200
    data = meas_res.json()
    assert len(data) >= 1
    # Vérification présence des clés pour le Dashboard React (time, temp, pir)
    assert "temp" in data[0]
    assert "pir" in data[0]
    assert "time" in data[0]
