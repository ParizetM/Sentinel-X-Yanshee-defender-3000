"""
Serveur MJPEG HTTP : expose la dernière frame annotée par YOLO.

Reprend la convention des scripts robot (branche scripts-robots) pour que
le dashboard consomme les deux flux de la même façon :

  - /stream.mjpg diffusé en multipart/x-mixed-replace
  - authentification par en-tête X-API-KEY ou paramètre ?key=
  - 401 JSON {"status": "unauthorized", ...} si la clé est absente ou fausse

Le flux est servi en HTTP (sans TLS) : la clé et les images circulent en
clair sur le réseau. Voir le README pour les conséquences.
"""

import hmac
import json
import os
import threading
from html import escape
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import parse_qs, urlparse

import cv2
from dotenv import load_dotenv

# Ce module est importé avant le load_dotenv() de yanshi_video : il charge
# donc lui-même le .env pour pouvoir lire SENTINEL_API_KEY.
load_dotenv()


# ============================================================
# CONFIGURATION
# ============================================================

SENTINEL_API_KEY = os.getenv("SENTINEL_API_KEY")

if not SENTINEL_API_KEY:
    raise RuntimeError(
        "SENTINEL_API_KEY manquant dans le .env "
        "(clé exigée par le flux vidéo exposé)"
    )

STREAM_HOST = os.getenv("STREAM_HOST") or "0.0.0.0"

try:
    STREAM_PORT = int(os.getenv("STREAM_PORT", "8080"))
except ValueError:
    raise RuntimeError(
        "STREAM_PORT doit être un entier dans le .env"
    ) from None

# Routes qui diffusent le flux : /stream.mjpg comme les scripts robot, et
# l'alias /api/v1/camera/stream prévu par le README racine.
STREAM_PATHS = ("/stream.mjpg", "/api/v1/camera/stream")

INDEX_PATHS = ("/", "/index.html")

BOUNDARY = "FRAME"

# Qualité JPEG du flux continu (les photos MQTT restent à 90)
JPEG_QUALITY = 80

# Attente de la première frame avant de répondre 503 : laisse à YOLO le
# temps de produire sa première inférence.
FIRST_FRAME_TIMEOUT = 10.0

# Réveil périodique des clients : filet de sécurité pour qu'un handler ne
# reste jamais bloqué si close() n'est pas appelé.
FRAME_WAIT_TIMEOUT = 1.0

MASKED_KEY = "***"


# ============================================================
# UTILITAIRES
# ============================================================

def mask_key(text: str) -> str:
    """Remplace la clé API par *** dans un texte destiné aux logs."""
    if not SENTINEL_API_KEY:
        return text

    return text.replace(SENTINEL_API_KEY, MASKED_KEY)


def keys_match(candidate: str | None, expected: str) -> bool:
    """
    Compare deux clés en temps constant.

    L'encodage UTF-8 est indispensable : hmac.compare_digest refuse les
    chaînes non-ASCII, donc une clé comme "café" envoyée par un client
    ferait lever TypeError au lieu de renvoyer False.
    """
    if not candidate:
        return False

    return hmac.compare_digest(
        candidate.encode("utf-8"),
        expected.encode("utf-8"),
    )


def encode_jpeg(frame, quality: int = JPEG_QUALITY) -> bytes | None:
    """Encode une frame en JPEG, ou None si l'encodage échoue."""
    try:
        ok, buffer = cv2.imencode(
            ".jpg",
            frame,
            [cv2.IMWRITE_JPEG_QUALITY, quality],
        )
    except cv2.error as e:
        # imencode lève (au lieu de renvoyer ok=False) sur un tableau vide
        # ou d'un format inattendu.
        print(f"[STREAM] Échec encodage JPEG : {e}")
        return None

    if not ok:
        return None

    return buffer.tobytes()


def build_unauthorized_body() -> bytes:
    """Corps JSON du 401, identique à celui des scripts robot."""
    return json.dumps({
        "status": "unauthorized",
        "error": "Invalid or missing API Key for camera feed",
    }).encode("utf-8")


def build_no_frame_body() -> bytes:
    """Corps JSON renvoyé tant qu'aucune frame n'a été produite."""
    return json.dumps({
        "status": "unavailable",
        "error": "No annotated frame available yet",
    }).encode("utf-8")


