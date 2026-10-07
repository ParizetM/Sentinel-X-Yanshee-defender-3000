# coding=utf-8
"""
SENTINEL-X — Yanshee MQTT Subscriber Service
Ecoute les ordres d action sur le broker Mosquitto centralise
et pilote les servomoteurs du robot Yanshee (Victory + Punch Gauche + Punch Droit).
"""

import os
import sys
import json
import time
import threading
import paho.mqtt.client as mqtt

# Configuration Broker Mosquitto
MQTT_HOST = os.environ.get("MQTT_BROKER_HOST", "172.16.137.4")
MQTT_PORT = int(os.environ.get("MQTT_BROKER_PORT", "8883"))
MQTT_USER = os.environ.get("MQTT_USERNAME", "admin")
MQTT_PASSWORD = os.environ.get("MQTT_PASSWORD", "Epsi1234.!")

# Topics MQTT
TOPIC_COMMAND = "detection_robot/command"
TOPIC_ACTION_STATUS = "detection_robot/action_status"

# Gestion de concurrence moteur
is_busy = False
action_lock = threading.Lock()

# ROS Yanshee Service Proxy (initialise au runtime)
ros_play_motion = None

def init_ros():
    global ros_play_motion
    try:
        import rospy
        import ubt_msgs.srv
        rospy.init_node("yanshee_mqtt_service", anonymous=True, disable_signals=True)
        rospy.wait_for_service("/play_motion_hts", timeout=5)
        ros_play_motion = rospy.ServiceProxy("/play_motion_hts", ubt_msgs.srv.play_motion_hts)
        print("[ROBOT-MQTT] Connexion au service ROS /play_motion_hts reussie !")
    except Exception as e:
        print("[ROBOT-MQTT] Avertissement ROS : " + str(e))

def execute_combo_thread(client, dry_run=False):
    global is_busy
    with action_lock:
        if is_busy:
            print("[ROBOT-MQTT] Sequence deja en cours, requete ignoree.")
            payload = {
                "status": "busy",
                "message": "Sequence deja en cours d execution",
                "timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
            }
            client.publish(TOPIC_ACTION_STATUS, json.dumps(payload), qos=1)
            return
        is_busy = True

    try:
        start_payload = {
            "status": "executing",
            "action": "victory_punch_left_right",
            "dry_run": dry_run,
            "timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
        }
        client.publish(TOPIC_ACTION_STATUS, json.dumps(start_payload), qos=1)

        if dry_run:
            print("[ROBOT-MQTT][DRY-RUN] Simulation combo : Aucun mouvement physique.")
            time.sleep(3.0)
        else:
            if ros_play_motion is None:
                raise RuntimeError("Service ROS /play_motion_hts non disponible")

            # 1. Geste Coucou (Victory)
            print("[ROBOT-MQTT] 1/3 Coucou Victory (Victory)...")
            r0 = ros_play_motion("Victory", 1)
            wait_victory = (r0.total_time / 1000.0) if hasattr(r0, 'total_time') and r0.total_time > 0 else 4.7
            time.sleep(wait_victory + 0.3)

            # 2. Punch Gauche (LeftHitForward)
            print("[ROBOT-MQTT] 2/3 Punch Gauche (LeftHitForward)...")
            r1 = ros_play_motion("LeftHitForward", 1)
            wait_left = (r1.total_time / 1000.0) if hasattr(r1, 'total_time') and r1.total_time > 0 else 2.6
            time.sleep(wait_left + 0.3)

            # 3. Punch Droit (RightHitForward)
            print("[ROBOT-MQTT] 3/3 Punch Droit (RightHitForward)...")
            r2 = ros_play_motion("RightHitForward", 1)
            wait_right = (r2.total_time / 1000.0) if hasattr(r2, 'total_time') and r2.total_time > 0 else 2.6
            time.sleep(wait_right)

        print("[ROBOT-MQTT] Combo termine avec succes !")

        done_payload = {
            "status": "completed",
            "action": "victory_punch_left_right",
            "dry_run": dry_run,
            "timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
        }
        client.publish(TOPIC_ACTION_STATUS, json.dumps(done_payload), qos=1)

    except Exception as e:
        print("[ROBOT-MQTT] Erreur execution : " + str(e))
        err_payload = {
            "status": "error",
            "error": str(e),
            "timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
        }
        client.publish(TOPIC_ACTION_STATUS, json.dumps(err_payload), qos=1)

    finally:
        with action_lock:
            is_busy = False

def on_connect(client, userdata, flags, rc):
    if rc == 0:
        print("[ROBOT-MQTT] Connecte au Broker Mosquitto (%s:%d)" % (MQTT_HOST, MQTT_PORT))
        client.subscribe(TOPIC_COMMAND, qos=1)
        client.subscribe("sentinel/robot/command", qos=1)
        print("[ROBOT-MQTT] Abonne aux topics : %s et sentinel/robot/command" % TOPIC_COMMAND)
    else:
        print("[ROBOT-MQTT] Echec connexion Mosquitto (code=%d)" % rc)

def on_message(client, userdata, msg):
    payload_str = str(msg.payload)
    print("[ROBOT-MQTT] Message recu sur %s : %s" % (msg.topic, payload_str))
    dry_run = False
    try:
        data = json.loads(payload_str)
        cmd = str(data.get("cmd", data.get("action", "")))
        dry_run = data.get("dry_run", False)
        if isinstance(dry_run, str):
            dry_run = dry_run.lower() in ("1", "true", "yes")
    except Exception:
        cmd = payload_str.strip()

    if cmd in ("punch", "combo", "victory", "attack", "alert"):
        t = threading.Thread(target=execute_combo_thread, args=(client, dry_run))
        t.daemon = True
        t.start()
    else:
        print("[ROBOT-MQTT] Commande inconnue : '%s'" % cmd)

def main():
    print("[ROBOT-MQTT] Demarrage du service MQTT Yanshee...")
    init_ros()

    client = mqtt.Client()
    if MQTT_USER:
        client.username_pw_set(MQTT_USER, MQTT_PASSWORD)

    import ssl
    if MQTT_PORT == 8883 or os.environ.get("MQTT_USE_TLS", "0").lower() in ("1", "true", "yes"):
        client.tls_set(cert_reqs=ssl.CERT_NONE)
        client.tls_insecure_set(True)

    client.on_connect = on_connect
    client.on_message = on_message

    client.reconnect_delay_set(min_delay=1, max_delay=30)
    client.connect(MQTT_HOST, MQTT_PORT, keepalive=60)

    try:
        client.loop_forever()
    except KeyboardInterrupt:
        print("[ROBOT-MQTT] Arret du service.")
        client.disconnect()

if __name__ == "__main__":
    main()
