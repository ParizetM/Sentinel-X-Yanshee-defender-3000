# SENTINEL-X — Backend API REST Python (EPIC 5)

API REST asynchrone haute performance et moteur d'ingestion MQTT pour le projet de surveillance cyber-physique **SENTINEL-X**.

---

## 🌟 Fonctionnalités Implémentées

* **Point d'entrée obligatoire `POST /api/v1/alerts` ([KAN-32](file:///Users/martinp/Documents/Projets/School/SENTINEL%20-%20X/Jira.xml)) :**
  * Validation stricte des données d'alertes entrantes (schéma Pydantic).
  * Codes retours HTTP conformes : `201 Created`, `400 Bad Request`, `422 Unprocessable Entity`, `401 Unauthorized`.
* **Moteur d'ingestion MQTT ([KAN-31](file:///Users/martinp/Documents/Projets/School/SENTINEL%20-%20X/Jira.xml)) :**
  * Connexion au broker Mosquitto (port 8883 MQTTS / TLS).
  * Abonnement automatique à `sentinelx/+/telemetry` et insertion en BDD (MariaDB Galera / SQLite).
  * Détection automatique des pics de gaz critique et levée d'alertes associées.
* **Supervision & Télémétrie ([KAN-33](file:///Users/martinp/Documents/Projets/School/SENTINEL%20-%20X/Jira.xml)) :**
  * `GET /api/v1/telemetry/latest` : dernière trame capteurs en temps réel.
  * `GET /api/v1/telemetry/history` : séries chronologiques pour les courbes du Dashboard.
  * `GET /api/v1/status` : état de connectivité du broker MQTT, de la base de données et des boîtiers.
* **Contrôle Réactif des Actionneurs ([KAN-35](file:///Users/martinp/Documents/Projets/School/SENTINEL%20-%20X/Jira.xml)) :**
  * `POST /api/v1/actuators/command` : déclenchement du buzzer/LED de l'ESP8266 et des mouvements de frappe du robot Yanshee.
  * `GET /api/v1/actuators/audit` : traçabilité complète des actions déclenchées.
* **Sécurité & Durcissement Pentest ([KAN-36](file:///Users/martinp/Documents/Projets/School/SENTINEL%20-%20X/Jira.xml)) :**
  * Authentification par token Bearer ou clé d'en-tête `X-API-Key`.
  * Support HTTPS natif ou derrière reverse-proxy.

---

## 🚀 Démarrage Rapide

### 1. Avec Python & venv

```bash
cd sentinel-api
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
uvicorn app.main:app --host 0.0.0.0 --port 8080 --reload
```

L'API est alors disponible sur :
* **Swagger UI :** `http://localhost:8080/docs`
* **Health Check :** `http://localhost:8080/health`
* **Statut Système :** `http://localhost:8080/api/v1/status`

### 2. Avec Docker

```bash
docker build -t sentinel-api .
docker run -d -p 8080:8080 --env-file .env --name sentinel-api-instance sentinel-api
```

---

## 🧪 Lancer la Suite de Tests

```bash
source .venv/bin/activate
pytest -v
```
