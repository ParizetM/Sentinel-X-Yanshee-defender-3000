"""
Service temps réel de maintenance prédictive Sentinel-X.

  ESP8266 ──MQTTS──► broker ──► anomaly_service.py ──HTTPS──► POST /api/v1/alerts
                                        │
                                        └──MQTTS──► sentinelx/<device>/anomaly (risque chaque seconde)

Pour chaque message de télémétrie :
  1. tampon glissant des 6 dernières minutes + références long terme par boîtier ;
  2. features → Isolation Forest + Random Forest par capteur → indice de risque ;
  3. anti-rebond → alerte « ia_anomaly » envoyée à l'API au début, au passage
     en critique, à la confirmation du diagnostic et au retour à la normale.

Configuration : .env (voir .env.example). Lancement : python anomaly_service.py
"""

from __future__ import annotations

import argparse
import json
import logging
import queue
import signal
import threading
import time
from datetime import datetime, timezone
from typing import Optional

import requests

from common import connect_mqtt, create_mqtt_client, env_flag, env_int, env_str, flatten_record, resolve_path
from detector import DIAGNOSIS_LABELS, AnomalyModel, StreamDetector

log = logging.getLogger("sentinel.anomaly")

TELEMETRY_TOPIC = env_str("TELEMETRY_TOPIC", "sentinelx/+/telemetry")
ANOMALY_TOPIC = env_str("ANOMALY_TOPIC", "sentinelx/{device}/anomaly")
API_ALERTS_URL = env_str("API_ALERTS_URL")
API_TOKEN = env_str("API_TOKEN")
API_CA_CERT = env_str("API_CA_CERT")
API_TLS_VERIFY = env_flag("API_TLS_VERIFY", default=True)
API_TIMEOUT_S = env_int("API_TIMEOUT_S", 5)

LEVELS = {"warning": "warning", "critical": "critical", "info": "info"}


def build_alert(event: dict) -> dict:
    """Événement du détecteur → corps de POST /api/v1/alerts (schéma AlertCreate de l'API)."""
    expl = event["explanation"]
    diagnosis = DIAGNOSIS_LABELS.get(expl["diagnosis"], expl["diagnosis"])
    if event["kind"] == "end":
        message = (f"IA : retour à la normale ({diagnosis.lower()}, durée {event.get('duration_s', 0)} s, "
                   f"risque max {event.get('peak_risk', event['risk']):.2f})")
    else:
        prefix = {"start": "IA prédictive", "escalate": "IA : aggravation",
                  "diagnosis": "IA : diagnostic confirmé"}[event["kind"]]
        message = f"{prefix} : {diagnosis} — {expl['label'].lower()} ({expl['value_str']})"
    return {
        "device_id": event["device"],
        "ts": datetime.now(timezone.utc).isoformat(),
        "source": "ia_anomaly",
        "alert_type": event["alert_type"],
        "level": LEVELS[event["level"]],
        "value": event["risk"],
        "message": message,
        "payload": {
            "event": event["kind"],
            "uptime_s": event["uptime_s"],
            "risk": event["risk"],
            "sensor": expl["sensor"],
            "diagnosis": expl["diagnosis"],
            "rf_probability": expl["rf_probability"],
            "if_risk": expl["if_risk"],
            "feature": expl["feature"],
            "feature_value": expl["value"],
            "feature_z": expl["z"],
            "duration_s": event.get("duration_s"),
            "model": "isolation_forest+random_forest",
        },
    }


class AlertSender(threading.Thread):
    """Envoie les alertes à l'API dans un thread à part (ne bloque jamais la boucle MQTT)."""

    def __init__(self, url: Optional[str]) -> None:
        super().__init__(daemon=True, name="alert-sender")
        self.url = url
        self.queue: "queue.Queue[dict]" = queue.Queue(maxsize=200)
        self.session = requests.Session()
        if API_TOKEN:
            self.session.headers["Authorization"] = f"Bearer {API_TOKEN}"
        if not API_TLS_VERIFY:
            log.warning("Vérification TLS de l'API désactivée (API_TLS_VERIFY=false)")
            self.verify = False
        else:
            self.verify = str(resolve_path(API_CA_CERT)) if API_CA_CERT else True

    def submit(self, alert: dict) -> None:
        try:
            self.queue.put_nowait(alert)
        except queue.Full:
            log.error("File d'alertes pleine : alerte abandonnée")

    def run(self) -> None:
        while True:
            alert = self.queue.get()
            if not self.url:
                log.info("[API désactivée] %s", alert["message"])
                continue
            for attempt in range(3):
                try:
                    r = self.session.post(self.url, json=alert, timeout=API_TIMEOUT_S, verify=self.verify)
                    if r.status_code < 300:
                        log.info("Alerte envoyée à l'API (%s) : %s", r.status_code, alert["message"])
                        break
                    log.error("API %s : %s", r.status_code, r.text[:200])
                    if r.status_code < 500:
                        break
                except requests.RequestException as exc:
                    log.error("API injoignable (essai %d/3) : %s", attempt + 1, exc)
                time.sleep(2 ** attempt)


