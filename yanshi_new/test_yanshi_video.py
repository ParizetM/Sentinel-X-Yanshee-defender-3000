import json
import ssl
from datetime import datetime
from types import SimpleNamespace

import numpy as np
import pytest

import yanshi_video


class FakeMqttClient:
    """Client MQTT factice qui enregistre les publications en mémoire."""

    def __init__(self):
        self.published = []

    def publish(self, topic, payload, qos=0):
        self.published.append((topic, payload, qos))
        return SimpleNamespace(rc=0)


class FailingMqttClient(FakeMqttClient):
    """Client MQTT factice simulant un broker injoignable."""

    def publish(self, topic, payload, qos=0):
        self.published.append((topic, payload, qos))
        return SimpleNamespace(rc=4)  # MQTT_ERR_NO_CONN


class FakeResponse:
    """Réponse HTTP factice pour mocker requests."""

    def __init__(self, status_code=200):
        self.status_code = status_code

    def raise_for_status(self):
        if self.status_code >= 400:
            raise Exception("HTTP error")


@pytest.fixture
def fake_client():
    return FakeMqttClient()


# ============================================================
# now_iso
# ============================================================

def test_now_iso_returns_parseable_iso8601_timestamp():
    parsed = datetime.fromisoformat(yanshi_video.now_iso())

    assert parsed.tzinfo is not None


# ============================================================
# build_action_payload
# ============================================================

def test_build_action_payload_contains_expected_fields():
    payload = yanshi_video.build_action_payload(200)

    assert payload["action"] == "punch"
    assert payload["dry_run"] is True
    assert payload["status_code"] == 200
    assert "timestamp" in payload


def test_build_action_payload_keeps_none_status_on_robot_error():
    payload = yanshi_video.build_action_payload(None)

    assert payload["status_code"] is None


# ============================================================
# Publications MQTT
# ============================================================

def test_publish_timestamp_sends_iso_string_on_timestamp_topic(fake_client):
    yanshi_video.publish_timestamp(
        fake_client,
        "2026-10-06T12:00:00+02:00"
    )

    topic, payload, qos = fake_client.published[0]

    assert topic == yanshi_video.TOPIC_TIMESTAMP
    assert payload == "2026-10-06T12:00:00+02:00"
    assert qos == yanshi_video.MQTT_QOS


def test_publish_person_count_sends_count_as_string(fake_client):
    yanshi_video.publish_person_count(fake_client, 3)

    topic, payload, _ = fake_client.published[0]

    assert topic == yanshi_video.TOPIC_PERSON_COUNT
    assert payload == "3"


def test_publish_photo_encodes_frame_as_jpeg_bytes(fake_client):
    frame = np.zeros((64, 64, 3), dtype=np.uint8)

    yanshi_video.publish_photo(fake_client, frame)

    topic, payload, _ = fake_client.published[0]

    assert topic == yanshi_video.TOPIC_PHOTO
    assert isinstance(payload, bytes)
    assert payload[:2] == b"\xff\xd8"      # magic number JPEG
    assert payload[-2:] == b"\xff\xd9"     # fin de fichier JPEG


def test_publish_action_sends_valid_json_on_action_topic(fake_client):
    yanshi_video.publish_action(fake_client, 200)

    topic, payload, _ = fake_client.published[0]

    assert topic == yanshi_video.TOPIC_ACTION

    data = json.loads(payload)

    assert data["action"] == "punch"
    assert data["status_code"] == 200


def test_publish_failure_is_logged_without_raising(capsys):
    client = FailingMqttClient()

    yanshi_video.publish_person_count(client, 1)

    captured = capsys.readouterr()

    assert "Échec publication" in captured.out
    assert len(client.published) == 1


# ============================================================
# trigger_action
# ============================================================

def test_trigger_action_returns_status_code(monkeypatch):
    monkeypatch.setattr(
        yanshi_video.requests,
        "get",
        lambda url, timeout: FakeResponse(200)
    )

    assert yanshi_video.trigger_action() == 200


def test_trigger_action_returns_none_on_request_error(monkeypatch):
    def raise_request_exception(url, timeout):
        raise yanshi_video.requests.RequestException("connexion refusée")

    monkeypatch.setattr(
        yanshi_video.requests,
        "get",
        raise_request_exception
    )

    assert yanshi_video.trigger_action() is None


# ============================================================
# save_frame
# ============================================================

def test_save_frame_writes_file_in_capture_dir(tmp_path, monkeypatch):
    monkeypatch.setattr(yanshi_video, "CAPTURE_DIR", tmp_path)

    frame = np.zeros((64, 64, 3), dtype=np.uint8)

    ok = yanshi_video.save_frame(
        frame,
        datetime(2026, 10, 6, 12, 0, 0)
    )

    files = list(tmp_path.glob("frame_2026-10-06_12-00-00.jpg"))

    assert ok is True
    assert len(files) == 1


