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
import threading
import YanAPI

# Paramètres configurables via l'environnement (200 ms est la vitesse maximale absolue supportée par le matériel)
REPETITIONS = int(os.environ.get("GESTURE_REPEAT", "8"))    # Nombre de cycles (6-7)
STEP_TIME = max(200, int(os.environ.get("GESTURE_SPEED_MS", "200")))  # 200 ms = vitesse max hardware Yanshee
TTS_PHRASE = os.environ.get("GESTURE_TTS", "Six seven")     # Phrase prononcée en anglais
REST_ON_EXIT = True

running = True

def speak_tts_async(phrase=TTS_PHRASE):
    """Prononce la phrase en anglais en arrière-plan sans bloquer les moteurs."""
    def _run():
        try:
            print("[6-7] [TTS] Prononciation anglaise : '%s'..." % phrase)
            YanAPI.start_voice_tts(tts=phrase, interrupt=True)
        except Exception as e:
            print("[6-7] [TTS] Warning:", e)
    t = threading.Thread(target=_run)
    t.daemon = True
    t.start()

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

    # 1. Pose de départ : bras 100% droits et tendus devant lui (coudes calibrés à 90)
    ready_pose = {
        "LeftShoulderFlex": 10,
        "RightShoulderFlex": 170,
        "LeftElbowFlex": 90,
        "RightElbowFlex": 90,
        "LeftShoulderRoll": 165,
        "RightShoulderRoll": 15,
        "NeckLR": 90
    }
    YanAPI.set_servos_angles(ready_pose, runtime=700)
    time.sleep(0.8)

    # Démarrage de la voix TTS en anglais au lancement de l'oscillation
    speak_tts_async(TTS_PHRASE)

    for i in range(1, cycles + 1):
        if not running:
            break

        # Relance de la voix à mi-parcours pour accompagner la cadence
        if i == (cycles // 2) + 1:
            speak_tts_async(TTS_PHRASE)

        # --- Phase "6" : Bras Gauche HAUT, Bras Droit BAS (opposition de phase) ---
        print("[6-7] [%d/%d] ---> SIX  (Bras gauche HAUT / Bras droit BAS)" % (i, cycles))
        six_pose = {
            "LeftShoulderRoll": 145,   # Gauche monte
            "RightShoulderRoll": 0,    # Droit descend
            "LeftShoulderFlex": 10,    # bras tendu devant
            "RightShoulderFlex": 170,  # bras tendu devant
            "LeftElbowFlex": 90,       # coude 100% droit
            "RightElbowFlex": 90,      # coude 100% droit
            "NeckLR": 80
        }
        YanAPI.set_servos_angles(six_pose, runtime=speed_ms)
        time.sleep(speed_ms / 1000.0 + 0.02)

        if not running:
            break

        # --- Phase "7" : Bras Droit HAUT, Bras Gauche BAS (opposition de phase) ---
        print("[6-7] [%d/%d] ---> SEVEN (Bras droit HAUT / Bras gauche BAS)" % (i, cycles))
        seven_pose = {
            "LeftShoulderRoll": 180,   # Gauche descend
            "RightShoulderRoll": 35,   # Droit monte
            "LeftShoulderFlex": 10,    # bras tendu devant
            "RightShoulderFlex": 170,  # bras tendu devant
            "LeftElbowFlex": 90,       # coude 100% droit
            "RightElbowFlex": 90,      # coude 100% droit
            "NeckLR": 100
        }
        YanAPI.set_servos_angles(seven_pose, runtime=speed_ms)
        time.sleep(speed_ms / 1000.0 + 0.02)

    print("[6-7] Geste terminé ! Retour en position neutre.")
    if REST_ON_EXIT:
        YanAPI.sync_play_motion(name="reset", speed="normal")

if __name__ == "__main__":
    init_robot()
    do_six_seven()
