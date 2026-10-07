# SENTINEL-X — Plan d'Action & Spécifications Détaillées : API REST Python (EPIC 5)

> **Projet :** SENTINEL-X — Workshop National 2026 (BAC+4)  
> **Composant :** API REST Backend & Ingestion MQTT  
> **Responsable :** Martin Parizet (Dev API)  
> **Tickets Jira associés :** KAN-8 (Epic), KAN-31, KAN-32, KAN-33, KAN-35, KAN-36, KAN-44, KAN-45, KAN-46  
> **Branche Git :** `features/api-rest`

---

## 1. Contexte & Rôle de l'API REST dans le Système

L'API REST Python constitue le **nœud d'intégration central** du système SENTINEL-X. Elle fait la passerelle entre :
1. **L'IoT (ESP8266 de table) :** Réception de la télémétrie capteurs (Température, Humidité DHT22, Gaz MQ-2, Détection PIR) via MQTT MQTTS (port 8883 TLS).
2. **L'IA (VM YOLO / OpenCV & Anomalies) :** Réception des alertes critiques de franchissement / anomalies cinétiques.
3. **Le Robot Yanshee :** Envoi des ordres de riposte/mouvement et suivi des statuts d'action.
4. **La Base de Données (Galera / MariaDB) :** Persistance de l'historique haute fréquence et des journaux d'audit.
5. **Le Dashboard Web (React / Vue) :** Consultation temps réel des courbes, du statut du boîtier et déclenchement manuel des actionneurs (Buzzer, LED, Robot).
6. **L'Équipe Pentest / Sécurité :** Résistance aux attaques (injections, falsification de données, brute force).

```
┌────────────────────────────────────────────────────────────────────────┐
│                              SENTINEL-X                                │
│                                                                        │
│   ┌───────────────┐     MQTTS (8883)     ┌─────────────────────────┐   │
│   │ ESP8266 IoT   │─────────────────────►│                         │   │
│   │ Capteurs      │                      │                         │   │
│   └───────────────┘                      │                         │   │
│                                          │      API REST PYTHON    │   │
│   ┌───────────────┐  POST /api/v1/alerts │        (FASTAPI)        │   │
│   │ Serveur IA    │─────────────────────►│                         │   │
│   │ (YOLO/Anomal.)│                      │  • Background Worker    │   │
│   └───────────────┘                      │    MQTT Listener        │   │
│                                          │  • Schémas Pydantic     │   │
│   ┌───────────────┐   HTTPS / REST / WS  │  • Sécurité / Auth      │   │
│   │ Dashboard Web │◄────────────────────►│                         │   │
│   │ Supervision   │                      └────────────┬────────────┘   │
│   └───────────────┘                                   │ SQL (Async)    │
│                                                       ▼                │
│                                          ┌─────────────────────────┐   │
│                                          │  Cluster MariaDB Galera │   │
│                                          │    172.16.137.x:3306    │   │
│                                          └─────────────────────────┘   │
└────────────────────────────────────────────────────────────────────────┘
```

---

## 2. Stack Technique Retenue

| Élément | Choix Technologique | Justification |
| :--- | :--- | :--- |
| **Framework Web** | **FastAPI** (Python 3.11+) | Asynchrone natif, ultra-performant, documentation Swagger auto (`/docs`). |
| **Validation des données** | **Pydantic v2** | Typage strict, validation automatique des payloads JSON (recommandé pour le pentest). |
| **Client MQTT** | **aiomqtt** (ou `paho-mqtt` asynchrone) | Permet d'écouter les topics MQTT directement dans la boucle d'événements FastAPI (`lifespan`). |
| **ORM / Accès BDD** | **SQLAlchemy 2.0 (async)** + **aiomysql** | Pooling de connexions, requêtes paramétrées anti-injections SQL, compatible MariaDB Galera. |
| **Authentification** | **HTTP Bearer (API Token / JWT)** | Simplicité de mise en œuvre, sécurisé, compatible Dashboard & scripts IA. |
| **Serveur ASGI** | **Uvicorn** avec support TLS | Capable de servir directement en HTTPS ou derrière le reverse proxy Nginx. |
| **Conteneurisation** | **Docker & Dockerfile multi-stage** | Déploiement immédiat dans le `docker-compose.yml` de l'équipe Infra. |

---

## 3. Cartographie Détaillée des Endpoints (Contrat d'API)

