# SENTINEL-X · Yanshee Defender 3000

> Workshop national EPSI Bac+4, octobre 2026 · Groupe 7
> Elios, Benoit (Infra) · Felis, Martin, Matis (Dev)

Prototype cyber-physique de surveillance pour les micro-centrales d'AetherCorp. Un boîtier **ESP8266** mesure son environnement (température, humidité, gaz, présence) et le transmet en **MQTT sur TLS**. Une **IA de vision** (YOLO) surveille la zone et une **IA prédictive** (Isolation Forest et Random Forest) repère les dérives avant le seuil critique. Un **dashboard React** affiche tout en temps réel et pilote les alarmes. Le robot humanoïde **Yanshee** porte la caméra et riposte physiquement aux intrusions.

---

## Sommaire

1. [Architecture](#1-architecture)
2. [Contenu du dépôt](#2-contenu-du-dépôt)
3. [Réseau et adressage](#3-réseau-et-adressage)
4. [Contrat d'interface (MQTT, API)](#4-contrat-dinterface)
5. [Installation et lancement](#5-installation-et-lancement)
6. [Sécurité](#6-sécurité)
7. [Tests](#7-tests)
8. [Démo](#8-démo)
9. [Correspondance avec le sujet](#9-correspondance-avec-le-sujet)

---

## 1. Architecture

**Variante retenue** : topologie distribuée « Edge-to-Server » (variante de l'option B du sujet). Le rôle de PC Serveur Local est réparti sur des VM Proxmox. La caméra du robot Yanshee remplace la webcam USB, et cette variante a été **validée par les coachs**.

```
 ┌──────────────┐  MQTTS 8883   ┌──────────────────┐   MQTTS    ┌──────────────────┐   SQL 3306   ┌─────────────────────┐
 │ Boîtier      ├──────────────►│ Mosquitto        │◄──────────►│ API FastAPI      ├─────────────►│ VIP HAProxy         │
 │ ESP8266      │◄── cmd ───────┤ 172.16.137.4     │            │ 172.16.137.5     │              │ 172.16.137.10       │
 │ DHT22 MQ-135 │               └──┬────────────▲──┘            └──┬──────────▲────┘              │  └ Galera ×3 (.1-.3)│
 │ PIR OLED     │                  │            │                  │ HTTPS/WSS │                   └─────────────────────┘
 │ buzzer LED   │       télémétrie │            │ person_count,    ▼           │ POST /api/v1/alerts
 └──────────────┘                  ▼            │ photo, action  ┌───────────┐ │
                          ┌──────────────────┐  │                │ Dashboard │ │
                          │ IA prédictive    ├──┼────────────────┤ React     │ │
                          │ anomaly_service  │  │                └───────────┘ │
                          └──────────────────┘  │                              │
 ┌──────────────┐ MJPEG   ┌─────────────────────┴┐  MQTTS detection_robot/command  ┌──────────────┐
 │ Robot Yanshee├────────►│ IA vision YOLO26n    ├────────────────────────────────►│ Robot Yanshee│
 │ caméra :8000 │         │ 172.16.137.6         │                                 │ riposte ROS  │
 └──────────────┘         └──────────────────────┘                                 └──────────────┘
```

| # | Flux | Protocole | Protection |
|---|---|---|---|
| 1 | ESP8266 → Mosquitto (mesures, statut) | MQTT/TLS 8883 | CA embarqué dans le firmware, chaîne vérifiée, authentification |
| 2 | Mosquitto → API (ingestion) | MQTT/TLS 8883 | Authentification broker |
| 3 | API → Galera (stockage) | SQL 3306 via VIP HAProxy | Utilisateur applicatif dédié |
| 4 | Dashboard ↔ API | HTTPS + WSS (reverse proxy) | TLS |
| 5 | Dashboard → API → Mosquitto → ESP8266 (buzzer, LED) | HTTPS puis MQTTS | Journal d'audit de chaque commande |
| 6 | IA prédictive → API (alertes) | HTTPS `POST /api/v1/alerts` | Jeton API |
| 7 | Robot → IA vision (vidéo) | MJPEG HTTP 8000 | Clé API (`X-API-KEY`) |
| 8 | IA vision → Mosquitto → robot (riposte) | MQTT/TLS 8883 | CA vérifié, authentification broker |

---

## 2. Contenu du dépôt

| Dossier | Rôle | Doc |
|---|---|---|
| [`sentinel-x-firmware/`](sentinel-x-firmware/README.md) | Firmware C++ ESP8266 (PlatformIO) : capteurs, OLED, MQTT/TLS, actionneurs | câblage, topics, payloads |
| [`sentinel-api/`](sentinel-api/README.md) | API REST + WebSocket (FastAPI), ingestion MQTT, stockage Galera | routes, lancement |
| [`dashboard/`](dashboard/README.md) | Dashboard React (Vite + Recharts) | lancement, configuration |
| [`prediction_ia/`](prediction_ia/README.md) | Maintenance prédictive : Isolation Forest + Random Forest, service temps réel | modèles, métriques, démo |
| [`yanshi_new/`](yanshi_new/README.md) | Vision : YOLO26n sur le flux du robot, publication MQTT, flux annoté | config TLS, flux MJPEG |
| [`robot-stream/`](robot-stream/README.md) | Serveur caméra du robot (encodage GPU, port 8000) | |
| [`robot-mqtt/`](robot-mqtt/README.md) | Écouteur MQTT du robot : exécute la riposte | |
| [`robot-control/`](robot-control/README.md) | API HTTP de secours du robot (port 5000) | |
| [`robot-gestures/`](robot-gestures/README.md), [`robot-patrol/`](robot-patrol/README.md) | Gestes et patrouille du robot | |
| `roles/`, `inventories/`, `playbooks/`, `ansible.cfg` | Ansible : cluster Galera, Zabbix server et agents | |
| [`ARCHITECTURE_ROBOT_FLUX.md`](ARCHITECTURE_ROBOT_FLUX.md) | Flux détaillés du robot Yanshee | |
| `Documentation Infrastructure.pdf`, `Infra (ports, réseau, IP).xlsx` | Documentation infra, VLAN, matrice des ports | |
| [`livrables/`](livrables/README.md) | Dossier PDF, présentation, poster A3, script de l'oral, sources pour les régénérer | |

---

## 3. Réseau et adressage

Infrastructure sur Proxmox, segmentée en 4 VLAN (`/26`).

| VLAN | ID | Réseau | Machines |
|---|---|---|---|
| WEB | 10 | 172.16.137.0/26 | Mosquitto, API, IA YOLO |
| INFRASTRUCTURE | 20 | 172.16.137.64/26 | Cluster Galera, VIP HAProxy |
| SUPERVISION | 30 | 172.16.137.128/26 | Zabbix |
| AUTOMATISATION | 40 | 172.16.137.192/26 | Ansible |

| Machine | Nom | IP |
|---|---|---|
| Galera nœud 1 (bootstrap) | WORKSHOP-GRP7-BDD1 | 172.16.137.1 |
| Galera nœud 2 | WORKSHOP-GRP7-BDD2 | 172.16.137.2 |
| Galera nœud 3 | WORKSHOP-GRP7-BDD3 | 172.16.137.3 |
| Broker Mosquitto | WORKSHOP-GRP7-BrockerMosquitto | 172.16.137.4 |
| API + dashboard | WORKSHOP-GRP7-APIDev | 172.16.137.5 |
| IA YOLO | WORKSHOP-GRP7-YOLO | 172.16.137.6 |
| Ansible | WORKSHOP-GRP7-Ansible | 172.16.137.7 |
| Zabbix | WORKSHOP-GRP7-Zabbix | 172.16.137.8 |
| VIP HAProxy (Galera) | | 172.16.137.10 |
| Robot Yanshee | | 10.0.3.234 |

La matrice complète des ports est dans `Infra (ports, réseau, IP).xlsx`.

---

## 4. Contrat d'interface

### Topics MQTT

| Topic | Sens | Contenu |
|---|---|---|
| `sentinelx/<device>/telemetry` | ESP → serveur | Mesures JSON, 1 par seconde |
| `sentinelx/<device>/status` | ESP → serveur | `online` / `offline` (retained, Last Will) |
| `sentinelx/<device>/cmd` | serveur → ESP | Commande buzzer / LED |
| `sentinelx/<device>/anomaly` | IA prédictive → API | Indice de risque, 1 par seconde |
| `detection_robot/person_count` | IA vision → API | Nombre de personnes (texte) |
| `detection_robot/photo` | IA vision → API | JPEG de preuve (au plus 1 toutes les 10 s) |
| `detection_robot/timestamp` | IA vision → API | Horodatage ISO 8601 |
| `detection_robot/command` | IA / API → robot | `{"cmd": "punch", "dry_run": false}` |
| `detection_robot/action_status` | robot → API | `executing` / `completed` |

`<device>` vaut `esp-01` pour le boîtier, et `esp-sim` pour la simulation de secours.

**Télémétrie** (`sentinelx/esp-01/telemetry`) :

```json
{
  "device": "esp-01", "uptime_s": 742,
  "temperature": 24.6, "humidity": 48.2,
  "gas": { "raw": 312, "baseline": 290, "level": "normal" },
  "presence": false, "rssi": -61,
  "actuators": { "buzzer": "off", "led": "off" }
}
```

**Commande** (`sentinelx/esp-01/cmd`) : `{"target": "buzzer|led|all", "state": "on|off|toggle", "duration_ms": 3000}`

### Routes de l'API

Documentation interactive : `/docs` (Swagger).

| Méthode | Route | Rôle |
|---|---|---|
| POST | `/api/v1/alerts` | **Imposé par le sujet** : réception des alertes (capteurs, IA) |
| GET | `/api/v1/alerts` | Alertes récentes (filtres `level`, `source`, `acknowledged`) |
| PUT | `/api/v1/alerts/{id}/acknowledge` | Acquittement (jeton requis) |
| GET | `/api/v1/measurements` | Historique des mesures pour les courbes |
| GET | `/api/v1/telemetry/latest` | Dernière trame |
| GET | `/api/v1/status` | État du broker, de la base, des boîtiers et de l'IA |
| POST | `/api/v1/commands` | Commande buzzer / LED / robot, relayée en MQTT et journalisée |
| GET | `/api/v1/commands` | Journal d'audit des commandes |
| POST | `/api/v1/auth/login` | Obtention du jeton |
| GET | `/api/v1/camera/stream` | Flux vidéo relayé (MJPEG) |
| GET | `/api/v1/camera/photos`, `/latest_photo` | Photos d'intrusion stockées en base |
| WS | `/ws` | Temps réel : `telemetry`, `alert`, `anomaly`, `person_count`, `photo`, `robot_action` |
| GET | `/health` | Healthcheck Docker |

---

## 5. Installation et lancement

> Aucun secret n'est versionné. Chaque brique fournit un modèle `.env.example` (ou `secrets.example.h`, `vault.example.yml`) à copier puis à remplir. Les vraies valeurs se transmettent hors dépôt.

### Firmware

```bash
cd sentinel-x-firmware
cp include/secrets.example.h include/secrets.h     # Wi-Fi + identifiants broker
~/.platformio/penv/bin/pio run -t upload
~/.platformio/penv/bin/pio device monitor          # 115200 bauds
```

### API

```bash
cd sentinel-api
cp .env.production.example .env                    # renseigner clés, BDD, broker
docker compose up -d --build                       # healthcheck sur /health
```

### Dashboard

```bash
cd dashboard
cp .env.example .env
npm ci && npm run build                            # dist/ servi derrière le reverse proxy HTTPS
```

### IA prédictive

```bash
cd prediction_ia
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
python anomaly_service.py                          # lancer 60 s avant la démo
```

### IA vision

```bash
cd yanshi_new
pip install -r requirements.txt
cp .env.example .env                               # MQTT_CA_CERT = certs/ca.crt
python3 yanshi_video.py                            # ou ./deploy/install_vm.sh (service systemd)
```

### Robot Yanshee

```bash
cp .env.robot.example .env                         # puis copier sur le robot
ssh sentinel "/home/pi/start_sentinel.sh"          # caméra :8000, API :5000, écouteur MQTT
```

### Infrastructure (Ansible)

```bash
cp vault.example.yml group_vars/zabbix/vault.yml && ansible-vault encrypt group_vars/zabbix/vault.yml
ansible-playbook -i inventories/hosts.ini playbooks/deploy.yml --ask-vault-pass
```

---

## 6. Sécurité

| Domaine | Mesure |
|---|---|
| Chiffrement IoT | MQTT sur TLS 8883. Le CA est embarqué dans le firmware et la chaîne du broker est vérifiée. |
| Chiffrement applicatif | Dashboard et API en HTTPS / WSS derrière un reverse proxy |
| Authentification | Utilisateurs sur le broker, jeton Bearer / `X-API-Key` sur l'API, clé API sur les flux vidéo et le robot |
| Durcissement système | Pare-feu UFW (deny par défaut), SSH par clé uniquement (`PasswordAuthentication no`) |
| Segmentation | 4 VLAN, base de données isolée derrière une VIP HAProxy |
| Haute disponibilité | Galera 3 nœuds (quorum maintenu si un nœud tombe) |
| MCO | Zabbix (CPU, RAM, disque, disponibilité) sur toutes les VM, healthcheck Docker sur l'API |
| Secrets | `.env`, `secrets.h` et `vault.yml` hors dépôt (`.gitignore`), modèles `*.example` fournis |

Le rapport d'auto-audit et les résultats du pentest croisé figurent dans le dossier d'ingénierie (`Workshop2026-M1-G7-Dossier.pdf`).

---

## 7. Tests

| Brique | Commande | Résultat |
|---|---|---|
| API | `cd sentinel-api && pytest -q` | 13 tests |
| IA prédictive | `cd prediction_ia && python -m pytest tests` | 10 tests, dont l'équivalence direct / entraînement |
| IA vision | `cd yanshi_new && pip install -r requirements-dev.txt && pytest` | flux MJPEG, MQTT, TLS |
| Firmware | `cd sentinel-x-firmware && pio run` | compilation (RAM 39 %, flash 40 %) |
| Actionneurs | `python test_actuators_mqtt.py` | envoie de vraies commandes au boîtier via le broker |

---

## 8. Démo

1. Le boîtier est sous tension et l'OLED affiche son IP, `MQTT: connecte`. Attendre 60 s de chauffe gaz.
2. Les courbes bougent en temps réel sur le dashboard.
3. Chauffer lentement le DHT22 et approcher du gel hydroalcoolique : la **jauge de risque IA** dépasse 1 et une alerte `ia_anomaly` arrive **alors que l'OLED affiche encore `normal`**.
4. Une personne entre dans le champ du robot : YOLO la détecte, une photo et une alerte d'intrusion apparaissent, et le robot riposte.
5. Les boutons buzzer / LED du dashboard déclenchent les alarmes du boîtier en moins d'une seconde.
6. Preuves de sécurité : capture Wireshark (MQTT illisible), `ufw status`, connexion SSH par mot de passe refusée.

**Plan de secours** (boîtier ou Wi-Fi en panne) : `python prediction_ia/simulate.py --scenario demo --minutes 20 --onset 120 --publish --speed 5` publie un faux boîtier `esp-sim`.

---

## 9. Correspondance avec le sujet

| Exigence du sujet | Réponse |
|---|---|
| Firmware C++ ESP8266, capteurs, OLED, payloads | `sentinel-x-firmware/` |
| Chiffrement de bout en bout (MQTTS / HTTPS) | TLS 8883 avec CA vérifié, HTTPS sur l'API |
| API REST / WebSocket, `POST /api/v1/alerts` | `sentinel-api/` |
| Dashboard : courbes, statut, flux caméra, commandes | `dashboard/` |
| Vision IA temps réel, images à 640 px | `yanshi_new/` (YOLO26n, `imgsz=640`) |
| Maintenance prédictive sans `if temp > 40` | `prediction_ia/` (Isolation Forest + Random Forest) |
| Conteneurs, BDD, broker | Docker Compose (API, Mosquitto), MariaDB Galera 3 nœuds |
| Isolation réseau, plan d'adressage | 4 VLAN, voir §3 |
| Hardening : pare-feu, SSH par clé, privilèges | Voir §6 |
| MCO : CPU, RAM, logs | Zabbix |
| Dépôt sans secret | `.gitignore` + modèles `*.example` |
