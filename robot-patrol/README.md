# Sentinel-X — Routine de Patrouille en Allée (Robot Patrol)

Ce script autonome permet de faire patrouiller le robot **Yanshee** dans une allée :
1. **Marche avant :** Avance de 10 pas consécutifs en foulée complète gauche/droite via `YanAPI` (`walk forward`).
2. **Pause d'observation :** Scan visuel de la zone (1 seconde).
3. **Demi-tour 180° :** Effectue une rotation sur place (`turn around left`).
4. **Boucle :** Répète la marche dans l'autre sens en continu.

---

## 1. Comment Lancer la Patrouille

### Option A : Directement depuis votre Mac (en 1 ligne)
```bash
ssh sentinel "/home/pi/run_patrol.sh"
```
*(Faites simplement `Ctrl + C` dans votre terminal pour interrompre proprement la patrouille à tout moment).*

### Option B : En étant connecté sur le Robot en SSH
```bash
ssh sentinel
./run_patrol.sh
```

---

## 2. Personnalisation des Paramètres (`patrol.py`)

Vous pouvez ajuster les constantes en tête du script selon la taille de votre allée :

* `NB_STEPS = 10` : Nombre de pas en ligne droite avant de faire demi-tour.
* `TURN_STEPS = 4` : Nombre de pas de rotation nécessaires pour faire un demi-tour complet à 180°.
* `SPEED = "fast"` : Vitesse de déplacement (`slow`, `normal`, `fast`, `very fast`).
