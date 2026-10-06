# Sentinel-X — Yanshee

Surveillance par caméra du robot **Yanshee** : détection de personnes (YOLO),
déclenchement d'une action robot et publication des événements vers un
broker **Mosquitto (MQTT)**.

```
Flux MJPG (robot) ──► YOLO (classe "person") ──► action robot (dry run)
                           │
                           └──► broker MQTT ──► timestamp / photo / compteur / action
```

## Prérequis

- Python 3.10+
- Accès réseau au robot (`10.0.3.234`) et au broker Mosquitto
- Un broker Mosquitto avec un utilisateur configuré

## Installation

```bash
pip install -r requirements.txt        # dépendances runtime
pip install -r requirements-dev.txt    # + pytest, amqtt (tests)
```

## Configuration

Copier [.env.example](.env.example) vers `.env` et renseigner les valeurs :

```ini
ROBOT_API_KEY = <clé API du robot>

MQTT_BROKER_HOST = <IP de la machine qui héberge Mosquitto>
MQTT_BROKER_PORT = 1883
MQTT_USERNAME = <utilisateur broker>       # laisser vide si auth désactivée
MQTT_PASSWORD = <mot de passe broker>
```

Le script refuse de démarrer si `ROBOT_API_KEY` ou `MQTT_BROKER_HOST` manquent.

## Utilisation

```bash
python3 yanshi_video.py
```

- La fenêtre OpenCV affiche le flux avec les détections dessinées.
- **Q** pour quitter.
- En cas de broker injoignable, le client MQTT se reconnecte
  automatiquement (délai 1 s → 30 s) et met en file jusqu'à 100 messages
  (QoS 1).

## Topics MQTT

Racine : `detection_robot/`

| Topic             | Payload                          | Quand                                   |
|-------------------|----------------------------------|-----------------------------------------|
| `timestamp`       | horaire ISO 8601 (`2026-10-06T14:23:05+02:00`) | à chaque capture (avec personne détectée) |
| `photo`           | JPEG binaire (qualité 90)        | à chaque capture (frame brute, sans rectangles YOLO) |
| `person_count`    | entier (ex. `2`)                 | à chaque capture ; **`0` toutes les 10 s** quand personne n'est détectée (heartbeat) |
| `action`          | JSON `{"action", "dry_run", "status_code", "timestamp"}` | à chaque action robot (cooldown 5 s) |

Le `timestamp` est publié juste avant la `photo` : un abonné reçoit les deux
à la suite et peut les associer.

### Observer le flux

```bash
# Depuis n'importe quelle machine avec mosquitto-clients :
mosquitto_sub -h <IP broker> -u <user> -P <mdp> -t 'detection_robot/#' -v

# Récupérer une photo :
mosquitto_sub -h <IP broker> -u <user> -P <mdp> -t 'detection_robot/photo' -C 1 > photo.jpg
```

## Tests

```bash
# 13 tests unitaires (publications MQTT, encodage JPEG, erreurs réseau, stockage)
pytest test_yanshi_video.py -v

# Smoke test d'intégration : démarre un broker amqtt local (port 18833)
# et vérifie que les 4 topics arrivent avec des payloads valides.
python3 smoke_test_mqtt.py
```

## Structure

```
yanshi_video.py       script principal (détection + MQTT)
test_yanshi_video.py  tests pytest
conftest.py           isolation des tests du .env
smoke_test_mqtt.py    test d'intégration avec un broker local
yolo26n.pt            modèle YOLO
captures/             photos sauvegardées localement (50 max)
```

## Notes

- L'action robot est en **dry run** (`dry_run=1`) : non dangereuse.
- La détection ne cible que la classe COCO 0 (person), confiance 0.40.
- Une photo est prise au maximum toutes les 10 s, uniquement lorsqu'au
  moins une personne est détectée.