class AnomalyService:
    def __init__(self, model: AnomalyModel, publish_risk: bool = True) -> None:
        self.detector = StreamDetector(model)
        self.sender = AlertSender(API_ALERTS_URL)
        self.publish_risk = publish_risk
        self.client = create_mqtt_client(env_str("MQTT_CLIENT_ID", "sentinel-x-anomaly"))
        self.client.on_connect = self.on_connect
        self.client.on_disconnect = self.on_disconnect
        self.client.on_message = self.on_message
        self.lock = threading.Lock()
        self.last_log = 0.0

    def on_connect(self, client, userdata, flags, reason_code, properties=None) -> None:
        if reason_code == 0:
            log.info("Connecté au broker, abonnement à %s", TELEMETRY_TOPIC)
            client.subscribe(TELEMETRY_TOPIC, qos=1)
        else:
            log.error("Connexion MQTT refusée (code %s)", reason_code)

    def on_disconnect(self, client, userdata, flags, reason_code, properties=None) -> None:
        log.warning("Déconnecté du broker (code %s), reconnexion automatique...", reason_code)

    def on_message(self, client, userdata, msg) -> None:
        try:
            data = json.loads(msg.payload.decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError):
            log.warning("Message illisible sur %s", msg.topic)
            return
        if not isinstance(data, dict):
            return
        record = flatten_record(data)
        if not data.get("device") and not data.get("device_id"):
            parts = msg.topic.split("/")
            record["device"] = parts[1] if len(parts) > 2 else record["device"]

        try:
            with self.lock:
                result = self.detector.update(record)
        except Exception:
            log.exception("Erreur du détecteur sur %s", record.get("device"))
            return

        if self.publish_risk and result["status"] == "ok":
            self.publish(result)
        event = result.get("event")
        if event:
            alert = build_alert(event)
            log.warning("[%s] %s", event["kind"].upper(), alert["message"])
            self.sender.submit(alert)

        now = time.monotonic()
        if now - self.last_log >= 10:
            self.last_log = now
            if result["status"] == "ok":
                log.info("%s uptime=%s risque=%.2f (%s) %s", result["device"], result["uptime_s"], result["risk"],
                         ", ".join(f"{k}={v:.2f}" for k, v in result["risks"].items()),
                         "ALERTE " + (result.get("level") or "") if result["active"] else "")
            else:
                log.info("%s : %s", result["device"], result["status"])

    def publish(self, result: dict) -> None:
        expl = result.get("explanation") or {}
        payload = {
            "device": result["device"],
            "uptime_s": result["uptime_s"],
            "ts": datetime.now(timezone.utc).isoformat(),
            "risk": result["risk"],
            "risks": result["risks"],
            "anomaly": result["anomaly"],
            "alert_active": result["active"],
            "level": result.get("level"),
            "diagnosis": expl.get("diagnosis") if result["active"] else None,
            "diagnosis_label": DIAGNOSIS_LABELS.get(expl.get("diagnosis")) if result["active"] else None,
        }
        self.client.publish(ANOMALY_TOPIC.format(device=result["device"]), json.dumps(payload), qos=0)

    def run(self) -> None:
        if not API_ALERTS_URL:
            log.warning("API_ALERTS_URL absent : les alertes seront seulement journalisées")
        self.sender.start()
        connect_mqtt(self.client)
        self.client.loop_forever(retry_first_connection=True)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--model", default=None, help="chemin du modèle (défaut : models/anomaly_model.joblib)")
    parser.add_argument("--no-publish", action="store_true", help="ne pas publier le risque sur MQTT")
    parser.add_argument("-v", "--verbose", action="store_true")
    args = parser.parse_args()

    logging.basicConfig(level=logging.DEBUG if args.verbose else logging.INFO,
                        format="%(asctime)s %(levelname)s %(message)s", datefmt="%H:%M:%S")
    model = AnomalyModel.load(resolve_path(args.model)) if args.model else AnomalyModel.load()
    log.info("Modèle chargé (entraîné le %s)", model.meta.get("trained_at"))

    service = AnomalyService(model, publish_risk=not args.no_publish)
    signal.signal(signal.SIGTERM, lambda *_: service.client.disconnect())
    try:
        service.run()
    except KeyboardInterrupt:
        log.info("Arrêt demandé")
        service.client.disconnect()


if __name__ == "__main__":
    main()