def build_index_html(api_key: str) -> str:
    """Page de démonstration affichant le flux."""
    key = escape(api_key, quote=True)

    return f"""<!DOCTYPE html>
<html>
<head><title>SENTINEL-X SECURE FEED</title></head>
<body style="background:#111;text-align:center;color:#00f3ff;font-family:monospace;padding-top:30px;">
    <h2>SENTINEL-X // FLUX IA ANNOTÉ</h2>
    <div style="margin-bottom:15px;color:#94a3b8;font-size:13px;">[SECURED BY API KEY]</div>
    <img src="/stream.mjpg?key={key}" style="border:2px solid #00f3ff;border-radius:8px;max-width:90%;" />
</body></html>"""


def stream_url(host: str | None = None, port: int | None = None) -> str:
    """
    URL du flux pour les logs, clé masquée.

    À ne pas confondre avec yanshi_video.STREAM_URL, qui est le flux
    *source* consommé depuis le robot.
    """
    if host is None:
        host = STREAM_HOST

    if port is None:
        port = STREAM_PORT

    return f"http://{host}:{port}/stream.mjpg?key={MASKED_KEY}"


# ============================================================
# PARTAGE DE FRAME
# ============================================================

class LatestFrame:
    """
    Dernière frame annotée, partagée entre la boucle YOLO et les clients.

    Le producteur publie une copie : le tableau stocké n'est plus jamais
    modifié après publication, les lecteurs peuvent donc l'encoder sans
    verrou. La Condition ne protège que la séquence et l'attente.
    """

    def __init__(self) -> None:
        self._condition = threading.Condition()
        self._frame = None
        self._sequence = 0
        self._closed = False

    @property
    def closed(self) -> bool:
        with self._condition:
            return self._closed

    def update(self, frame) -> None:
        """Publie une nouvelle frame (copie) et réveille les lecteurs."""
        if frame is None:
            return

        with self._condition:
            self._frame = frame.copy()
            self._sequence += 1
            self._condition.notify_all()

    def wait_for_frame(
        self, last_sequence: int, timeout: float | None = None
    ) -> tuple:
        """
        Attend une frame plus récente que last_sequence.

        Retourne (frame, sequence), ou (None, last_sequence) si le délai
        est écoulé, si la frame est déjà connue, ou si le flux est fermé.
        """
        with self._condition:
            self._condition.wait_for(
                lambda: self._closed or self._sequence > last_sequence,
                timeout=timeout,
            )

            if self._frame is not None and self._sequence > last_sequence:
                return self._frame, self._sequence

        return None, last_sequence

    def close(self) -> None:
        """Ferme le flux : les lecteurs en attente sont réveillés."""
        with self._condition:
            self._closed = True
            self._condition.notify_all()


# ============================================================
# SERVEUR HTTP
# ============================================================

