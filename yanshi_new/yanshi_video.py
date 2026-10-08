import json
import os
import ssl
import threading
import time
from datetime import datetime
from pathlib import Path

import cv2
import paho.mqtt.client as mqtt
import requests
from dotenv import load_dotenv
from ultralytics import YOLO

from stream_server import LatestFrame, create_stream_server, stream_url


# ============================================================
# CONFIGURATION
# ============================================================

load_dotenv()


def _env_flag(name: str, default: bool = False) -> bool:
    """Interprète une variable d'environnement comme un booléen."""
    raw = os.getenv(name)
    if raw is None or not raw.strip():
        return default
    return raw.strip().lower() in {"1", "true", "yes", "on"}


ROBOT_API_KEY = os.getenv("ROBOT_API_KEY")

if not ROBOT_API_KEY:
    raise RuntimeError("ROBOT_API_KEY manquant dans le .env")

STREAM_URL = f"http://10.0.3.234:8000/stream.mjpg?key={ROBOT_API_KEY}"

# Action NON DANGEREUSE du robot
ACTION_URL = f"http://10.0.3.234:5000/punch?key={ROBOT_API_KEY}&dry_run=1"

# --- Broker Mosquitto ---

MQTT_HOST = os.getenv("MQTT_BROKER_HOST")
MQTT_USERNAME = os.getenv("MQTT_USERNAME") or None
MQTT_PASSWORD = os.getenv("MQTT_PASSWORD") or None

try:
    MQTT_PORT = int(os.getenv("MQTT_BROKER_PORT", "1883"))
except ValueError:
    raise RuntimeError(
        "MQTT_BROKER_PORT doit être un entier dans le .env"
    ) from None

if not MQTT_HOST:
    raise RuntimeError("MQTT_BROKER_HOST manquant dans le .env")

# --- TLS ---

# MQTT_TLS : chiffre la connexion et vérifie le certificat présenté par
# le broker. MQTT_CA_CERT est l'autorité (CA) qui a signé ce certificat ;
# un chemin absolu, ou relatif au dossier du script.
MQTT_TLS = _env_flag("MQTT_TLS", default=True)

# MQTT_TLS_INSECURE : ne désactive QUE le contrôle du nom d'hôte (utile
# si le certificat serveur ne contient pas l'IP du broker). La chaîne de
# certification reste vérifiée. Dépannage uniquement.
MQTT_TLS_INSECURE = _env_flag("MQTT_TLS_INSECURE")

SCRIPT_DIR = Path(__file__).resolve().parent

MQTT_CA_CERT = SCRIPT_DIR / Path(
    os.path.expanduser(os.getenv("MQTT_CA_CERT", "certs/ca.crt"))
)

# Arborescence des topics :
#   detection_robot/timestamp    → horaire de la photo (ISO 8601)
#   detection_robot/photo        → photo (JPEG binaire)
#   detection_robot/person_count → nombre de personnes détectées
#   detection_robot/action       → action du robot (JSON)
MQTT_TOPIC_ROOT = "detection_robot"

TOPIC_TIMESTAMP = f"{MQTT_TOPIC_ROOT}/timestamp"
TOPIC_PHOTO = f"{MQTT_TOPIC_ROOT}/photo"
TOPIC_PERSON_COUNT = f"{MQTT_TOPIC_ROOT}/person_count"
TOPIC_ACTION = f"{MQTT_TOPIC_ROOT}/action"

# QoS 1 : le message est délivré au moins une fois
MQTT_QOS = 1

# Nombre max de messages en attente quand le broker est injoignable
# (évite une croissance mémoire illimitée pendant une coupure)
MQTT_MAX_QUEUED = 1000

MODEL_PATH = "yolo26n.pt"

CONFIDENCE = 0.40
IMAGE_SIZE = 640

# Une photo maximum toutes les 10 secondes
CAPTURE_INTERVAL = 10

# Évite également de spammer l'endpoint robot à chaque frame
ACTION_COOLDOWN = 5

MAX_IMAGES = 1000

CAPTURE_DIR = Path("captures")
CAPTURE_DIR.mkdir(exist_ok=True)

# --- Affichage ---

# Fenêtre OpenCV locale. false = exécution sans écran (le flux HTTP reste
# servi, la sortie se fait par Ctrl+C).
SHOW_WINDOW = _env_flag("SHOW_WINDOW", default=True)


# ============================================================
# UTILITAIRES
# ============================================================

def now_iso() -> str:
    """Horodatage ISO 8601 avec fuseau horaire local."""
    return datetime.now().astimezone().isoformat()


def trigger_action() -> int | None:
    """
    Déclenche une action non dangereuse sur le robot.

    Retourne le code HTTP de la réponse, ou None en cas d'erreur.
    """
    try:
        response = requests.get(
            ACTION_URL,
            timeout=2
        )

        response.raise_for_status()

        print(
            f"[ROBOT] Action déclenchée "
            f"({response.status_code})"
        )

        return response.status_code

    except requests.RequestException as e:
        print(f"[ROBOT] Erreur endpoint : {e}")
        return None


