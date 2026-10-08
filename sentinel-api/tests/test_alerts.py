"""Tests unitaires pour les alertes (Contrat §4.4, §4.5 & KAN-32 : POST /api/v1/alerts)."""

import pytest
from httpx import AsyncClient


@pytest.mark.asyncio
async def test_create_alert_standard_contract(client: AsyncClient):
    """Vérifie la création selon le contrat exact du README §4.5."""
    payload = {
        "device_id": "esp-01",
        "ts": "2026-10-07T10:15:30Z",
        "source": "sensor",
        "level": "alert",
        "message": "Seuil de gaz critique franchi",
        "payload": {"raw": 480, "baseline": 150}
    }

    response = await client.post("/api/v1/alerts", json=payload)
    assert response.status_code == 201
    data = response.json()
    assert data["id"] is not None
    assert data["device_id"] == "esp-01"
    assert data["level"] == "alert"
    assert data["source"] == "sensor"
    assert data["payload"]["raw"] == 480


@pytest.mark.asyncio
async def test_create_alert_from_sensor_state_change(client: AsyncClient):
    """Vérifie l'ingestion d'un changement d'état capteur brut (sujet national)."""
    payload = {
        "device": "esp-01",
        "sensor": "gas",
        "state": "alerte",
        "value": 312
    }

    response = await client.post("/api/v1/alerts", json=payload)
    assert response.status_code == 201
    data = response.json()
    assert data["device_id"] == "esp-01"
    assert data["level"] == "alert"
    assert "gas" in data["alert_type"]
    assert data["value"] == 312


@pytest.mark.asyncio
async def test_create_alert_from_ia_vision(client: AsyncClient):
    """Vérifie l'ingestion d'une alerte IA YOLO."""
    payload = {
        "source": "ia_vision",
        "level": "alert",
        "message": "2 personnes détectées devant la caméra",
        "person_count": 2
    }

    response = await client.post("/api/v1/alerts", json=payload)
    assert response.status_code == 201
    data = response.json()
    assert data["source"] == "ia_vision"
    assert data["level"] == "alert"
    assert data["payload"]["person_count"] == 2


@pytest.mark.asyncio
async def test_create_alert_invalid_json(client: AsyncClient):
    """Vérifie le rejet HTTP 422 en cas de format invalide."""
    response = await client.post(
        "/api/v1/alerts",
        content="ceci_n_est_pas_un_json",
        headers={"Content-Type": "application/json"}
    )
    assert response.status_code == 422


@pytest.mark.asyncio
async def test_get_alerts_list(client: AsyncClient):
    payload = {
        "source": "ia_vision",
        "level": "high",
        "message": "Intrusion détectée"
    }
    await client.post("/api/v1/alerts", json=payload)

    response = await client.get("/api/v1/alerts?level=alert")
    assert response.status_code == 200
    data = response.json()
    assert len(data) >= 1


@pytest.mark.asyncio
async def test_acknowledge_alert_requires_auth(client: AsyncClient):
    res_create = await client.post("/api/v1/alerts", json={
        "source": "ia_vision",
        "level": "warning",
        "message": "Test ack"
    })
    alert_id = res_create.json()["id"]

    # Sans token -> 401
    res_unauth = await client.put(f"/api/v1/alerts/{alert_id}/acknowledge", json={"acknowledged_by": "martin"})
    assert res_unauth.status_code == 401

    # Avec token -> 200
    res_auth = await client.put(
        f"/api/v1/alerts/{alert_id}/acknowledge",
        json={"acknowledged_by": "martin"},
        headers={"Authorization": "Bearer test-api-key"}
    )
    assert res_auth.status_code == 200
    assert res_auth.json()["acknowledged"] is True
