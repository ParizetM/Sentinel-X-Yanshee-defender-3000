#!/usr/bin/env python3
# coding=utf-8
"""
SENTINEL-X — Routine de Patrouille Autonome (Patrol Loop)
Utilise le SDK officiel YanAPI de UBTECH Yanshee.
Fait marcher le robot avec la vraie marche fluide gauche/droite,
puis demi-tour 180°, et repete dans l'allee.
"""

import sys
import time
import signal
import YanAPI

# Configuration de la patrouille
NB_STEPS = 10           # Nombre de pas (demarche complete gauche/droite)
TURN_STEPS = 4          # Nombre de pas de rotation pour ~180°
SPEED = "fast"          # very slow, slow, normal, fast, very fast

keep_patrolling = True

def signal_handler(sig, frame):
    global keep_patrolling
    print("\n[PATROL] Interruption demandee ! Arret propre du robot...")
    keep_patrolling = False
    try:
        YanAPI.stop_play_motion()
        YanAPI.sync_play_motion(name="reset", speed="normal")
    except Exception:
        pass
    sys.exit(0)

signal.signal(signal.SIGINT, signal_handler)
signal.signal(signal.SIGTERM, signal_handler)

def patrol_loop():
    global keep_patrolling

    print("[PATROL] Initialisation du SDK YanAPI (127.0.0.1)...")
    YanAPI.yan_api_init("127.0.0.1")

    # Remettre le robot droit avant de commencer
    print("[PATROL] Position neutre de depart (reset)...")
    YanAPI.sync_play_motion(name="reset", speed="normal")
    time.sleep(1.0)

    print("[PATROL] Pret ! Demarrage de la patrouille (Ctrl+C pour stopper).")

    lap_count = 1
    while keep_patrolling:
        print("\n==========================================")
        print("[PATROL] --- TOURNEE N°%d ---" % lap_count)
        print("==========================================")

        # 1. Marche avant avec alternance naturelle pied gauche / pied droit
        print("[PATROL] Phase 1 : Marche avant fluide (%d pas)..." % NB_STEPS)
        YanAPI.sync_play_motion(
            name="walk",
            direction="forward",
            speed=SPEED,
            repeat=NB_STEPS
        )

        if not keep_patrolling:
            break

        print("[PATROL] Fin de l'allee. Pause de surveillance (1 sec)...")
        time.sleep(1.0)

        # 2. Demi-tour 180°
        print("[PATROL] Phase 2 : Demi-tour 180° (%d pas de rotation)..." % TURN_STEPS)
        YanAPI.sync_play_motion(
            name="turn around",
            direction="left",
            speed=SPEED,
            repeat=TURN_STEPS
        )

        if not keep_patrolling:
            break

        print("[PATROL] Demi-tour termine ! Pret pour le retour...")
        time.sleep(1.0)
        lap_count += 1

    print("[PATROL] Fin de patrouille. Remise en position neutre.")
    YanAPI.sync_play_motion(name="reset", speed="normal")

if __name__ == "__main__":
    patrol_loop()
