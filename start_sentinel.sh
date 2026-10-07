#!/bin/bash
# ============================================================
# SENTINEL-X — Démarrage de tous les services du Robot
# ============================================================

# Chargement automatique des variables d'environnement (.env)
if [ -f "$(dirname "$0")/.env" ]; then
    set -a
    source "$(dirname "$0")/.env"
    set +a
elif [ -f /home/pi/.env ]; then
    set -a
    source /home/pi/.env
    set +a
fi

# Nettoyage des ports occupés et anciens démons
fuser -k 5000/tcp 8000/tcp 2>/dev/null || true
pkill -f yanshee_mqtt_listener.py 2>/dev/null || true

# Configuration ROS Kinetic & Python Yanshee
export ROS_MASTER_URI=http://localhost:11311
export ROS_IP=127.0.0.1
source /opt/ros/kinetic/setup.bash
export PYTHONPATH=/opt/yanshee/lib/python2.7/dist-packages:/opt/pose_imitation/lib/python2.7/dist-packages:$PYTHONPATH

# 1. API HTTP locale (Secours / Port 5000)
nohup python2 /home/pi/punch_api.py > /home/pi/punch_api.log 2>&1 &

# 2. Caméra GPU directe (Port 8000)
nohup python2 /opt/yanshee/lib/vision/fast_camera.py > /home/pi/fast_camera.log 2>&1 &

# 3. Écouteur MQTT centralisé (Port 8883 / TLS)
nohup python2 -u /home/pi/yanshee_mqtt_listener.py > /home/pi/mqtt_listener.log 2>&1 &

echo "[SENTINEL-X] Tous les services ont démarré avec succès !"
echo "  • Caméra MJPEG GPU : http://10.0.3.234:8000/stream.mjpg?key=${SENTINEL_API_KEY}"
echo "  • API REST Punch   : http://10.0.3.234:5000/punch"
echo "  • Écouteur MQTT    : Broker ${MQTT_BROKER_HOST}:${MQTT_BROKER_PORT}"
