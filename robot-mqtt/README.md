# Sentinel-X — Contrôle Moteur Robot via Mosquitto (MQTT)

Ce module permet de piloter le robot **Yanshee** à 100% via le broker central **Mosquitto** (`172.16.137.4`), sans nécessiter d'appels HTTP directs.

---

## 1. Architecture des Échanges MQTT

```
┌─────────────────────────────────┐                 ┌─────────────────────────────────┐
│     IA YOLO (yanshi_video.py)   │                 │      BROKER MOSQUITTO (INFRA)   │
│                                 │                 │         172.16.137.4:8883       │
│  Détection d'un intrus          │                 │                                 │
│  Publie l'ordre de frappe ──────┼─── MQTT (QoS 1) ┼─► Topic :                       │
│  {"cmd": "punch",               │                 │  detection_robot/command        │
│   "dry_run": false}             │                 │                 │               │
└─────────────────────────────────┘                 └─────────────────┼───────────────┘
                                                                      │
                                                    ┌─────────────────┼───────────────┐
                                                    │                 ▼               │
                                                    │        ROBOT YANSHEE            │
                                                    │  (yanshee_mqtt_listener.py)     │
                                                    │                                 │
                                                    │  1. Réception de la commande    │
                                                    │  2. Exécution ROS :             │
                                                    │     • Coucou (Victory)          │
                                                    │     • Punch Gauche              │
                                                    │     • Punch Droit               │
                                                    │  3. Retour de statut ───────────┼──► Topic :
                                                    │     {"status": "completed"}     │    detection_robot/action_status
                                                    └─────────────────────────────────┘
```

---

## 2. Configuration & Identifiants du Broker

* **Hôte :** `172.16.137.4`
* **Port :** `8883` (SSL/TLS)
* **Utilisateur :** `admin`
* **Mot de passe :** défini par `MQTT_PASSWORD` dans le `.env` (hors dépôt)

---

## 3. Topics MQTT Utilisés

| Topic | Sens | Payload JSON | Description |
| :--- | :--- | :--- | :--- |
| **`detection_robot/command`** | In (Robot) | `{"cmd": "punch", "dry_run": false}` | Déclenche le combo complet |
| **`detection_robot/action_status`** | Out (Robot) | `{"status": "executing"}` ou `{"status": "completed"}` | Notifie l'avancement de l'action |

---

## 4. Démarrage du Service sur le Robot

Le script `yanshee_mqtt_listener.py` est intégré dans le lanceur général du robot.

En SSH sur le robot (`ssh sentinel`) :
```bash
./start_sentinel.sh
```
Ce script démarre automatiquement :
1. Le flux caméra vidéo matériel (Port 8000).
2. L'API HTTP de secours (Port 5000).
3. Le listener MQTT connecté à Mosquitto.
