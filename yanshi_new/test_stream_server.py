import json
import socket
import struct
import threading
import time

import numpy as np
import pytest

import stream_server

API_KEY = "test-key"


# ============================================================
# Outils de test
# ============================================================

def _frame(value: int, size=(48, 64)) -> np.ndarray:
    """Frame synthétique unicolore, pour ne dépendre d'aucune image."""
    return np.full((*size, 3), value, dtype=np.uint8)


def _request(port: int, path: str, key: str | None = None, method="GET"):
    """Requête HTTP brute, retourne (statut, en-têtes, corps)."""

    request = [f"{method} {path} HTTP/1.0", "Host: 127.0.0.1"]

    if key is not None:
        request.append(f"X-API-KEY: {key}")

    sock = socket.create_connection(("127.0.0.1", port), timeout=5)
    sock.sendall(("\r\n".join(request) + "\r\n\r\n").encode())

    raw = b""

    while b"\r\n\r\n" not in raw:
        chunk = sock.recv(4096)
        if not chunk:
            break
        raw += chunk

    head, _, body = raw.partition(b"\r\n\r\n")

    status = int(head.split(b" ")[1])

    headers = {}

    for line in head.split(b"\r\n")[1:]:
        name, _, value = line.partition(b": ")
        headers[name.decode().lower()] = value.decode()

    length = int(headers.get("content-length", 0))

    while len(body) < length:
        chunk = sock.recv(4096)
        if not chunk:
            break
        body += chunk

    sock.close()

    return status, headers, body


def _open_stream(port: int, key: str) -> socket.socket:
    """Ouvre une connexion sur le flux et retourne la socket."""
    sock = socket.create_connection(("127.0.0.1", port), timeout=5)
    sock.sendall(
        f"GET /stream.mjpg?key={key} HTTP/1.0\r\n"
        f"Host: 127.0.0.1\r\n\r\n".encode()
    )
    return sock


def _read_until(sock, marker: bytes, count=1, initial=b"", deadline=5.0):
    """Lit jusqu'à ce que marker apparaisse count fois (garde-fou : délai)."""
    sock.settimeout(deadline)

    data = initial

    while data.count(marker) < count:
        chunk = sock.recv(4096)
        if not chunk:
            break
        data += chunk

    return data


def _drain_until_eof(sock, deadline=3.0) -> bool:
    """Vide la socket ; True si le pair ferme la connexion à temps."""
    sock.settimeout(deadline)

    while True:
        try:
            chunk = sock.recv(4096)
        except (TimeoutError, socket.timeout):
            return False

        if not chunk:
            return True


def _parse_parts(raw: bytes):
    """Découpe une réponse multipart en (en-têtes, jpeg) par partie."""
    parts = []

    for segment in raw.split(b"--FRAME\r\n")[1:]:
        head, separator, body = segment.partition(b"\r\n\r\n")

        if not separator:
            continue  # partie incomplète en fin de lecture

        headers = {}

        for line in head.split(b"\r\n"):
            name, _, value = line.partition(b": ")
            headers[name.decode().lower()] = value.decode()

        parts.append((headers, body[:-2]))  # retire le \r\n terminal

    return parts


@pytest.fixture
def running_server():
    """Serveur réel sur un port libre (port=0), avec sa frame partagée."""
    frames = stream_server.LatestFrame()

    server = stream_server.create_stream_server(
        frames,
        host="127.0.0.1",
        port=0,
        api_key=API_KEY,
    )

    thread = threading.Thread(
        target=server.serve_forever, name="test-stream", daemon=True
    )
    thread.start()

    yield server, frames

    frames.close()
    server.shutdown()
    server.server_close()
    thread.join(timeout=5)


# ============================================================
# keys_match
# ============================================================

def test_keys_match_accepts_exact_key():
    assert stream_server.keys_match(API_KEY, API_KEY) is True


def test_keys_match_rejects_wrong_and_empty_keys():
    assert stream_server.keys_match("mauvaise", API_KEY) is False
    assert stream_server.keys_match("", API_KEY) is False
    assert stream_server.keys_match(None, API_KEY) is False


def test_keys_match_rejects_near_miss():
    assert stream_server.keys_match("test-ke", API_KEY) is False


def test_keys_match_handles_non_ascii_client_key_without_raising():
    # hmac.compare_digest refuse les chaînes non-ASCII : sans l'encodage
    # UTF-8 explicite, cette comparaison lèverait TypeError au lieu de
    # renvoyer False (un client peut envoyer n'importe quoi).
    assert stream_server.keys_match("clé-accentuée", API_KEY) is False


# ============================================================
# encode_jpeg
# ============================================================

def test_encode_jpeg_returns_jpeg_bytes():
    jpeg = stream_server.encode_jpeg(_frame(128))

    assert jpeg is not None
    assert jpeg[:2] == b"\xff\xd8"      # magic number JPEG
    assert jpeg[-2:] == b"\xff\xd9"     # fin de fichier JPEG


