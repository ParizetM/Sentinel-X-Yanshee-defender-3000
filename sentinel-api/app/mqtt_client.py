"""Client MQTT asynchrone pour l'ingestion des mesures (ESP8266) et des détections (Robot/IA)."""

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
from app.websocket_manager import ws_manager

logger = logging.getLogger("sentinel.mqtt")

# Cache mémoire du statut des équipements
device_status_cache: Dict[str, Dict[str, Any]] = {}

# Dernière photo binaire JPEG capturée par le robot Yanshee / IA
latest_photo_cache: Optional[bytes] = None
latest_photo_timestamp: Optional[str] = None


class SentinelMQTTClient:
    def __init__(self):
        self.client: Optional[mqtt.Client] = None
        self.loop: Optional[asyncio.AbstractEventLoop] = None
        self.is_connected: bool = False
        self._last_intrusion_alert_time: float = 0.0

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
            # Souscriptions ESP8266
            client.subscribe("sentinelx/+/telemetry")
            client.subscribe("sentinel/+/telemetry")
            client.subscribe("sentinelx/+/status")
            client.subscribe("sentinel/+/status")
            client.subscribe("sentinel/+/event")
            # Souscriptions IA / Robot Yanshee (yanshi_video.py)
            client.subscribe("detection_robot/person_count")
            client.subscribe("detection_robot/photo")
            client.subscribe("detection_robot/timestamp")
            client.subscribe("detection_robot/action")
            client.subscribe("detection_robot/action_status")
            logger.info("Abonnements MQTT actifs (ESP8266 + Robot Yanshee IA).")
        else:
            self.is_connected = False
            logger.warning(f"Échec de connexion MQTT (rc={rc})")

    def _on_disconnect(self, client, userdata, disconnect_flags, rc=None, properties=None):
        self.is_connected = False
        logger.warning(f"Déconnecté du broker MQTT (rc={rc})")

    def _on_message(self, client, userdata, msg):
        topic = msg.topic
        payload_bytes = msg.payload

        if self.loop and self.loop.is_running():
            asyncio.run_coroutine_threadsafe(self._process_message(topic, payload_bytes), self.loop)

    async def _process_message(self, topic: str, payload_bytes: bytes):
        global latest_photo_cache, latest_photo_timestamp
        try:
            # 1. Photo binaire reçue de l'IA (detection_robot/photo)
            if topic == "detection_robot/photo":
                latest_photo_cache = payload_bytes
                logger.info(f"[MQTT] Photo JPEG reçue ({len(payload_bytes)} octets)")
                return

            # Décoder en texte pour les autres topics
            try:
                payload_str = payload_bytes.decode("utf-8").strip()
            except UnicodeDecodeError:
                return

            # 2. Télémétrie capteurs ESP8266 : sentinelx/esp-01/telemetry
            if topic.endswith("/telemetry"):
                await self._handle_telemetry(payload_str)

            # 3. Statut de vie boîtier : sentinelx/esp-01/status
            elif topic.endswith("/status"):
                parts = topic.split("/")
                device_id = parts[1] if len(parts) > 1 else "esp-01"
                device_status_cache[device_id] = {
                    "status": payload_str,
                    "last_seen": datetime.now(timezone.utc).isoformat()
                }
                logger.info(f"[MQTT] Statut boîtier {device_id} : {payload_str}")

            # 4. Nombre de personnes détectées par l'IA YOLO (detection_robot/person_count)
            elif topic == "detection_robot/person_count":
                try:
                    count = int(payload_str)
                except ValueError:
                    count = 0

                device_status_cache["yanshee-01"] = {
                    "status": "online",
                    "person_count": count,
                    "last_seen": datetime.now(timezone.utc).isoformat()
                }

                # Si personnes détectées > 0 : génération alerte intrusion
                if count > 0:
                    now_ts = asyncio.get_event_loop().time()
                    if now_ts - self._last_intrusion_alert_time >= 5.0:  # anti-rebond 5s
                        self._last_intrusion_alert_time = now_ts
                        await self._create_intrusion_alert(count)

            # 5. Timestamp de la photo
            elif topic == "detection_robot/timestamp":
                latest_photo_timestamp = payload_str

            # 6. Action robot exécutée (detection_robot/action ou action_status)
            elif topic.startswith("detection_robot/action"):
                logger.info(f"[MQTT] Robot action: {payload_str}")
                await ws_manager.broadcast({
                    "type": "robot_action",
                    "topic": topic,
                    "data": payload_str
                })

        except Exception as e:
            logger.error(f"Erreur traitement message MQTT ({topic}): {e}")

    async def _create_intrusion_alert(self, count: int):
        """Enregistre et diffuse une alerte d'intrusion détectée par l'IA YOLO."""
        alert = Alert(
            device_id="yanshee-01",
            created_at=datetime.now(timezone.utc),
            source="ia_vision",
            alert_type="human_intrusion",
            level="alert",
            value=float(count),
            message=f"Intrusion détectée : {count} personne(s) identifiée(s) par la caméra",
            payload_json=json.dumps({"person_count": count, "model": "yolo26n"}),
            acknowledged=False
        )

        async with async_session_factory() as session:
            session.add(alert)
            await session.commit()
            await session.refresh(alert)
            alert_dict = alert.to_dict()

        logger.warning(f"🚨 ALERTE INTRUSION ENREGISTRÉE : {count} personne(s)")
        await ws_manager.broadcast({
            "type": "alert",
            "data": alert_dict
        })

    async def _handle_telemetry(self, payload_str: str):
        data = json.loads(payload_str)
        device_id = data.get("device") or data.get("device_id") or "esp-01"

        # Mise à jour du cache de vie
        device_status_cache[device_id] = {
            "status": "online",
            "last_seen": datetime.now(timezone.utc).isoformat(),
            "last_telemetry": data
        }

        # Parsing capteurs
        gas_obj = data.get("gas", {}) or {}
        if isinstance(gas_obj, int):
            gas_raw = gas_obj
            gas_baseline = None
            gas_level = "normal"
        else:
            gas_raw = gas_obj.get("raw")
            gas_baseline = gas_obj.get("baseline")
            gas_level = gas_obj.get("level", "normal")

        actuators_obj = data.get("actuators", {}) or {}

        telemetry_record = Telemetry(
            device_id=device_id,
            recorded_at=datetime.now(timezone.utc),
            uptime_s=data.get("uptime_s"),
            temperature=data.get("temperature"),
            humidity=data.get("humidity"),
            gas_raw=gas_raw,
            gas_baseline=gas_baseline,
            gas_level=gas_level,
            presence=bool(data.get("presence", data.get("pir", False))),
            rssi=data.get("rssi"),
            buzzer_state=actuators_obj.get("buzzer", "off"),
            led_state=actuators_obj.get("led", "off")
        )

        async with async_session_factory() as session:
            session.add(telemetry_record)

            # Détection automatique de pic de gaz (niveau "alerte")
            if gas_level in ["alerte", "alert"]:
                alert = Alert(
                    device_id=device_id,
                    source="sensor",
                    alert_type="gas_leak",
                    level="alert",
                    value=float(gas_raw or 0),
                    message=f"Seuil de gaz critique dépassé sur le capteur MQ-2 (valeur: {gas_raw})",
                    payload_json=json.dumps({"gas": gas_obj})
                )
                session.add(alert)

            await session.commit()

        # Diffusion temps réel aux clients WebSocket connectés (Dashboard React)
        tel_dict = telemetry_record.to_dict()
        await ws_manager.broadcast({
            "type": "telemetry",
            "data": tel_dict
        })

    def publish_command(self, topic: str, payload: dict) -> bool:
        """Publie une commande MQTT vers l'ESP8266 ou le Robot."""
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