def trigger_action_async(client: mqtt.Client) -> None:
    """
    Déclenche l'action robot dans un thread séparé : un endpoint
    injoignable ne bloque plus la boucle de détection.
    """
    status_code = trigger_action()
    publish_action(client, status_code)


def enforce_image_limit():
    """
    Conserve uniquement les MAX_IMAGES images les plus récentes.
    Supprime la plus ancienne lorsque la limite est dépassée.
    """

    images = sorted(
        CAPTURE_DIR.glob("*.jpg"),
        key=lambda path: path.stat().st_mtime
    )

    while len(images) > MAX_IMAGES:
        oldest = images.pop(0)

        print(f"[STORAGE] Suppression : {oldest.name}")

        oldest.unlink()


def save_frame(frame, timestamp: datetime) -> bool:
    """
    Sauvegarde la frame entière de la vidéo.

    Retourne False si l'écriture sur le disque a échoué.
    """

    filename = CAPTURE_DIR / (
        f"frame_{timestamp.strftime('%Y-%m-%d_%H-%M-%S')}.jpg"
    )

    ok = cv2.imwrite(
        str(filename),
        frame,
        [cv2.IMWRITE_JPEG_QUALITY, 90]
    )

    if not ok:
        print(f"[CAPTURE] Échec d'écriture : {filename}")
        return False

    print(f"[CAPTURE] {filename}")

    enforce_image_limit()

    return True


# ============================================================
# MQTT
# ============================================================

def on_connect(client, userdata, flags, reason_code, properties=None):
    """Callback de connexion : journalise l'état de la connexion."""
    print(f"[MQTT] Connecté au broker (code={reason_code})")


def on_disconnect(
    client, userdata, disconnect_flags, reason_code, properties=None
):
    """Callback de déconnexion : journalise et laisse paho reconnecter."""
    print(f"[MQTT] Déconnecté (code={reason_code}), reconnexion auto...")


def on_connect_fail(client, userdata):
    """
    Callback d'échec de connexion : paho retente en arrière-plan, on se
    contente de rendre la cause probable lisible dans les logs.
    """
    if MQTT_TLS:
        print(
            "[MQTT] Échec de connexion — vérifier le port TLS (souvent 8883), "
            f"le certificat du broker et le CA ({MQTT_CA_CERT})"
        )
    else:
        print("[MQTT] Échec de connexion au broker, nouvelle tentative...")


def _configure_tls(client: mqtt.Client) -> None:
    """
    Active TLS sur le client : le certificat présenté par le broker doit
    être signé par MQTT_CA_CERT et correspondre à l'hôte contacté.
    """

    if not MQTT_CA_CERT.is_file():
        raise RuntimeError(
            f"Certificat CA introuvable : {MQTT_CA_CERT} "
            "(renseigner MQTT_CA_CERT ou MQTT_TLS=false dans le .env)"
        )

    client.tls_set(
        ca_certs=str(MQTT_CA_CERT),
        tls_version=ssl.PROTOCOL_TLS_CLIENT,
    )

    if MQTT_TLS_INSECURE:
        print(
            "[MQTT] ATTENTION : contrôle du nom d'hôte désactivé "
            "(MQTT_TLS_INSECURE=true)"
        )
        client.tls_insecure_set(True)


def create_mqtt_client() -> mqtt.Client:
    """
    Crée le client MQTT et démarre la reconnexion automatique
    en arrière-plan.
    """

    client = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2)

    if MQTT_USERNAME:
        client.username_pw_set(MQTT_USERNAME, MQTT_PASSWORD)

    if MQTT_TLS:
        _configure_tls(client)

    client.on_connect = on_connect
    client.on_connect_fail = on_connect_fail
    client.on_disconnect = on_disconnect

    client.max_queued_messages_set(MQTT_MAX_QUEUED)
    client.reconnect_delay_set(min_delay=1, max_delay=30)

    # connect_async : ne bloque pas si le broker est injoignable,
    # paho retente automatiquement en arrière-plan.
    client.connect_async(MQTT_HOST, MQTT_PORT, keepalive=60)
    client.loop_start()

    return client


def publish(client: mqtt.Client, topic: str, payload) -> None:
    """Publie un message sur un topic MQTT."""

    info = client.publish(topic, payload, qos=MQTT_QOS)

    if info.rc == mqtt.MQTT_ERR_SUCCESS:
        print(f"[MQTT] Publié → {topic}")
    else:
        print(f"[MQTT] Échec publication {topic} (rc={info.rc})")


def publish_timestamp(client: mqtt.Client, timestamp_iso: str) -> None:
    """Publie l'horaire de la photo sur detection_robot/timestamp."""
    publish(client, TOPIC_TIMESTAMP, timestamp_iso)


def publish_person_count(client: mqtt.Client, count: int) -> None:
    """Publie le nombre de personnes sur detection_robot/person_count."""
    publish(client, TOPIC_PERSON_COUNT, str(count))


