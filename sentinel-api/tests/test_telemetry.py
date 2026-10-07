"""Tests unitaires pour la télémétrie capteurs (KAN-31, KAN-33)."""

import pytest
from httpx import AsyncClient


@pytest.mark.asyncio
async def test_ingest_and_get_telemetry(client: AsyncClient):
    payload = {
        "device": "sentinel-01",
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
    latest_res = await client.get("/api/v1/telemetry/latest?device_id=sentinel-01")
    assert latest_res.status_code == 200
    assert latest_res.json()["device_id"] == "sentinel-01"
    assert latest_res.json()["presence"] is True

    # Consultation historique
    hist_res = await client.get("/api/v1/telemetry/history?device_id=sentinel-01&limit=10")
    assert hist_res.status_code == 200
    assert len(hist_res.json()) >= 1
