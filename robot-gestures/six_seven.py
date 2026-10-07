#!/usr/bin/env python3
# coding=utf-8
"""
SENTINEL-X — Geste Mème Viral "6 - 7" (Six-Seven / La Balance)
Anime les bras et la tête du robot Yanshee pour reproduire
la balance "6 7" (mains qui pèsent alternativement de gauche à droite).
"""

import os
import sys
import time
import signal
import YanAPI

# Paramètres configurables via l'environnement
REPETITIONS = int(os.environ.get("GESTURE_REPEAT", "4"))    # Nombre de cycles (6-7)
STEP_TIME = int(os.environ.get("GESTURE_SPEED_MS", "450"))  # Durée d'un mouvement en ms
REST_ON_EXIT = True

running = True

def signal_handler(sig, frame):
    global running
    print("\n[6-7] Arrêt demandé, remise en position neutre...")
    running = False
    try:
        YanAPI.sync_play_motion(name="reset", speed="normal")
    except Exception:
        pass
    sys.exit(0)

signal.signal(signal.SIGINT, signal_handler)
signal.signal(signal.SIGTERM, signal_handler)

def init_robot():
    YanAPI.yan_api_init("127.0.0.1")
    print("[6-7] Initialisation : position stable debout...")
    YanAPI.sync_play_motion(name="reset", speed="normal")
    time.sleep(0.5)

def do_six_seven(cycles=REPETITIONS, speed_ms=STEP_TIME):
    global running
    print("[6-7] Démarrage du geste '6 - 7' (%d cycles)..." % cycles)

    # 1. Pose de départ : bras parfaitement droits et verrouillés devant (manchette)
    ready_pose = {
        "LeftShoulderFlex": 10,
        "RightShoulderFlex": 170,
        "LeftElbowFlex": 10,
        "RightElbowFlex": 170,
        "LeftShoulderRoll": 165,
        "RightShoulderRoll": 15,
        "NeckLR": 90
    }
    YanAPI.set_servos_angles(ready_pose, runtime=700)
    time.sleep(0.8)

    for i in range(1, cycles + 1):
        if not running:
            break

        # --- Phase "6" : Rotation épaule Gauche monte un peu, Droite descend un peu ---
        print("[6-7] [%d/%d] ---> SIX  (Épaule gauche HAUT / Épaule droite BAS)" % (i, cycles))
        six_pose = {
            "LeftShoulderRoll": 145,   # monte un peu
            "RightShoulderRoll": 35,   # descend un peu
            "LeftShoulderFlex": 10,    # bras droit devant
            "RightShoulderFlex": 170,  # bras droit devant
            "LeftElbowFlex": 10,       # bras droit
            "RightElbowFlex": 170,     # bras droit
            "NeckLR": 80
        }
        YanAPI.set_servos_angles(six_pose, runtime=speed_ms)
        time.sleep(speed_ms / 1000.0 + 0.05)

        if not running:
            break

        # --- Phase "7" : Rotation épaule Droite monte un peu, Gauche descend un peu ---
        print("[6-7] [%d/%d] ---> SEVEN (Épaule droite HAUT / Épaule gauche BAS)" % (i, cycles))
        seven_pose = {
            "LeftShoulderRoll": 180,   # descend un peu
            "RightShoulderRoll": 0,    # monte un peu
            "LeftShoulderFlex": 10,    # bras droit devant
            "RightShoulderFlex": 170,  # bras droit devant
            "LeftElbowFlex": 10,       # bras droit
            "RightElbowFlex": 170,     # bras droit
            "NeckLR": 100
        }
        YanAPI.set_servos_angles(seven_pose, runtime=speed_ms)
        time.sleep(speed_ms / 1000.0 + 0.05)

    print("[6-7] Geste terminé ! Retour en position neutre.")
    if REST_ON_EXIT:
        YanAPI.sync_play_motion(name="reset", speed="normal")

if __name__ == "__main__":
    init_robot()
    do_six_seven()
