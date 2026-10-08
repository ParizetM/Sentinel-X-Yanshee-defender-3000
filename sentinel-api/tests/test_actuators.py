"""Tests unitaires pour les commandes d'actionneurs (Contrat §4.3 & §4.4, KAN-35)."""

import pytest
from unittest.mock import patch
from httpx import AsyncClient


@pytest.mark.asyncio
async def test_commands_contract_payload(client: AsyncClient):
    """Vérifie l'envoi d'une commande selon le contrat §4.3 exact."""
    payload = {
        "target": "buzzer",
        "state": "toggle",
        "duration_ms": 3000
    }
    response = await client.post("/api/v1/commands", json=payload)
    assert response.status_code == 200
    data = response.json()
    assert data["target"] == "buzzer"
    assert data["command"]["state"] == "toggle"
    assert data["command"]["duration_ms"] == 3000
    assert "audit_id" in data


@pytest.mark.asyncio
async def test_commands_all_esp8266(client: AsyncClient):
    """Vérifie la commande d'arrêt globale (target=all, state=off)."""
    payload = {
        "target": "all",
        "state": "off"
    }
    response = await client.post("/api/v1/commands", json=payload)
    assert response.status_code == 200
    data = response.json()
    assert data["command"]["target"] == "all"
    assert data["command"]["state"] == "off"


@pytest.mark.asyncio
async def test_commands_yanshee_robot(client: AsyncClient):
    """Vérifie la commande envoyée au robot Yanshee."""
    payload = {
        "target": "yanshee",
        "action": "punch",
        "dry_run": True
    }
    response = await client.post("/api/v1/commands", json=payload)
    assert response.status_code == 200
    data = response.json()
    assert data["command"]["cmd"] == "punch"
    assert data["command"]["dry_run"] is True


@pytest.mark.asyncio
async def test_dashboard_controls_direct(client: AsyncClient):
    """Test des routes de contrôle utilisées par le Dashboard React."""
    res_alarm = await client.post("/api/v1/control/alarm")
    assert res_alarm.status_code == 200
    assert res_alarm.json()["status"] == "alarm_triggered"

    res_led = await client.post("/api/v1/control/led")
    assert res_led.status_code == 200
    assert res_led.json()["status"] == "led_triggered"


@pytest.mark.asyncio
async def test_auth_login_endpoint(client: AsyncClient):
    """Test de la route de connexion (Contrat §4.4)."""
    # Échec
    bad_res = await client.post("/api/v1/auth/login", json={"username": "bad", "password": "wrong"})
    assert bad_res.status_code == 401

    # Succès
    good_res = await client.post("/api/v1/auth/login", json={"username": "admin", "password": "test-password"})
    assert good_res.status_code == 200
    assert "access_token" in good_res.json()


@pytest.mark.asyncio
async def test_video_stream_and_system_health(client: AsyncClient):
    health = await client.get("/health")
    assert health.status_code == 200

    status = await client.get("/api/v1/status")
    assert status.status_code == 200

    with patch("httpx.AsyncClient.stream", side_effect=Exception("Robot offline")):
        res = await client.get("/api/v1/camera/stream")
        assert res.status_code == 200
        assert "multipart/x-mixed-replace" in res.headers["content-type"]
