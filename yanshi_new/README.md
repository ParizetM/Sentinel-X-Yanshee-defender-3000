# Sentinel-X — Yanshee

Surveillance par caméra du robot **Yanshee** : détection de personnes (YOLO),
déclenchement d'une action robot et publication des événements vers un
broker **Mosquitto (MQTT)**.

```
Flux MJPG (robot) ──► YOLO (classe "person") ──► action robot (dry run)
                           │
                           ├──► broker MQTT ──► timestamp / photo / compteur / action
                           │
                           └──► serveur HTTP ──► /stream.mjpg (flux annoté, clé API)
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
MQTT_BROKER_PORT = 8883
MQTT_USERNAME = <utilisateur broker>       # laisser vide si auth désactivée
MQTT_PASSWORD = <mot de passe broker>

MQTT_TLS = true                            # false = connexion en clair (port 1883)
MQTT_CA_CERT = certs/ca.crt                # CA qui a signé le certificat du broker
MQTT_TLS_INSECURE = false                  # true = ne plus vérifier le nom d'hôte

SENTINEL_API_KEY = <clé du flux vidéo>     # exigée par /stream.mjpg
STREAM_HOST = 0.0.0.0                      # 0.0.0.0 = toutes les interfaces
STREAM_PORT = 8080
SHOW_WINDOW = true                         # false = exécution sans écran
```

Le script refuse de démarrer si `ROBOT_API_KEY`, `MQTT_BROKER_HOST` ou
`SENTINEL_API_KEY` manquent.

### TLS

Par défaut la connexion au broker est chiffrée : le client présente le CA
[certs/ca.crt](certs/ca.crt) et vérifie que le certificat du broker est signé
par ce CA **et** qu'il correspond bien à `MQTT_BROKER_HOST`.

- Le certificat du broker doit contenir un **SAN** couvrant l'hôte utilisé
  (`DNS:...` ou `IP:...`). Un certificat sans SAN, ou dont le SAN ne
  correspond pas à `MQTT_BROKER_HOST`, est refusé — même s'il est signé par
  le bon CA.
- Si le certificat ne peut pas être régénéré tout de suite,
  `MQTT_TLS_INSECURE = true` désactive **uniquement** le contrôle du nom
  d'hôte : la chaîne de certification reste vérifiée. À réserver au dépannage.
- Pour une connexion non chiffrée, utiliser `MQTT_TLS = false` (port 1883) —
  c'est le seul moyen de désactiver la vérification du certificat.
- Si le fichier CA est absent et que `MQTT_TLS = true`, le script s'arrête
  avec un message explicite plutôt que de se connecter sans vérification.

## Flux HTTP (MJPEG)

Le flux **annoté par YOLO** (rectangles de détection incrustés) est exposé en
HTTP, avec le même format et la même clé que le flux caméra du robot — le
dashboard peut donc consommer les deux de la même façon.

| Route | Contenu |
|---|---|
| `/stream.mjpg` | Flux MJPEG (`multipart/x-mixed-replace`, une partie JPEG par frame) |
| `/api/v1/camera/stream` | Alias, pour la route prévue au README racine |
| `/` et `/index.html` | Page de démo qui affiche le flux |

Authentification : clé `SENTINEL_API_KEY`, par **en-tête** `X-API-KEY` ou par
**paramètre** `?key=`. Sans clé valide → `401` avec
`{"status": "unauthorized", "error": "Invalid or missing API Key for camera feed"}`
(identique aux scripts robot). La vérification a lieu **avant** le routage :
une route inconnue renvoie `401` sans clé, et `404` avec.

```bash
# En-tête : la clé n'apparaît ni dans l'URL ni dans l'historique shell
curl -N -H "X-API-KEY: $SENTINEL_API_KEY" http://<ip-machine-IA>:8080/stream.mjpg -o /dev/null

# Navigateur
http://<ip-machine-IA>:8080/?key=<clé>
```

Si aucune frame n'a encore été produite (YOLO démarre), la réponse est un
`503` explicite plutôt qu'une connexion qui pend.

> **Le flux est en HTTP, pas en HTTPS** : la clé et les images circulent en
> clair sur le réseau, alors que la branche MQTT est chiffrée. C'est un choix
> assumé pour cette version — à mentionner dans le dossier et à privilégier
> l'en-tête `X-API-KEY` (la clé dans l'URL finit dans l'historique du
> navigateur, les journaux de proxy et la sortie de `ps`). Le champ
> `STREAM_HOST` permet de restreindre l'écoute à une interface.

Sans écran (machine IA), mettre `SHOW_WINDOW = false` : la fenêtre OpenCV
n'est plus ouverte, le flux HTTP continue d'être servi et `Ctrl+C` arrête
proprement le script (le serveur MQTT, le serveur HTTP et les clients du flux
sont fermés).

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

## Déploiement sur une VM

Le script est prévu pour tourner sur une VM (ou toute machine sans écran) :

```bash
./deploy/install_vm.sh --check    # vérifie réseau, .env, certificats, port
./deploy/install_vm.sh            # venv + dépendances + service systemd
```

Le service `sentinel-video` démarre avec la machine et redémarre tout seul.
Détails, configuration et dépannage : **[deploy/README.md](deploy/README.md)**.

Sur une VM, `SHOW_WINDOW = false` est obligatoire (pas d'écran) ; le flux HTTP
reste servi normalement.

## Tests

```bash
# 49 tests : publications MQTT, encodage JPEG, erreurs réseau, stockage, TLS,
# et serveur de flux (authentification, format multipart, déconnexions)
pytest test_yanshi_video.py test_stream_server.py -v

# Smoke test d'intégration : démarre un broker amqtt local (port 18833)
# et vérifie que les 4 topics arrivent avec des payloads valides.
python3 smoke_test_mqtt.py
```

## Structure

```
yanshi_video.py       script principal (détection + MQTT)
stream_server.py      serveur MJPEG HTTP (flux annoté + clé API)
test_yanshi_video.py  tests pytest
conftest.py           isolation des tests du .env
test_stream_server.py tests pytest du serveur de flux
smoke_test_mqtt.py    test d'intégration avec un broker local
deploy/               installation sur VM (install_vm.sh + doc)
yolo26n.pt            modèle YOLO
certs/ca.crt          autorité de certification du broker (TLS)
captures/             photos sauvegardées localement (50 max)
```

## Notes

- L'action robot est en **dry run** (`dry_run=1`) : non dangereuse.
- La détection ne cible que la classe COCO 0 (person), confiance 0.40.
- Une photo est prise au maximum toutes les 10 s, uniquement lorsqu'au
  moins une personne est détectée.
