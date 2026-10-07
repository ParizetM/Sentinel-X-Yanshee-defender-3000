"""Tests unitaires pour les alertes (KAN-32 - POST /api/v1/alerts)."""

import pytest
from httpx import AsyncClient


@pytest.mark.asyncio
async def test_create_alert_success(client: AsyncClient):
    payload = {
        "source": "sensor_esp8266",
        "device_id": "sentinel-01",
        "alert_type": "gas_leak",
        "severity": "critical",
        "value": 480.5,
        "message": "Seuil critique de gaz MQ-2 dépassé",
        "metadata": {"raw": 480, "baseline": 150}
    }

    response = await client.post("/api/v1/alerts", json=payload)
    assert response.status_code == 201
    data = response.json()
    assert data["id"] is not None
    assert data["source"] == "sensor_esp8266"
    assert data["severity"] == "critical"
    assert data["acknowledged"] is False


@pytest.mark.asyncio
async def test_create_alert_invalid_schema(client: AsyncClient):
    # Manque des champs obligatoires (message, severity)
    payload = {
        "source": "sensor_esp8266",
        "device_id": "sentinel-01"
    }

    response = await client.post("/api/v1/alerts", json=payload)
    assert response.status_code == 422
    data = response.json()
    assert "error" in data


@pytest.mark.asyncio
async def test_get_alerts_list(client: AsyncClient):
    # Création d'une alerte
    payload = {
        "source": "ia_vision",
        "device_id": "sentinel-01",
        "alert_type": "human_intrusion",
        "severity": "high",
        "message": "Intrusion détectée par la caméra"
    }
    await client.post("/api/v1/alerts", json=payload)

    response = await client.get("/api/v1/alerts")
    assert response.status_code == 200
    data = response.json()
    assert len(data) >= 1
    assert data[0]["alert_type"] == "human_intrusion"


@pytest.mark.asyncio
async def test_acknowledge_alert_requires_auth(client: AsyncClient):
    # Création d'une alerte d'abord
    res_create = await client.post("/api/v1/alerts", json={
        "source": "ia_vision",
        "device_id": "sentinel-01",
        "alert_type": "test",
        "severity": "low",
        "message": "Test message"
    })
    alert_id = res_create.json()["id"]

    # Tentative sans token -> 401
    res_unauth = await client.put(f"/api/v1/alerts/{alert_id}/acknowledge", json={"acknowledged_by": "martin"})
    assert res_unauth.status_code == 401

    # Tentative avec token valide -> 200
    res_auth = await client.put(
        f"/api/v1/alerts/{alert_id}/acknowledge",
        json={"acknowledged_by": "martin"},
        headers={"Authorization": "Bearer sentinel-x-secret-key-2026"}
    )
    assert res_auth.status_code == 200
    assert res_auth.json()["acknowledged"] is True
    assert res_auth.json()["acknowledged_by"] == "martin"