def test_encode_jpeg_returns_none_on_invalid_frame():
    # imencode lève sur un tableau vide : la fonction doit renvoyer None
    # plutôt que laisser remonter l'exception.
    assert stream_server.encode_jpeg(np.array([])) is None


# ============================================================
# LatestFrame
# ============================================================

def test_latest_frame_returns_published_frame():
    frames = stream_server.LatestFrame()

    frames.update(_frame(42))

    frame, sequence = frames.wait_for_frame(0, timeout=0)

    assert frame is not None
    assert sequence == 1
    assert frame[0, 0, 0] == 42


def test_latest_frame_timeout_returns_none_with_same_sequence():
    frames = stream_server.LatestFrame()

    frames.update(_frame(42))

    frame, sequence = frames.wait_for_frame(1, timeout=0.05)

    assert frame is None
    assert sequence == 1


def test_latest_frame_copies_published_frame():
    frames = stream_server.LatestFrame()

    image = _frame(10)
    frames.update(image)

    # Le producteur modifie son tableau après publication : la frame
    # partagée ne doit pas changer (lecture sans verrou côté clients).
    image[:] = 255

    frame, _ = frames.wait_for_frame(0, timeout=0)

    assert frame[0, 0, 0] == 10


def test_latest_frame_close_wakes_blocked_reader():
    frames = stream_server.LatestFrame()

    def close_soon():
        time.sleep(0.2)
        frames.close()

    threading.Thread(target=close_soon, daemon=True).start()

    started = time.monotonic()
    frame, sequence = frames.wait_for_frame(0, timeout=5)
    elapsed = time.monotonic() - started

    assert frame is None
    assert sequence == 0
    assert elapsed < 2


def test_latest_frame_closed_is_visible():
    frames = stream_server.LatestFrame()

    assert frames.closed is False

    frames.close()

    assert frames.closed is True


# ============================================================
# Corps de réponse et page HTML
# ============================================================

def test_unauthorized_body_matches_robot_scripts():
    assert stream_server.build_unauthorized_body() == (
        b'{"status": "unauthorized", '
        b'"error": "Invalid or missing API Key for camera feed"}'
    )


def test_index_html_embeds_stream_with_key():
    page = stream_server.build_index_html(API_KEY)

    assert f"/stream.mjpg?key={API_KEY}" in page


def test_index_html_escapes_key():
    page = stream_server.build_index_html('a"onmouseover="x')

    assert "&quot;" in page
    assert '"onmouseover="x' not in page


def test_mask_key_hides_secret():
    assert stream_server.mask_key(f"key={API_KEY}") == "key=***"


def test_stream_url_masks_key_and_uses_given_port():
    assert stream_server.stream_url("127.0.0.1", 0) == (
        "http://127.0.0.1:0/stream.mjpg?key=***"
    )


# ============================================================
# Authentification (socket réelle)
# ============================================================

def test_request_without_key_is_rejected(running_server):
    server, _ = running_server

    status, headers, body = _request(server.server_address[1], "/stream.mjpg")

    assert status == 401
    assert headers["content-type"] == "application/json"
    assert json.loads(body) == {
        "status": "unauthorized",
        "error": "Invalid or missing API Key for camera feed",
    }


def test_request_with_wrong_key_is_rejected(running_server):
    server, _ = running_server

    status, _, _ = _request(
        server.server_address[1], "/stream.mjpg", key="mauvaise-cle"
    )

    assert status == 401


def test_unknown_path_without_key_is_rejected_not_404(running_server):
    # L'authentification passe avant le routage : une route inconnue ne
    # doit pas être révélée à un client non authentifié.
    server, _ = running_server

    status, _, _ = _request(server.server_address[1], "/inconnu")

    assert status == 401


def test_unknown_path_with_key_returns_404(running_server):
    server, _ = running_server

    status, _, _ = _request(
        server.server_address[1], "/inconnu", key=API_KEY
    )

    assert status == 404


def test_options_is_allowed_without_key(running_server):
    server, _ = running_server

    status, headers, _ = _request(
        server.server_address[1], "/stream.mjpg", method="OPTIONS"
    )

    assert status == 200
    assert headers["access-control-allow-origin"] == "*"
    assert headers["access-control-allow-headers"] == "X-API-KEY, Content-Type"


def test_index_page_is_served_with_key(running_server):
    server, _ = running_server

    status, headers, body = _request(
        server.server_address[1], "/", key=API_KEY
    )

    assert status == 200
    assert headers["content-type"] == "text/html; charset=utf-8"
    assert f"/stream.mjpg?key={API_KEY}".encode() in body


# ============================================================
# Flux MJPEG (socket réelle)
# ============================================================