### 3.1 Point d'entrée Obligatoire : `POST /api/v1/alerts` (KAN-32)
* **Description :** Réceptionne les alertes émises par l'ESP8266, l'IA (détection humaine, corrélation anormale gaz/température) ou un opérateur.
* **Headers :** `Content-Type: application/json`, `Authorization: Bearer <TOKEN>` (ou `X-API-Key`).
* **Format Payload attendu :**
```json
{
  "source": "ia_vision",             // "sensor_esp8266" | "ia_vision" | "ia_anomaly" | "manual"
  "device_id": "sentinel-01",
  "alert_type": "human_intrusion",    // "gas_leak" | "temperature_spike" | "human_intrusion" | "anomaly"
  "severity": "critical",            // "low" | "medium" | "high" | "critical"
  "value": 2,                        // valeur numérique ou seuil atteint
  "message": "Intrusion détectée : 2 personnes identifiées dans le périmètre",
  "metadata": {
    "confidence": 0.89,
    "photo_ref": "photo_20261007_104800.jpg"
  }
}
```
* **Codes retour HTTP :**
  * `201 Created` : Alerte validée et persistée en BDD.
  * `400 Bad Request` : Format invalide.
  * `422 Unprocessable Entity` : Schéma JSON non conforme.
  * `401 Unauthorized` : Clé d'API absente ou invalide.

---