def test_save_frame_returns_false_on_write_failure(tmp_path, monkeypatch):
    monkeypatch.setattr(yanshi_video, "CAPTURE_DIR", tmp_path)

    monkeypatch.setattr(yanshi_video.cv2, "imwrite", lambda *args, **kw: False)

    ok = yanshi_video.save_frame(
        np.zeros((64, 64, 3), dtype=np.uint8),
        datetime(2026, 10, 6, 12, 0, 0)
    )

    assert ok is False
    assert list(tmp_path.glob("*.jpg")) == []


# ============================================================
# Coherence du flux complet
# ============================================================

def test_capture_event_publishes_timestamp_photo_and_count_in_order(
    fake_client
):
    frame = np.zeros((64, 64, 3), dtype=np.uint8)

    timestamp_iso = "2026-10-06T12:00:00+02:00"

    yanshi_video.publish_timestamp(fake_client, timestamp_iso)
    yanshi_video.publish_photo(fake_client, frame)
    yanshi_video.publish_person_count(fake_client, 2)

    topics = [topic for topic, _, _ in fake_client.published]

    assert topics == [
        yanshi_video.TOPIC_TIMESTAMP,
        yanshi_video.TOPIC_PHOTO,
        yanshi_video.TOPIC_PERSON_COUNT,
    ]


# ============================================================
# TLS
# ============================================================

class RecordingMqttClient:
    """Client MQTT factice qui enregistre sa configuration TLS."""

    def __init__(self, *args, **kwargs):
        self.tls_set_calls = []
        self.insecure_calls = []
        self.connected_to = []
        self.started = False

    # --- configuration TLS ---

    def username_pw_set(self, username, password=None):
        pass

    def tls_set(self, **kwargs):
        self.tls_set_calls.append(kwargs)

    def tls_insecure_set(self, value):
        self.insecure_calls.append(value)

    # --- cycle de vie ---

    def max_queued_messages_set(self, count):
        pass

    def reconnect_delay_set(self, min_delay=1, max_delay=120):
        pass

    def connect_async(self, host, port, keepalive=60):
        self.connected_to.append((host, port))

    def loop_start(self):
        self.started = True


@pytest.fixture
def ca_cert(tmp_path, monkeypatch):
    """Faux certificat CA, pour ne dépendre d'aucun fichier du dépôt."""

    path = tmp_path / "ca.crt"
    path.write_text(
        "-----BEGIN CERTIFICATE-----\nZmFrZQ==\n-----END CERTIFICATE-----\n"
    )

    monkeypatch.setattr(yanshi_video, "MQTT_CA_CERT", path)

    return path


def test_configure_tls_verifies_broker_certificate_against_ca(
    ca_cert, monkeypatch
):
    monkeypatch.setattr(yanshi_video, "MQTT_TLS_INSECURE", False)

    client = RecordingMqttClient()

    yanshi_video._configure_tls(client)

    assert client.tls_set_calls[0]["ca_certs"] == str(ca_cert)
    assert client.tls_set_calls[0]["tls_version"] == ssl.PROTOCOL_TLS_CLIENT
    assert client.insecure_calls == []


def test_configure_tls_insecure_flag_disables_hostname_check(
    ca_cert, monkeypatch
):
    monkeypatch.setattr(yanshi_video, "MQTT_TLS_INSECURE", True)

    client = RecordingMqttClient()

    yanshi_video._configure_tls(client)

    assert client.insecure_calls == [True]


def test_configure_tls_raises_readable_error_when_ca_cert_missing(
    tmp_path, monkeypatch
):
    monkeypatch.setattr(yanshi_video, "MQTT_CA_CERT", tmp_path / "absent.crt")

    with pytest.raises(RuntimeError, match="Certificat CA introuvable"):
        yanshi_video._configure_tls(RecordingMqttClient())


def test_create_mqtt_client_enables_tls_when_configured(
    ca_cert, monkeypatch
):
    monkeypatch.setattr(yanshi_video, "MQTT_TLS", True)
    monkeypatch.setattr(yanshi_video, "MQTT_HOST", "127.0.0.1")
    monkeypatch.setattr(yanshi_video.mqtt, "Client", RecordingMqttClient)

    client = yanshi_video.create_mqtt_client()

    assert client.tls_set_calls[0]["ca_certs"] == str(ca_cert)
    assert client.connected_to == [("127.0.0.1", yanshi_video.MQTT_PORT)]
    assert client.started is True


def test_create_mqtt_client_skips_tls_when_disabled(monkeypatch):
    monkeypatch.setattr(yanshi_video, "MQTT_TLS", False)
    monkeypatch.setattr(yanshi_video, "MQTT_HOST", "127.0.0.1")
    monkeypatch.setattr(yanshi_video.mqtt, "Client", RecordingMqttClient)

    client = yanshi_video.create_mqtt_client()

    assert client.tls_set_calls == []
    assert client.connected_to == [("127.0.0.1", yanshi_video.MQTT_PORT)]