def test_stream_rejects_missing_key(running_server):
    server, frames = running_server

    frames.update(_frame(10))

    status, _, _ = _request(server.server_address[1], "/stream.mjpg")

    assert status == 401


def test_stream_response_is_multipart(running_server):
    server, frames = running_server

    frames.update(_frame(10))

    sock = _open_stream(server.server_address[1], API_KEY)
    raw = _read_until(sock, b"--FRAME\r\n")

    assert b"200 OK" in raw
    assert b"multipart/x-mixed-replace; boundary=FRAME" in raw

    sock.close()


def test_stream_part_headers_match_payload(running_server):
    server, frames = running_server

    frames.update(_frame(10))

    sock = _open_stream(server.server_address[1], API_KEY)
    raw = _read_until(sock, b"\xff\xd9\r\n")
    sock.close()

    part_headers, jpeg = _parse_parts(raw)[0]

    # Un Content-Length qui ne correspond pas à la taille réelle
    # désynchroniserait définitivement le parseur du client.
    assert int(part_headers["content-length"]) == len(jpeg)
    assert part_headers["content-type"] == "image/jpeg"
    assert jpeg[:2] == b"\xff\xd8"
    assert jpeg[-2:] == b"\xff\xd9"


def test_stream_sends_one_part_per_frame(running_server):
    server, frames = running_server

    frames.update(_frame(10))

    sock = _open_stream(server.server_address[1], API_KEY)
    raw = _read_until(sock, b"--FRAME\r\n")

    frames.update(_frame(200))

    # Attend deux parties *complètes* (fin de JPEG + CRLF), et non deux
    # frontières : à la deuxième frontière, la partie 2 n'est pas encore
    # arrivée et la découpe serait incomplète.
    raw = _read_until(sock, b"\xff\xd9\r\n", count=2, initial=raw)
    sock.close()

    parts = _parse_parts(raw)

    # Ce test attrape le piège send_header() : si les en-têtes de partie
    # passaient par send_header(), ils n'arriveraient jamais et les
    # parties seraient indécoupables.
    assert len(parts) == 2
    assert parts[0][1] != parts[1][1]


def test_stream_returns_503_when_no_frame_yet(
    running_server, monkeypatch
):
    server, _ = running_server

    monkeypatch.setattr(stream_server, "FIRST_FRAME_TIMEOUT", 0.1)

    status, headers, body = _request(
        server.server_address[1], "/stream.mjpg", key=API_KEY
    )

    assert status == 503
    assert headers["content-type"] == "application/json"
    assert json.loads(body)["status"] == "unavailable"


def test_stream_alias_path_is_served(running_server):
    server, frames = running_server

    frames.update(_frame(10))

    sock = socket.create_connection(
        ("127.0.0.1", server.server_address[1]), timeout=5
    )
    sock.sendall(
        f"GET /api/v1/camera/stream?key={API_KEY} HTTP/1.0\r\n"
        f"Host: 127.0.0.1\r\n\r\n".encode()
    )

    raw = _read_until(sock, b"--FRAME\r\n")
    sock.close()

    assert b"200 OK" in raw


def test_closing_stream_ends_client_connection(running_server):
    server, frames = running_server

    frames.update(_frame(10))

    sock = _open_stream(server.server_address[1], API_KEY)

    # Attend une partie complète : sinon les octets du JPEG encore en
    # tampon seraient pris pour la réponse au premier recv().
    _read_until(sock, b"\xff\xd9\r\n")

    frames.close()

    # Le serveur doit fermer la connexion (EOF) au lieu de la laisser
    # pendre : si rien ne se passait, _drain_until_eof rendrait False.
    assert _drain_until_eof(sock) is True

    sock.close()


def test_server_survives_client_reset(running_server):
    server, frames = running_server

    frames.update(_frame(10))

    # RST forcé (SO_LINGER 0) : plus déterministe qu'une fermeture propre
    # pour vérifier que le handler encaisse une déconnexion brutale.
    sock = _open_stream(server.server_address[1], API_KEY)
    _read_until(sock, b"--FRAME\r\n")
    sock.setsockopt(
        socket.SOL_SOCKET, socket.SO_LINGER, struct.pack("ii", 1, 0)
    )
    sock.close()

    time.sleep(0.2)

    status, _, _ = _request(
        server.server_address[1], "/stream.mjpg", key=API_KEY
    )

    assert status == 200


# ============================================================
# create_stream_server
# ============================================================

def test_create_stream_server_uses_given_parameters():
    frames = stream_server.LatestFrame()

    server = stream_server.create_stream_server(
        frames, host="127.0.0.1", port=0, api_key="autre-cle"
    )

    try:
        assert server.frames is frames
        assert server.api_key == "autre-cle"
        assert server.server_address[1] > 0
    finally:
        server.server_close()
