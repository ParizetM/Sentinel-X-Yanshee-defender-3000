#!/usr/bin/env python3
# coding=utf-8
"""
SENTINEL-X — Script de Test des Actionneurs ESP8266 via Mosquitto (MQTTS Port 8883)
Déclenche le Buzzer pendant 1 seconde, puis la LED d'alerte pendant 1 seconde,
ou les deux simultanément.
"""

import os
import sys
import json
import time
import ssl
import paho.mqtt.client as mqtt

# Configuration Mosquitto
BROKER_HOST = os.environ.get("MQTT_BROKER_HOST", "172.16.137.4")
BROKER_PORT = 8883
BROKER_USER = os.environ.get("MQTT_USERNAME", "")
BROKER_PASS = os.environ.get("MQTT_PASSWORD", "")

DEVICE_ID = "esp-01"
CMD_TOPIC = "sentinelx/{}/cmd".format(DEVICE_ID)

def run_test():
    print("==================================================")
    print("  TEST DES ACTIONNEURS ESP8266 (BUZZER + LED)     ")
    print("==================================================")
    print("Broker : {}:{} (TLS)".format(BROKER_HOST, BROKER_PORT))
    print("Topic  : {}".format(CMD_TOPIC))
    print("")

    client = mqtt.Client()
    client.username_pw_set(BROKER_USER, BROKER_PASS)
    client.tls_set(cert_reqs=ssl.CERT_NONE)
    client.tls_insecure_set(True)

    try:
        client.connect(BROKER_HOST, BROKER_PORT, keepalive=10)
    except Exception as e:
        print("[ERREUR] Impossible de joindre le broker :", e)
        sys.exit(1)

    client.loop_start()
    time.sleep(0.5)

    # 1. Alarme Buzzer (1000 ms)
    payload_buzzer = {
        "target": "buzzer",
        "state": "on",
        "duration_ms": 1000
    }
    print("[1/2] 🔊 Déclenchement BUZZER pendant 1000 ms...")
    msg1 = client.publish(CMD_TOPIC, json.dumps(payload_buzzer), qos=1)
    msg1.wait_for_publish()
    print("      -> Ordre envoyé avec succès. Pause 1.5s...")
    time.sleep(1.5)

    # 2. LED Alerte (1000 ms)
    payload_led = {
        "target": "led",
        "state": "on",
        "duration_ms": 1000
    }
    print("[2/2] 💡 Déclenchement LED pendant 1000 ms...")
    msg2 = client.publish(CMD_TOPIC, json.dumps(payload_led), qos=1)
    msg2.wait_for_publish()
    print("      -> Ordre envoyé avec succès.")
    time.sleep(1.0)

    client.loop_stop()
    client.disconnect()
    print("")
    print("✅ Test terminé ! Les deux ordres ont été reçus par Mosquitto.")

if __name__ == "__main__":
    run_test()
