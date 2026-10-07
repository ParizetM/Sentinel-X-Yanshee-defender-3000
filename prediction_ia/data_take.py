import paho.mqtt.client as mqtt
import json
import csv
import os
from datetime import datetime

# --- Configuration ---
BROKER = "172.16.137.4"      # ou l'IP de ton broker
PORT = 1883
TOPIC = "sentinelx/esp-01/telemetry"       # adapte selon ton topic
USERNAME = "admin"           # si auth requise
PASSWORD = "Epsi1234.!"

CSV_FILE = "telemetry.csv"
JSON_FILE = "telemetry.jsonl"   # JSON Lines : 1 objet par ligne
BUFFER_SIZE = 1            # écriture par lots pour la perf

# --- Buffers ---
csv_buffer = []
json_buffer = []
csv_header_written = os.path.exists(CSV_FILE)

# --- Callbacks MQTT ---
def on_connect(client, userdata, flags, rc):
    if rc == 0:
        print(f"✅ Connecté au broker {BROKER}:{PORT}")
        client.subscribe(TOPIC, qos=1)
        print(f"📡 Abonné à : {TOPIC}")
    else:
        print(f"❌ Échec de connexion (code {rc})")

def on_message(client, userdata, msg):
    try:
        payload = msg.payload.decode("utf-8")
        data = json.loads(payload)   # si le payload est déjà du JSON
    except (UnicodeDecodeError, json.JSONDecodeError):
        # sinon on stocke brut
        data = {"value": msg.payload.decode(errors="ignore")}

    # Ajout de métadonnées utiles pour le ML / le debug
    record = {
        "timestamp": datetime.utcnow().isoformat(),
        # "timestamp": datetime.isoformat(),
        "topic": msg.topic,
        **data
    }
    print(f"Le record est {record}")
    csv_buffer.append(record)
    json_buffer.append(record)

    if len(csv_buffer) >= BUFFER_SIZE:
        flush_buffers()

def flush_buffers():
    global csv_header_written
    if csv_buffer:
        # Récupère toutes les colonnes rencontrées
        keys = set()
        for r in csv_buffer:
            keys.update(r.keys())
        fieldnames = sorted(keys)

        with open(CSV_FILE, "a", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=fieldnames)
            if not csv_header_written:
                writer.writeheader()
                csv_header_written = True
            writer.writerows(csv_buffer)
        csv_buffer.clear()

    if json_buffer:
        with open(JSON_FILE, "a", encoding="utf-8") as f:
            for r in json_buffer:
                f.write(json.dumps(r, ensure_ascii=False) + "\n")
        json_buffer.clear()

# --- Client MQTT ---
client = mqtt.Client(client_id="telemetry_collector")
if USERNAME:
    client.username_pw_set(USERNAME, PASSWORD)

client.on_connect = on_connect
client.on_message = on_message

client.connect(BROKER, PORT, keepalive=60)

try:
    print("▶️  Collecte en cours (Ctrl+C pour arrêter)...")
    client.loop_forever()
except KeyboardInterrupt:
    print("\n⏹  Arrêt demandé...")
finally:
    flush_buffers()       # <-- ne pas oublier le flush final !
    client.disconnect()
    print(f"💾 Données sauvegardées dans {CSV_FILE} et {JSON_FILE}")