### 3.2 Ingestion & Télémétrie Capteurs (KAN-31, KAN-33)
* **Background Worker MQTT (KAN-31) :**
  * Écoute le topic `sentinelx/+/telemetry`
  * Format consommé (produit par l'ESP8266) :
    ```json
    {
      "device": "sentinel-01",
      "uptime_s": 120,
      "temperature": 23.4,
      "humidity": 45.2,
      "gas": { "raw": 320, "baseline": 300, "level": "normal" },
      "presence": true,
      "rssi": -65,
      "actuators": { "buzzer": "off", "led": "off" }
    }
    ```
  * Enregistrement en base de données MariaDB.

* **Endpoints de lecture (KAN-33) :**
  * **`GET /api/v1/telemetry/latest`** : Dernière mesure de chaque capteur (pour rafraîchissement rapide du dashboard).
  * **`GET /api/v1/telemetry/history`** :
    * Query params : `device_id`, `start_date`, `end_date`, `metric` (temp, humidity, gas), `limit` (défaut 100, max 1000).
    * Permet au dashboard d'afficher les graphiques temporels.
  * **`GET /api/v1/status`** : État de santé global du boîtier (dernière émission MQTT, statut `online`/`offline`).
  * **`GET /api/v1/alerts`** : Historique des alertes avec filtre par sévérité et statut d'acquittement.
  * **`PUT /api/v1/alerts/{id}/acknowledge`** : Acquittement d'une alerte par un opérateur.

---

### 3.3 Commande des Actionneurs (KAN-35)
* **`POST /api/v1/actuators/command`** :
  * Payload :
    ```json
    {
      "target": "esp8266",          // "esp8266" ou "yanshee"
      "device_id": "sentinel-01",
      "command": {
        "buzzer": "on",             // "on" | "off"
        "led": "on"                 // "on" | "off"
      }
    }
    ```
  * Ou pour le Robot Yanshee :
    ```json
    {
      "target": "yanshee",
      "command": {
        "action": "punch",          // "punch" | "patrol" | "standby"
        "dry_run": false
      }
    }
    ```
  * L'API publie immédiatement l'ordre sur le topic MQTT approprié (`sentinelx/{id}/cmd` ou `detection_robot/command`) et trace la commande dans la table d'audit.

---

### 3.4 Sécurité & Durcissement (KAN-36)
* Authentification via Header `Authorization: Bearer <TOKEN>` ou `X-API-Key`.
* Configuration CORS sécurisée (origines restreintes au dashboard).
* Rate limiting (ex: 60 requêtes / minute par IP pour éviter les attaques DoS).
* Chiffrement TLS / HTTPS activé.

---

## 4. Modèle de Données (Base de Données Galera/MariaDB)

### Table `telemetry`
```sql
CREATE TABLE IF NOT EXISTS telemetry (
    id BIGINT AUTO_INCREMENT PRIMARY KEY,
    device_id VARCHAR(64) NOT NULL,
    recorded_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    temperature FLOAT NULL,
    humidity FLOAT NULL,
    gas_raw INT NULL,
    gas_baseline INT NULL,
    gas_level VARCHAR(32) NULL,
    presence BOOLEAN NOT NULL DEFAULT FALSE,
    rssi INT NULL,
    buzzer_state VARCHAR(8) DEFAULT 'off',
    led_state VARCHAR(8) DEFAULT 'off',
    INDEX idx_device_time (device_id, recorded_at)
) ENGINE=InnoDB;
```

### Table `alerts`
```sql
CREATE TABLE IF NOT EXISTS alerts (
    id BIGINT AUTO_INCREMENT PRIMARY KEY,
    device_id VARCHAR(64) NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    source VARCHAR(64) NOT NULL,
    alert_type VARCHAR(64) NOT NULL,
    severity VARCHAR(32) NOT NULL,
    value FLOAT NULL,
    message TEXT NOT NULL,
    metadata JSON NULL,
    acknowledged BOOLEAN DEFAULT FALSE,
    acknowledged_at TIMESTAMP NULL,
    INDEX idx_alerts_time (created_at),
    INDEX idx_alerts_severity (severity)
) ENGINE=InnoDB;
```

### Table `actuator_audit_logs`
```sql
CREATE TABLE IF NOT EXISTS actuator_audit_logs (
    id BIGINT AUTO_INCREMENT PRIMARY KEY,
    triggered_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    target VARCHAR(32) NOT NULL,
    device_id VARCHAR(64) NOT NULL,
    command_payload JSON NOT NULL,
    user_identity VARCHAR(128) DEFAULT 'dashboard_user'
) ENGINE=InnoDB;
```

---

## 5. Architecture Logicielle du Projet (`sentinel-api/`)

```
sentinel-api/
├── Dockerfile                  # Image Docker légère (python:3.11-slim)
├── requirements.txt            # Dépendances (fastapi, uvicorn, pydantic, aiomysql, sqlalchemy, aiomqtt...)
├── .env.example                # Variables d'environnement (BDD, MQTT, Clés API)
├── app/
│   ├── __init__.py
│   ├── main.py                 # Point d'entrée FastAPI, cycle de vie (lifespan)
│   ├── config.py               # Configuration centralisée (Pydantic Settings)
│   ├── database.py             # Session SQLAlchemy async & engine
│   ├── mqtt_client.py          # Gestionnaire de connexion MQTT & subscriptions
│   ├── models/                 # Modèles de base de données (SQLAlchemy)
│   │   ├── __init__.py
│   │   ├── telemetry.py
│   │   ├── alert.py
│   │   └── audit.py
│   ├── schemas/                # Schémas de validation (Pydantic)
│   │   ├── __init__.py
│   │   ├── alert.py            # Schéma du POST /api/v1/alerts
│   │   ├── telemetry.py        # Schémas GET telemetry
│   │   └── actuator.py         # Schéma POST actuator
│   ├── routers/                # Routes de l'API
│   │   ├── __init__.py
│   │   ├── alerts.py           # /api/v1/alerts
│   │   ├── telemetry.py        # /api/v1/telemetry
│   │   ├── actuators.py        # /api/v1/actuators
│   │   └── status.py           # /api/v1/status & /health
│   └── security/               # Sécurité & middlewares
│       ├── __init__.py
│       └── auth.py             # Vérification de token / API Key
└── tests/
    ├── test_alerts.py          # Tests unitaires du POST /api/v1/alerts
    ├── test_telemetry.py       # Tests des requêtes GET
    └── test_actuators.py       # Tests d'envoi de commandes
```

---

## 6. Planning des Étapes de Réalisation

```
Étape 1 : Initialisation & Socle de Base
  │ • Création de la structure sentinel-api/
  │ • requirements.txt, Dockerfile, .env.example
  │ • Configuration Pydantic & initialisation FastAPI
  ▼
Étape 2 : Modèles & Base de Données
  │ • Configuration de la connexion asynchrone SQLAlchemy / aiomysql
  │ • Définition des tables (telemetry, alerts, audit)
  │ • Script d'auto-création des tables
  ▼
Étape 3 : Implémentation du POST /api/v1/alerts (Point obligatoire)
  │ • Définition du schéma Pydantic strict
  │ • Routeur alerts.py avec codes HTTP 201/400/422
  │ • Tests unitaires associés
  ▼
Étape 4 : Ingestion MQTT en tâche de fond (Lifespan)
  │ • Client MQTT asynchrone connecté au broker (TLS optionnel / direct)
  │ • Décodage des payloads sentinelx/+/telemetry
  │ • Insertion automatique en BDD
  ▼
Étape 5 : Endpoints de Lecture & Commandes Actionneurs
  │ • GET /api/v1/telemetry/latest & /history avec filtres temporels
  │ • GET /api/v1/status (santé boîtier)
  │ • POST /api/v1/actuators/command -> publication MQTT
  ▼
Étape 6 : Sécurisation & Durcissement Pentest
  │ • Middleware Auth (API Key / Bearer)
  │ • Validation contre attaques et CORS
  │ • Documentation Swagger (/docs) validée
```
