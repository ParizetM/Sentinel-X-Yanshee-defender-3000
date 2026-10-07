# SENTINEL-X — Architecture Globale & Cartographie des Flux du Robot Yanshee

Ce document détaille l'ensemble des fonctionnalités, du matériel, des services et des flux réseau/MQTT échangés entre le **Robot UBTECH Yanshee (Edge Node)**, l'**IA (YOLO)**, le **Broker Mosquitto** et le reste de l'infrastructure **Sentinel-X**.

---

## 1. Vue d'Ensemble de l'Écosystème

Le robot Yanshee joue le rôle de **Sentinelle Cyber-Physique Avancée** sur la table d'opération. Il assure :
1. **La captation vidéo frontale** de la zone surveillée.
2. **L'exécution physique des contre-mesures** (mouvements expressifs et frappes physiques dissuasives).
3. **La communication temps réel sécurisée** avec le cœur du système d'information via Mosquitto (MQTT).

```
┌────────────────────────────────────────────────────────────────────────────────────────┐
│                                INFRASTRUCTURE SENTINEL-X                               │
│                                                                                        │
│   ┌────────────────────────────────┐                 ┌─────────────────────────────┐   │
│   │        VM BROKER MOSQUITTO     │                 │        VM SERVEUR IA        │   │
│   │         172.16.137.4:8883      │                 │         172.16.137.6        │   │
│   │                                │                 │                             │   │
│   │   • Bus d'événements central   │◄─── Alertes ────┤   • YOLO26n (Détection)     │   │
│   │   • Télémétrie & Alertes       │─── Ordres ─────►│   • Inférence temps réel    │   │
│   └────────────────┬───────────────┘                 └──────────────▲──────────────┘   │
│                    │                                                │                  │
│       Ordres MQTT  │  Statut MQTT                                   │                  │
│       (JSON)       │  (JSON)                                        │ Flux Vidéo       │
│                    ▼                                                │ (MJPEG 25 FPS)   │
│   ┌─────────────────────────────────────────────────────────────────┴──────────────┐   │
│   │                           ROBOT HUMANOÏDE YANSHEE                              │   │
│   │                               IP: 10.0.3.234                                   │   │
│   │                                                                                │   │
│   │   [Port 8000] : fast_camera.py (GPU VideoCore IV) ─────────────────────────────┘   │
│   │   [Port 5000] : punch_api.py (API HTTP de secours / Interface Web)                 │
│   │   [Client]    : yanshee_mqtt_listener.py (Abonné à Mosquitto)                      │
│   │   [Moteurs]   : Contrôleur STM32 / ROS /play_motion_hts                            │
│   └────────────────────────────────────────────────────────────────────────────────┘   │
└────────────────────────────────────────────────────────────────────────────────────────┘
```

---

## 2. Ce que fait le Robot en Local

### A. Vision & Streaming Matériel (GPU)
* **Composant :** Caméra HD située dans la tête du robot (`/dev/video0`).
* **Service :** `fast_camera.py` (écoute sur le port `8000`).
* **Optimisations :** 
  * Encodage direct par le GPU VideoCore IV du Raspberry Pi (zéro surcharge processeur).
  * Résolution 640x480 à 25 FPS, qualité 60% (conforme aux exigences de latence < 100 ms).
  * Zéro buffer de cache pour une réactivité instantanée.
* **Sécurité :** Accès conditionné par la clé d'API (`sentinel-x-secret-key-2026`).

### B. Mouvements & Contrôle Moteur (ROS Kinetic)
* **Actionneurs :** 17 servomoteurs numériques intelligents pilotés par le microcontrôleur STM32 via ROS.
* **Service :** `yanshee_mqtt_listener.py` (ou `punch_api.py`).
* **Chorégraphie Sentinelle exécutée :**
  1. **Coucou des deux bras** (`Victory`) : Le robot lève ses 2 bras en l'air pour signifier l'interception (~4,7 s).
  2. **Direct du Gauche** (`LeftHitForward`) : Coup de poing sec du bras gauche vers l'avant (~2,6 s).
  3. **Direct du Droit** (`RightHitForward`) : Coup de poing sec du bras droit vers l'avant (~2,6 s).
* **Mode Simulation (`dry_run`) :**
  * Si `dry_run = true` : le robot valide l'ordre, loggue l'action et notifie le réseau, sans solliciter physiquement les servos (idéal pour les tests ou économiser la batterie).
  * Si `dry_run = false` : exécution matérielle complète.

---

## 3. Cartographie Complète des Flux Réseau

### 3.1 Flux Vidéo (HTTP Streaming Dédié)
La vidéo haute fréquence (25 FPS) ne passe pas par MQTT pour éviter d'engorger le broker.

