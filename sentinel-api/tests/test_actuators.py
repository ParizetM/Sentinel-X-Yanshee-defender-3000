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