class StreamRequestHandler(BaseHTTPRequestHandler):
    """Handler HTTP : page de démo, flux MJPEG, authentification par clé."""

    # Flux temps réel : on désactive l'algorithme de Nagle (TCP_NODELAY).
    disable_nagle_algorithm = True

    # Volontairement en HTTP/1.0 (défaut de la classe) : le corps multipart
    # est infini, il n'a donc ni Content-Length global ni chunked. HTTP/1.0
    # ferme aussi la connexion en fin de réponse.

    def log_message(self, format: str, *args) -> None:
        """
        Journalise sur stdout avec la clé masquée.

        Le log par défaut écrit la ligne de requête complète sur stderr,
        ce qui exposerait ?key=<clé> en clair à chaque connexion.
        """
        print(f"[STREAM] {self.address_string()} — {mask_key(format % args)}")

    # --------------------------------------------------------
    # Authentification
    # --------------------------------------------------------

    def _is_authorized(self, query: dict) -> bool:
        """Vrai si la clé API est valide (en-tête X-API-KEY ou ?key=)."""
        header_key = self.headers.get("X-API-KEY")

        if keys_match(
            header_key.strip() if header_key else None,
            self.server.api_key,
        ):
            return True

        return keys_match(
            query.get("key", [None])[0],
            self.server.api_key,
        )

    # --------------------------------------------------------
    # Envoi de réponses
    # --------------------------------------------------------

    def _send_cors(self) -> None:
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, OPTIONS")
        self.send_header(
            "Access-Control-Allow-Headers", "X-API-KEY, Content-Type"
        )

    def _send_json(self, status: int, body: bytes) -> None:
        self.send_response(status)
        self._send_cors()
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _send_html(self, content: str) -> None:
        body = content.encode("utf-8")

        self.send_response(200)
        self._send_cors()
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _write_part(self, jpeg: bytes) -> None:
        """
        Écrit une partie du flux multipart, en octets bruts.

        send_header() n'est PAS utilisable ici : après le premier
        end_headers(), il empile dans _headers_buffer, qui n'est plus
        jamais vidé — les en-têtes de partie n'atteindraient jamais le
        client et la liste grossirait sans fin.
        """
        self.wfile.write(
            b"--" + BOUNDARY.encode("ascii") + b"\r\n"
            b"Content-Type: image/jpeg\r\n"
            b"Content-Length: " + str(len(jpeg)).encode("ascii") + b"\r\n"
            b"\r\n"
        )
        self.wfile.write(jpeg)
        self.wfile.write(b"\r\n")

    def _send_stream(self) -> None:
        """Diffuse les frames annotées jusqu'à déconnexion du client."""
        frames = self.server.frames

        frame, sequence = frames.wait_for_frame(
            0, timeout=FIRST_FRAME_TIMEOUT
        )

        if frame is None:
            # Statut choisi AVANT d'engager la réponse : le client reçoit
            # un vrai 503 plutôt qu'une connexion qui pend.
            self._send_json(503, build_no_frame_body())
            return

        self.send_response(200)
        self._send_cors()
        self.send_header("Age", "0")
        self.send_header(
            "Cache-Control", "no-cache, no-store, must-revalidate"
        )
        self.send_header("Pragma", "no-cache")
        self.send_header(
            "Content-Type",
            f"multipart/x-mixed-replace; boundary={BOUNDARY}",
        )
        self.end_headers()

        try:
            while True:
                jpeg = encode_jpeg(frame)

                if jpeg is not None:
                    self._write_part(jpeg)

                new_frame, new_sequence = frames.wait_for_frame(
                    sequence, timeout=FRAME_WAIT_TIMEOUT
                )

                if new_frame is None:
                    # Délai écoulé sans nouvelle frame : on garde la
                    # précédente et on réessaie, sauf si le flux est fermé.
                    if frames.closed:
                        break

                    continue

                frame, sequence = new_frame, new_sequence

        except ConnectionError as e:
            # Client parti (BrokenPipeError, ConnectionResetError...) :
            # cas normal, on rend simplement la main.
            print(
                f"[STREAM] Client déconnecté "
                f"({self.client_address[0]}) : {e}"
            )

    # --------------------------------------------------------
    # Routage
    # --------------------------------------------------------

    def do_OPTIONS(self) -> None:
        """Pré-vol CORS : sans authentification, comme la référence."""
        self.send_response(200)
        self._send_cors()
        self.end_headers()

    def do_GET(self) -> None:
        parsed = urlparse(self.path)
        query = parse_qs(parsed.query)

        # Authentification AVANT le routage : une route inconnue ne doit
        # pas être révélée à un client non authentifié.
        if not self._is_authorized(query):
            self._send_json(401, build_unauthorized_body())
            return

        if parsed.path in INDEX_PATHS:
            self._send_html(build_index_html(self.server.api_key))
        elif parsed.path in STREAM_PATHS:
            self._send_stream()
        else:
            self.send_error(404)


class StreamingServer(ThreadingHTTPServer):
    """
    Serveur HTTP threadé portant la frame partagée et la clé attendue.

    Les porter sur l'instance (plutôt qu'en globales de module comme la
    référence Python 2) permet à deux serveurs de coexister dans un même
    processus, notamment pendant les tests.

    daemon_threads = True est délibéré : les threads de handler restent
    bloqués tant qu'un client regarde le flux ; avec False, server_close()
    les joindrait et pendrait indéfiniment.
    """

    allow_reuse_address = True
    daemon_threads = True

    def __init__(self, address, frames: LatestFrame, api_key: str) -> None:
        super().__init__(address, StreamRequestHandler)
        self.frames = frames
        self.api_key = api_key


def create_stream_server(
    frames: LatestFrame,
    host: str | None = None,
    port: int | None = None,
    api_key: str | None = None,
) -> StreamingServer:
    """
    Crée le serveur (non démarré) : l'appelant lance serve_forever() dans
    son propre thread, puis shutdown() depuis un autre thread.
    """
    if host is None:
        host = STREAM_HOST

    if port is None:
        port = STREAM_PORT

    if api_key is None:
        api_key = SENTINEL_API_KEY

    return StreamingServer((host, port), frames, api_key)