def publish_photo(client: mqtt.Client, frame) -> None:
    """Publie la photo (JPEG binaire) sur detection_robot/photo."""

    ok, buffer = cv2.imencode(
        ".jpg",
        frame,
        [cv2.IMWRITE_JPEG_QUALITY, 90]
    )

    if not ok:
        print("[MQTT] Échec encodage JPEG, photo non publiée")
        return

    publish(client, TOPIC_PHOTO, buffer.tobytes())


def build_action_payload(status_code: int | None) -> dict:
    """Construit le payload JSON publié sur detection_robot/action."""
    return {
        "action": "punch",
        "dry_run": True,
        "status_code": status_code,
        "timestamp": now_iso(),
    }


def publish_action(client: mqtt.Client, status_code: int | None) -> None:
    """Publie l'action du robot sur detection_robot/action."""
    payload = json.dumps(build_action_payload(status_code))
    publish(client, TOPIC_ACTION, payload)


# ============================================================
# BOUCLE PRINCIPALE
# ============================================================

def main() -> None:

    model = YOLO(MODEL_PATH)

    mqtt_client = create_mqtt_client()

    # Frame annotée partagée avec les clients HTTP
    frames = LatestFrame()

    http_server = None

    try:

        # Créé dans le try : si le port est déjà pris, le finally ne doit
        # pas appeler shutdown() sur un serveur jamais démarré (il
        # bloquerait indéfiniment).
        http_server = create_stream_server(frames)

        threading.Thread(
            target=http_server.serve_forever,
            name="sentinel-stream",
            daemon=True
        ).start()

        print("[SYSTEM] Chargement du flux...")
        print(f"[SYSTEM] Source : {STREAM_URL.replace(ROBOT_API_KEY, '***')}")
        transport = (
            f"TLS (CA: {MQTT_CA_CERT})" if MQTT_TLS else "sans TLS"
        )
        print(f"[SYSTEM] Broker MQTT : {MQTT_HOST}:{MQTT_PORT} — {transport}")
        print(f"[STREAM] Flux annoté : {stream_url()} (clé API requise)")

        if not SHOW_WINDOW:
            print(
                "[STREAM] Fenêtre OpenCV désactivée "
                "(SHOW_WINDOW=false)"
            )

        last_capture_time = 0
        last_action_time = 0

        results = model.predict(
            source=STREAM_URL,
            stream=True,
            device="cpu",
            imgsz=IMAGE_SIZE,
            conf=CONFIDENCE,
            classes=[0],       # classe COCO 0 = person
            verbose=False
        )

        for result in results:

            frame = result.orig_img

            boxes = result.boxes

            person_count = len(boxes) if boxes is not None else 0

            person_detected = person_count > 0

            current_time = time.monotonic()

            if person_detected:

                # ----------------------------------------------------
                # Action robot
                # ----------------------------------------------------

                if current_time - last_action_time >= ACTION_COOLDOWN:

                    print(
                        f"[DETECTION] "
                        f"{person_count} personne(s) détectée(s)"
                    )

                    threading.Thread(
                        target=trigger_action_async,
                        args=(mqtt_client,),
                        daemon=True
                    ).start()

                    last_action_time = current_time

                # ----------------------------------------------------
                # Capture toutes les 10 secondes
                # ----------------------------------------------------

                if current_time - last_capture_time >= CAPTURE_INTERVAL:

                    print(
                        f"[CAPTURE] Frame entière "
                        f"({person_count} personne(s))"
                    )

                    capture_time = datetime.now().astimezone()

                    save_frame(frame, capture_time)

                    publish_timestamp(
                        mqtt_client,
                        capture_time.isoformat()
                    )
                    publish_photo(mqtt_client, frame)
                    publish_person_count(mqtt_client, person_count)

                    last_capture_time = current_time

            else:
                # Aucune personne : publie quand même 0 pour que les
                # abonnés distinguent « 0 personne » de « pas de mise
                # à jour »
                if current_time - last_capture_time >= CAPTURE_INTERVAL:
                    publish_person_count(mqtt_client, 0)
                    last_capture_time = current_time

            # Image avec les détections YOLO dessinées
            display_frame = result.plot()

            # Publiée pour les clients HTTP (copie interne : les
            # lecteurs l'encodent sans verrou)
            frames.update(display_frame)

            if SHOW_WINDOW:
                cv2.imshow("Sentinel-X - Yanshee", display_frame)

                # Q pour fermer
                if cv2.waitKey(1) & 0xFF == ord("q"):
                    break

    except KeyboardInterrupt:
        # Exécution sans fenêtre : Ctrl+C est le seul moyen de sortir
        print("[SYSTEM] Interruption clavier.")

    finally:

        print("[SYSTEM] Flux terminé.")

        # Réveille les clients HTTP bloqués AVANT de fermer le serveur,
        # sinon shutdown() attendrait des handlers encore en attente.
        frames.close()

        if http_server is not None:
            http_server.shutdown()
            http_server.server_close()

        if SHOW_WINDOW:
            cv2.destroyAllWindows()

        mqtt_client.loop_stop()
        if mqtt_client.is_connected():
            mqtt_client.disconnect()


if __name__ == "__main__":
    main()
