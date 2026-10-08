#!/bin/bash
# ============================================================
# SENTINEL-X — Lancement du geste mème "6 - 7"
# ============================================================

if [ -f "$(dirname "$0")/.env" ]; then
    set -a
    source "$(dirname "$0")/.env"
    set +a
elif [ -f /home/pi/.env ]; then
    set -a
    source /home/pi/.env
    set +a
fi

python3 /home/pi/six_seven.py
