"""Tests unitaires pour les commandes d'actionneurs (KAN-35)."""

import pytest
from httpx import AsyncClient


@pytest.mark.asyncio
async def test_actuator_command_unauthorized(client: AsyncClient):
    payload = {
        "target": "esp8266",
        "device_id": "sentinel-01",
        "command": {"buzzer": "on"}
    }
    response = await client.post("/api/v1/actuators/command", json=payload)
    assert response.status_code == 401


@pytest.mark.asyncio
async def test_actuator_command_authorized_and_audit(client: AsyncClient):
    payload = {
        "target": "esp8266",
        "device_id": "sentinel-01",
        "command": {"buzzer": "on", "led": "on"}
    }
    headers = {"Authorization": "Bearer sentinel-x-secret-key-2026"}

    # Envoi commande
    response = await client.post("/api/v1/actuators/command", json=payload, headers=headers)
    assert response.status_code == 200
    data = response.json()
    assert "audit_id" in data

    # Consultation de l'audit
    audit_res = await client.get("/api/v1/actuators/audit")
    assert audit_res.status_code == 200
    logs = audit_res.json()
    assert len(logs) >= 1
    assert logs[0]["target"] == "esp8266"


@pytest.mark.asyncio
async def test_system_status_and_health(client: AsyncClient):
    health = await client.get("/health")
    assert health.status_code == 200
    assert health.json()["status"] == "healthy"

    status = await client.get("/api/v1/status")
    assert status.status_code == 200
    assert status.json()["api"]["status"] == "online"


@pytest.mark.asyncio
async def test_dashboard_controls(client: AsyncClient):
    # Test alarm endpoint utilisé par le Dashboard React
    res_alarm = await client.post("/api/v1/control/alarm")
    assert res_alarm.status_code == 200
    assert res_alarm.json()["status"] == "alarm_triggered"

    # Test LED endpoint utilisé par le Dashboard React
    res_led = await client.post("/api/v1/control/led")
    assert res_led.status_code == 200
    assert res_led.json()["status"] == "led_triggered"


@pytest.mark.asyncio
async def test_video_stream_endpoint(client: AsyncClient):
    from unittest.mock import patch
    with patch("httpx.AsyncClient.stream", side_effect=Exception("Robot offline")):
        res = await client.get("/api/v1/video/stream")
        assert res.status_code == 200
        assert "multipart/x-mixed-replace" in res.headers["content-type"]


