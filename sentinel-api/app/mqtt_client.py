"""Client MQTT asynchrone pour l'ingestion des mesures (KAN-31) et l'envoi de commandes (KAN-35)."""

import json
import ssl
import asyncio
import logging
from typing import Optional, Dict, Any
from datetime import datetime, timezone
import paho.mqtt.client as mqtt

from app.config import settings
from app.database import async_session_factory
from app.models.telemetry import Telemetry
from app.models.alert import Alert

logger = logging.getLogger("sentinel.mqtt")

# Stockage en mémoire du dernier statut connu des devices
device_status_cache: Dict[str, Dict[str, Any]] = {}


class SentinelMQTTClient:
    def __init__(self):
        self.client: Optional[mqtt.Client] = None
        self.loop: Optional[asyncio.AbstractEventLoop] = None
        self.is_connected: bool = False

    def setup(self, loop: asyncio.AbstractEventLoop):
        self.loop = loop
        self.client = mqtt.Client(
            client_id=settings.MQTT_CLIENT_ID,
            callback_api_version=mqtt.CallbackAPIVersion.VERSION2
        )

        if settings.MQTT_USERNAME and settings.MQTT_PASSWORD:
            self.client.username_pw_set(settings.MQTT_USERNAME, settings.MQTT_PASSWORD)

        if settings.MQTT_USE_TLS:
            context = ssl.create_default_context()
            if settings.MQTT_CA_CERT_PATH:
                context.load_verify_locations(settings.MQTT_CA_CERT_PATH)
            else:
                context.check_hostname = False
                context.verify_mode = ssl.CERT_NONE
            self.client.tls_set_context(context)

        self.client.on_connect = self._on_connect
        self.client.on_disconnect = self._on_disconnect
        self.client.on_message = self._on_message

    def start(self):
        if not settings.MQTT_ENABLED:
            logger.info("MQTT client désactivé par configuration.")
            return

        try:
            logger.info(f"Connexion au broker MQTT {settings.MQTT_BROKER_HOST}:{settings.MQTT_BROKER_PORT}...")
            self.client.connect_async(settings.MQTT_BROKER_HOST, settings.MQTT_BROKER_PORT, keepalive=60)
            self.client.loop_start()
        except Exception as e:
            logger.error(f"Échec de connexion au broker MQTT : {e}")

    def stop(self):
        if self.client:
            self.client.loop_stop()
            self.client.disconnect()
            logger.info("Client MQTT arrêté.")

    def _on_connect(self, client, userdata, flags, rc, properties=None):
        if rc == 0:
            self.is_connected = True
            logger.info("Connecté au broker MQTT avec succès.")
            client.subscribe(settings.MQTT_TELEMETRY_TOPIC)
            client.subscribe(settings.MQTT_STATUS_TOPIC)
            client.subscribe(settings.MQTT_ROBOT_STATUS_TOPIC)
            logger.info(f"Abonné aux topics : {settings.MQTT_TELEMETRY_TOPIC}, {settings.MQTT_STATUS_TOPIC}")
        else:
            self.is_connected = False
            logger.warning(f"Échec de connexion MQTT (code retour rc={rc})")

    def _on_disconnect(self, client, userdata, disconnect_flags, rc=None, properties=None):
        self.is_connected = False
        logger.warning(f"Déconnecté du broker MQTT (rc={rc})")

    def _on_message(self, client, userdata, msg):
        topic = msg.topic
        try:
            payload_str = msg.payload.decode("utf-8")
        except UnicodeDecodeError:
            payload_str = ""

        if self.loop and self.loop.is_running():
            asyncio.run_coroutine_threadsafe(self._process_message(topic, payload_str), self.loop)

    async def _process_message(self, topic: str, payload_str: str):
        try:
            # Traitement Télémétrie : sentinelx/{device}/telemetry
            if topic.endswith("/telemetry"):
                await self._handle_telemetry(payload_str)
            # Traitement Statut : sentinelx/{device}/status
            elif topic.endswith("/status"):
                parts = topic.split("/")
                device_id = parts[1] if len(parts) > 1 else "unknown"
                device_status_cache[device_id] = {
                    "status": payload_str.strip(),
                    "last_seen": datetime.now(timezone.utc).isoformat()
                }
                logger.info(f"[MQTT] Statut device {device_id} : {payload_str}")
        except Exception as e:
            logger.error(f"Erreur lors du traitement du message MQTT ({topic}): {e}")

    async def _handle_telemetry(self, payload_str: str):
        data = json.loads(payload_str)
        device_id = data.get("device", "sentinel-01")

        # Mise à jour du cache de vie
        device_status_cache[device_id] = {
            "status": "online",
            "last_seen": datetime.now(timezone.utc).isoformat(),
            "last_telemetry": data
        }

        # Parsing capteurs
        gas_obj = data.get("gas", {}) or {}
        actuators_obj = data.get("actuators", {}) or {}

        telemetry_record = Telemetry(
            device_id=device_id,
            recorded_at=datetime.now(timezone.utc),
            uptime_s=data.get("uptime_s"),
            temperature=data.get("temperature"),
            humidity=data.get("humidity"),
            gas_raw=gas_obj.get("raw"),
            gas_baseline=gas_obj.get("baseline"),
            gas_level=gas_obj.get("level", "normal"),
            presence=bool(data.get("presence", False)),
            rssi=data.get("rssi"),
            buzzer_state=actuators_obj.get("buzzer", "off"),
            led_state=actuators_obj.get("led", "off")
        )

        async with async_session_factory() as session:
            session.add(telemetry_record)

            # Détection automatique de niveau critique de gaz
            if gas_obj.get("level") == "alerte":
                alert = Alert(
                    device_id=device_id,
                    source="sensor_esp8266",
                    alert_type="gas_leak",
                    severity="critical",
                    value=float(gas_obj.get("raw", 0)),
                    message=f"Fuite de gaz critique détectée par le capteur MQ-2 (valeur brute: {gas_obj.get('raw')})",
                    metadata_json=json.dumps({"gas": gas_obj})
                )
                session.add(alert)

            await session.commit()

        logger.debug(f"[MQTT] Mesure sauvegardée pour {device_id}")

    def publish_command(self, topic: str, payload: dict) -> bool:
        """Publie une commande MQTT (ex: vers ESP8266 ou Robot)."""
        if not self.client or not self.is_connected:
            logger.warning("Publication MQTT ignorée : client non connecté.")
            return False

        try:
            payload_bytes = json.dumps(payload).encode("utf-8")
            info = self.client.publish(topic, payload_bytes, qos=1)
            info.wait_for_publish(timeout=2.0)
            return True
        except Exception as e:
            logger.error(f"Erreur publication MQTT vers {topic}: {e}")
            return False


mqtt_manager = SentinelMQTTClient()
