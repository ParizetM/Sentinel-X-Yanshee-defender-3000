"""
Smoke test d'intégration : démarre un broker MQTT local (amqtt),
puis utilise les vraies fonctions de publication de yanshi_video
pour vérifier que les 4 topics arrivent correctement au broker.

Usage : python3 smoke_test_mqtt.py
"""

import asyncio
import json
import threading
import time

import numpy as np
import paho.mqtt.client as mqtt
from amqtt.broker import Broker

import yanshi_video


PORT = 18833  # port local dédié pour éviter tout conflit


def start_broker() -> None:
    """Démarre le broker amqtt dans un thread en arrière-plan."""

    config = {
        "listeners": {
            "default": {
                "type": "tcp",
                "bind": f"127.0.0.1:{PORT}",
            }
        },
        "sys_interval": 0,
        "auth": {"allow-anonymous": True},
    }

    async def run_broker():
        broker = Broker(config)
        await broker.start()
        await asyncio.Event().wait()  # garde le broker en vie

    threading.Thread(
        target=lambda: asyncio.run(run_broker()),
        daemon=True
    ).start()

    time.sleep(1)  # laisse le broker démarrer


def main() -> None:
    start_broker()

    # --- Pointe les constantes du module vers le broker local ---
    yanshi_video.MQTT_HOST = "127.0.0.1"
    yanshi_video.MQTT_PORT = PORT
    yanshi_video.MQTT_USERNAME = None
    yanshi_video.MQTT_PASSWORD = None

    # --- Abonné de contrôle ---
    received = {}

    def on_message(client, userdata, message):
        received[message.topic] = message.payload
        print(f"[SMOKE] reçu : {message.topic}")

    subscriber = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2)
    subscriber.on_message = on_message
    subscriber.connect("127.0.0.1", PORT)
    subscriber.subscribe("detection_robot/#")
    subscriber.loop_start()

    # --- Publication avec les vraies fonctions du script ---
    client = yanshi_video.create_mqtt_client()

    # Attend que le client soit connecté au broker
    for _ in range(50):
        if client.is_connected():
            break
        time.sleep(0.1)

    assert client.is_connected(), "Client MQTT non connecté au broker"

    yanshi_video.publish_timestamp(client, "2026-10-06T12:00:00+02:00")
    yanshi_video.publish_photo(client, np.zeros((64, 64, 3), dtype=np.uint8))
    yanshi_video.publish_person_count(client, 2)
    yanshi_video.publish_action(client, 200)

    time.sleep(1)  # laisse les messages circuler

    # --- Vérifications ---
    assert yanshi_video.TOPIC_TIMESTAMP in received
    assert received[yanshi_video.TOPIC_TIMESTAMP] == b"2026-10-06T12:00:00+02:00"

    assert yanshi_video.TOPIC_PHOTO in received
    photo = received[yanshi_video.TOPIC_PHOTO]
    assert photo[:2] == b"\xff\xd8" and photo[-2:] == b"\xff\xd9"

    assert yanshi_video.TOPIC_PERSON_COUNT in received
    assert received[yanshi_video.TOPIC_PERSON_COUNT] == b"2"

    assert yanshi_video.TOPIC_ACTION in received
    action = json.loads(received[yanshi_video.TOPIC_ACTION])
    assert action["action"] == "punch"
    assert action["status_code"] == 200

    print("[SMOKE] ✅ 4 topics reçus par le broker, payloads corrects")

    client.loop_stop()
    client.disconnect()
    subscriber.loop_stop()
    subscriber.disconnect()


if __name__ == "__main__":
    main()
