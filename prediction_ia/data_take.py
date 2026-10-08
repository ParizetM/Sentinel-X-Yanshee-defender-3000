"""
Collecte de la télémétrie MQTT dans un fichier JSONL (un message par ligne).

Sert à constituer les jeux de données de l'IA :
  - data/normal_<nom>.jsonl   : boîtier en fonctionnement normal, SANS
    manipulation (30 à 60 min conseillées) → utilisé par train.py ;
  - data/test_<nom>.jsonl     : sessions de scénarios (chauffe, gaz...) → evaluate.py.

Configuration du broker : .env (voir .env.example), connexion MQTTS.

Exemples :
  python data_take.py --out data/normal_salle.jsonl
  python data_take.py --out data/test_chauffe.jsonl --minutes 20
"""

from __future__ import annotations

import argparse
import json
import time
from datetime import datetime, timezone
from pathlib import Path

from common import SCRIPT_DIR, connect_mqtt, create_mqtt_client, env_str, flatten_record


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    default_out = SCRIPT_DIR / "data" / f"telemetry_{datetime.now():%Y%m%d_%H%M%S}.jsonl"
    parser.add_argument("--out", type=Path, default=default_out)
    parser.add_argument("--topic", default=env_str("TELEMETRY_TOPIC", "sentinelx/+/telemetry"))
    parser.add_argument("--minutes", type=float, default=None, help="arrêt automatique après N minutes")
    args = parser.parse_args()

    args.out.parent.mkdir(parents=True, exist_ok=True)
    out = open(args.out, "a", encoding="utf-8", buffering=1)  # une ligne écrite = une ligne sur disque
    count = 0

    def on_connect(client, userdata, flags, reason_code, properties=None):
        if reason_code == 0:
            print(f"Connecté, abonné à {args.topic}")
            client.subscribe(args.topic, qos=1)
        else:
            print(f"Connexion refusée (code {reason_code})")

    def on_message(client, userdata, msg):
        nonlocal count
        try:
            data = json.loads(msg.payload.decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError):
            print(f"Message illisible ignoré sur {msg.topic}")
            return
        record = {"received_at": datetime.now(timezone.utc).isoformat(), "topic": msg.topic, **data}
        out.write(json.dumps(record, ensure_ascii=False) + "\n")
        count += 1
        if count % 30 == 1:
            flat = flatten_record(data)
            print(f"{count:5d} msg | {flat['device']} uptime={flat['uptime_s']} T={flat['temperature']} "
                  f"H={flat['humidity']} gaz={flat['gas_raw']} ({flat['gas_level']})")

    client = create_mqtt_client(f"sentinel-collector-{int(time.time())}")
    client.on_connect = on_connect
    client.on_message = on_message
    connect_mqtt(client)
    client.loop_start()

    print(f"Enregistrement dans {args.out} (Ctrl+C pour arrêter)")
    deadline = time.monotonic() + args.minutes * 60 if args.minutes else None
    try:
        while deadline is None or time.monotonic() < deadline:
            time.sleep(0.5)
    except KeyboardInterrupt:
        pass
    finally:
        client.loop_stop()
        client.disconnect()
        out.close()
        print(f"{count} messages enregistrés dans {args.out}")


if __name__ == "__main__":
    main()
