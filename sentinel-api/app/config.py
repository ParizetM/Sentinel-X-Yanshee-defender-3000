"""Configuration centralisée pour l'API REST Sentinel-X."""

import os
from typing import Optional
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    # Application
    API_ENV: str = "development"
    API_HOST: str = "0.0.0.0"
    API_PORT: int = 8080
    API_DEBUG: bool = True
    API_SECRET_KEY: str = "sentinel-x-secret-key-2026"

    # Database
    DATABASE_URL: str = "sqlite+aiosqlite:///./sentinel.db"

    # MQTT
    MQTT_BROKER_HOST: str = "172.16.137.4"
    MQTT_BROKER_PORT: int = 8883
    MQTT_USERNAME: Optional[str] = "admin"
    MQTT_PASSWORD: Optional[str] = "Epsi1234.!"
    MQTT_USE_TLS: bool = True
    MQTT_CA_CERT_PATH: Optional[str] = None
    MQTT_CLIENT_ID: str = "sentinel-x-api-backend"
    MQTT_ENABLED: bool = True

    # MQTT Topics
    MQTT_TELEMETRY_TOPIC: str = "sentinelx/+/telemetry"
    MQTT_STATUS_TOPIC: str = "sentinelx/+/status"
    MQTT_CMD_TOPIC_PREFIX: str = "sentinelx"
    MQTT_ROBOT_CMD_TOPIC: str = "detection_robot/command"
    MQTT_ROBOT_STATUS_TOPIC: str = "detection_robot/action_status"

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore"
    )


settings = Settings()
