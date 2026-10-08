"""Outils partagés : configuration (.env), client MQTT TLS et chargement de la télémétrie."""

from __future__ import annotations

import json
import os
import ssl
from pathlib import Path
from typing import Iterable, List, Optional

import pandas as pd
from dotenv import load_dotenv

SCRIPT_DIR = Path(__file__).resolve().parent

load_dotenv(SCRIPT_DIR / ".env")


# ============================================================
# CONFIGURATION
# ============================================================

def env_str(name: str, default: Optional[str] = None) -> Optional[str]:
    """Variable d'environnement texte (une valeur vide vaut « absente »)."""
    raw = os.getenv(name)
    if raw is None or not raw.strip():
        return default
    return raw.strip()


def env_flag(name: str, default: bool = False) -> bool:
    """Interprète une variable d'environnement comme un booléen."""
    raw = env_str(name)
    if raw is None:
        return default
    return raw.lower() in {"1", "true", "yes", "on"}


def env_int(name: str, default: int) -> int:
    raw = env_str(name)
    if raw is None:
        return default
    try:
        return int(raw)
    except ValueError:
        raise RuntimeError(f"{name} doit être un entier dans le .env") from None


def resolve_path(raw: str) -> Path:
    """Chemin absolu, ou relatif au dossier prediction_ia."""
    path = Path(os.path.expanduser(raw))
    return path if path.is_absolute() else SCRIPT_DIR / path


# ============================================================
# MQTT
# ============================================================

def create_mqtt_client(client_id: str):
    """
    Client MQTT configuré depuis le .env (mêmes variables que yanshi_new) :
    MQTT_BROKER_HOST, MQTT_BROKER_PORT, MQTT_USERNAME, MQTT_PASSWORD,
    MQTT_TLS, MQTT_CA_CERT, MQTT_TLS_INSECURE.

    Le client n'est pas encore connecté : appeler connect_mqtt().
    """
    import paho.mqtt.client as mqtt

    host = env_str("MQTT_BROKER_HOST")
    if not host:
        raise RuntimeError("MQTT_BROKER_HOST manquant dans le .env")

    client = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2, client_id=client_id)

    username = env_str("MQTT_USERNAME")
    if username:
        client.username_pw_set(username, env_str("MQTT_PASSWORD"))

    if env_flag("MQTT_TLS", default=True):
        ca_cert = resolve_path(env_str("MQTT_CA_CERT", "certs/ca.crt"))
        if not ca_cert.is_file():
            raise RuntimeError(
                f"Certificat CA introuvable : {ca_cert} "
                "(renseigner MQTT_CA_CERT ou MQTT_TLS=false dans le .env)"
            )
        client.tls_set(ca_certs=str(ca_cert), tls_version=ssl.PROTOCOL_TLS_CLIENT)
        if env_flag("MQTT_TLS_INSECURE"):
            print("[MQTT] ATTENTION : contrôle du nom d'hôte désactivé (MQTT_TLS_INSECURE=true)")
            client.tls_insecure_set(True)
    else:
        print("[MQTT] ATTENTION : connexion en clair (MQTT_TLS=false)")

    client.reconnect_delay_set(min_delay=1, max_delay=30)
    return client


def connect_mqtt(client) -> None:
    """Connexion non bloquante : paho retente seul si le broker est injoignable."""
    host = env_str("MQTT_BROKER_HOST")
    port = env_int("MQTT_BROKER_PORT", 8883)
    print(f"[MQTT] Connexion à {host}:{port} ...")
    client.connect_async(host, port, keepalive=60)


# ============================================================
# DONNÉES
# ============================================================

# Colonnes à plat utilisées par tout le pipeline
COLUMNS = [
    "device", "uptime_s", "temperature", "humidity",
    "gas_raw", "gas_baseline", "gas_level", "presence",
]


def flatten_record(data: dict) -> dict:
    """Message de télémétrie du firmware → dictionnaire à plat."""
    gas = data.get("gas")
    if isinstance(gas, dict):
        gas_raw, gas_baseline, gas_level = gas.get("raw"), gas.get("baseline"), gas.get("level")
    else:
        gas_raw, gas_baseline, gas_level = gas, None, None

    def num(value):
        return None if value is None else float(value)

    return {
        "device": data.get("device") or data.get("device_id") or "esp-01",
        "uptime_s": data.get("uptime_s"),
        "temperature": num(data.get("temperature")),
        "humidity": num(data.get("humidity")),
        "gas_raw": num(gas_raw),
        "gas_baseline": num(gas_baseline),
        "gas_level": gas_level,
        "presence": bool(data.get("presence", data.get("pir", False))),
    }


def load_jsonl(paths: Iterable[Path]) -> pd.DataFrame:
    """Charge un ou plusieurs fichiers JSONL produits par data_take.py."""
    rows: List[dict] = []
    for path in paths:
        with open(path, encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                record = flatten_record(json.loads(line))
                record["source_file"] = Path(path).name
                rows.append(record)
    if not rows:
        return pd.DataFrame(columns=COLUMNS + ["source_file"])
    return pd.DataFrame(rows)


def split_segments(df: pd.DataFrame, max_gap_s: int = 10) -> List[pd.DataFrame]:
    """
    Découpe en séries continues (même fichier, même boîtier, pas de reboot
    ni de trou > max_gap_s) puis rééchantillonne à 1 Hz sur uptime_s.

    uptime_s sert d'horloge : il vient de l'ESP et ne dépend pas de la
    gigue réseau, contrairement à l'heure de réception.
    """
    segments = []
    group_keys = [c for c in ("source_file", "device") if c in df.columns]
    groups = df.groupby(group_keys, sort=False) if group_keys else [(None, df)]
    for _, group in groups:
        # Ordre d'arrivée conservé : un reboot fait nettement redescendre
        # uptime_s, alors qu'un doublon ou une inversion QoS 1 ne recule que
        # de quelques secondes (corrigé par le tri ci-dessous).
        group = group.dropna(subset=["uptime_s"]).reset_index(drop=True)
        uptime = group["uptime_s"].astype(int)
        step = uptime.diff()
        breaks = (step < -max_gap_s) | (step > max_gap_s)
        for _, seg in group.groupby(breaks.cumsum()):
            seg = seg.drop_duplicates("uptime_s", keep="last").set_index("uptime_s").sort_index()
            seg.index = seg.index.astype(int)
            full = range(seg.index.min(), seg.index.max() + 1)
            seg = seg.reindex(full).ffill(limit=max_gap_s)
            seg.index.name = "uptime_s"
            segments.append(seg)
    return segments