| Émetteur | Récepteur | Protocole / Port | URL / Ressource | Payload | Description |
| :--- | :--- | :--- | :--- | :--- | :--- |
| **Robot** (`10.0.3.234`) | **VM IA** (`172.16.137.6`) | HTTP / 8000 | `/stream.mjpg?key=sentinel-x-secret-key-2026` | Trame continue multipart JPEG | Flux vidéo temps réel analysé par YOLO |
| **Robot** (`10.0.3.234`) | **Navigateur / React** | HTTP / 8000 | `/?key=sentinel-x-secret-key-2026` | HTML + flux MJPEG | Visualisation directe de la caméra |

---

### 3.2 Flux Événements & Commandes (Broker Mosquitto `172.16.137.4:8883`)
Tous les signaux décisionnels, alertes et déclenchements transitent par Mosquitto avec authentification (`admin` / `Epsi1234.!`).

```
  VM IA (YOLO)                     BROKER MOSQUITTO                   ROBOT YANSHEE
       │                                  │                                 │
       │─── detection_robot/command ─────►│                                 │
       │    {"cmd":"punch","dry_run":0}   │─── detection_robot/command ────►│ (Reçoit l'ordre)
       │                                  │                                 │ ─── Exécute Victory + Punchs
       │                                  │◄── detection_robot/action_status│ (Publie statut "executing")
       │                                  │                                 │ (Termine les mouvements)
       │                                  │◄── detection_robot/action_status│ (Publie statut "completed")
       │                                  │                                 │
       │─── detection_robot/person_count ─►│ (Pour Dashboard / BDD)          │
       │─── detection_robot/photo ────────►│ (Cliché JPEG de preuve)         │
       │─── detection_robot/timestamp ────►│ (Horodatage ISO 8601)          │
```

#### Détail des Topics MQTT :

| Topic MQTT | Direction | Publié par | Consommé par | Format Payload | Rôle / Signification |
| :--- | :--- | :--- | :--- | :--- | :--- |
| **`detection_robot/command`** | In | IA YOLO | **Robot Yanshee** | JSON : `{"cmd": "punch", "dry_run": false}` | **Donne l'ordre au robot de frapper** dès qu'un humain est vu |
| **`detection_robot/action_status`** | Out | **Robot Yanshee** | Dashboard / BDD | JSON : `{"status": "executing"}` ou `{"status": "completed"}` | **Indique l'avancement physique** des actions du robot |
| **`detection_robot/person_count`** | Out | IA YOLO | Dashboard / API | Texte : `"1"`, `"2"`, `"0"` | Nombre d'intrus présents dans la zone |
| **`detection_robot/photo`** | Out | IA YOLO | BDD / Dashboard | Binaire JPEG | **Preuve visuelle d'intrusion** (1 capture max toutes les 10s) |
| **`detection_robot/timestamp`** | Out | IA YOLO | BDD / Dashboard | Texte ISO 8601 | Heure exacte de l'alerte |
| **`detection_robot/action`** | Out | IA YOLO | API Dev / Logs | JSON : `{"action": "punch", ...}` | Journalisation de l'événement côté IA |

---

### 3.3 Flux HTTP de Secours / Administration Manuelle
Conservé en cas d'indisponibilité du broker MQTT pour tester directement le robot.

| Émetteur | Récepteur | Protocole / Port | URL | Paramètres | Description |
| :--- | :--- | :--- | :--- | :--- | :--- |
| **Opérateur** | **Robot** (`10.0.3.234`) | HTTP / 5000 | `/punch` | `?key=...&dry_run=0` | Déclenchement manuel direct de la frappe |
| **Opérateur** | **Robot** (`10.0.3.234`) | HTTP / 5000 | `/` | `?key=...` | Interface Web tactile de commande |

---

## 4. Cycle de Vie & Résumé des Services sur le Robot

Tous les services du robot sont centralisés et lancés en une seule commande via `/home/pi/start_sentinel.sh` :

1. **`fast_camera.py` (PID background, Port 8000) :** Maintient le serveur vidéo GPU ouvert et prêt à diffuser.
2. **`yanshee_mqtt_listener.py` (PID background, Client MQTT) :** Écoute `detection_robot/command` sur `172.16.137.4` et transmet les ordres à ROS.
3. **`punch_api.py` (PID background, Port 5000) :** Maintient l'interface de secours HTTP.

---

## 5. Synthèse de Conformité au Cahier des Charges Sentinel-X

* **Cybersécurité & Durcissement :** Clé d'API asymétrique sur tous les endpoints, authentification obligatoire sur le broker Mosquitto, accès SSH durci par clé Ed25519 sans mot de passe.
* **MCO & Résilience Réseau :** Pas de saturation du bus MQTT par de la vidéo 25 FPS ; seuls les événements textuels et les snapshots cadencés (10s) transitent sur le broker.
* **Interconnexion Totale :** Liaison prouvée entre la captation Edge (Robot), le serveur de calcul IA (YOLO VM), le broker de centralisation (Mosquitto) et le stockage/supervision.
