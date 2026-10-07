"""
Simulateur de télémétrie Sentinel-X, calibré sur les mesures réelles du boîtier.

Il reproduit ce que publie le firmware :
  - DHT22 lu toutes les 2 s, résolution 0,1 ;
  - MQ-135 échantillonné à 10 Hz, filtre exponentiel, référence adaptative
    et niveaux normal/eleve/alerte (portage exact, voir firmware_gas.py).

Le bruit vient de l'enregistrement du 06/10 : résidu gaz ≈ 1,2 après filtre,
pas de 0,1 °C toutes les dizaines de secondes, humidité ± 0,15 %. Le
fonctionnement normal inclut des dérives lentes de la pièce et des
micro-événements (quelqu'un passe près du boîtier).

Usages :
  - générer des heures de fonctionnement normal pour entraîner le modèle
    tant qu'on n'a pas de long enregistrement réel ;
  - rejouer des scénarios contrôlés (surchauffe lente, fuite lente...) pour
    mesurer l'avance de l'IA sur les seuils ;
  - démo de secours : --publish envoie la simulation sur le broker comme
    un vrai boîtier.

Exemples :
  python simulate.py --scenario demo --minutes 20 --out data/sim_demo.jsonl
  python simulate.py --scenario demo --publish --device esp-sim
"""

from __future__ import annotations

import argparse
import json
import time
from dataclasses import dataclass
from typing import Optional

import numpy as np
import pandas as pd

from firmware_gas import FirmwareGas

SCENARIOS = ("normal", "surchauffe", "fuite_lente", "fuite_rapide", "humidite", "demo")

GAS_ADC_NOISE = 3.5      # bruit ADC par échantillon (≈ 1,2 après le filtre du firmware)
TEMP_NOISE = 0.03        # bruit du DHT22 avant arrondi à 0,1 °C
HUM_NOISE = 0.15         # bruit du DHT22 avant arrondi à 0,1 %
GAS_WARMUP_S = 60        # identique au firmware (GAS_WARMUP)

# Retour à la normale après la fin d'un incident (constantes de temps, s)
TEMP_RECOVERY_TAU = 300
GAS_RECOVERY_TAU = 90    # le MQ-135 met 1 à 3 min à redescendre (vu le 06/10)
HUM_RECOVERY_TAU = 60

# Micro-événements normaux : quelqu'un passe près du boîtier (respiration :
# un peu d'humidité, de chaleur et de CO2 vu par le MQ-135). En moyenne un
# toutes les 8 min ; ils ne sont PAS des incidents.
MICRO_EVENT_EVERY_S = 480

# Vérité terrain : à partir de quel effet réel une seconde est « incident »
# (≈ 10 fois le bruit du capteur, pour que l'étiquette soit physiquement visible)
LABEL_TEMP_EXCESS = 0.5     # °C
LABEL_GAS_EXCESS = 15.0     # unités ADC
LABEL_HUM_EXCESS = 3.0      # %

# Seuils « critiques » de référence, pour mesurer l'avance de l'IA (jamais
# utilisés pour détecter) : 40 °C, l'exemple du sujet ; +150 de gaz réel au-dessus
# de l'air propre, le seuil « eleve » du firmware appliqué à la vraie concentration.
CRITICAL_TEMP = 40.0
CRITICAL_GAS_EXCESS = 150.0


@dataclass
class Scenario:
    name: str = "normal"
    onset_s: int = 0
    end_s: Optional[int] = None   # fin de l'incident (None = jusqu'au bout)
    temp_rate: float = 0.0        # °C/min ajoutés pendant l'incident
    gas_rate: float = 0.0         # unités ADC/min ajoutées (fuite lente)
    gas_step: float = 0.0         # bouffée : excès atteint en gas_step_s secondes
    gas_step_s: float = 10.0
    hum_step: float = 0.0         # humidité : excès atteint en hum_step_s secondes
    hum_step_s: float = 20.0


def make_scenario(name: str, onset_s: int, rng: np.random.Generator, end_s: Optional[int] = None) -> Scenario:
    """Tire les paramètres d'un scénario (plages réalistes pour la démo)."""
    if name == "normal":
        return Scenario(name, onset_s, end_s)
    if name == "surchauffe":
        return Scenario(name, onset_s, end_s, temp_rate=rng.uniform(0.3, 0.8))
    if name == "fuite_lente":
        return Scenario(name, onset_s, end_s, gas_rate=rng.uniform(5, 20))
    if name == "fuite_rapide":
        return Scenario(name, onset_s, end_s, gas_step=rng.uniform(150, 700), gas_step_s=rng.uniform(3, 20))
    if name == "humidite":
        return Scenario(name, onset_s, end_s, hum_step=rng.uniform(6, 35), hum_step_s=rng.uniform(5, 60))
    if name == "demo":
        # Scénario du README : hausse lente de température + micro-dérive de gaz
        return Scenario(name, onset_s, end_s, temp_rate=rng.uniform(0.3, 0.5), gas_rate=rng.uniform(6, 10))
    raise ValueError(f"Scénario inconnu : {name} (choix : {', '.join(SCENARIOS)})")


def _ou_step(x: float, rng: np.random.Generator, tau_s: float, sigma: float) -> float:
    """Processus d'Ornstein-Uhlenbeck (pas de 1 s) : dérive aléatoire qui revient vers 0."""
    return x - x / tau_s + sigma * np.sqrt(2.0 / tau_s) * rng.standard_normal()


def simulate(
    duration_s: int,
    seed: int = 0,
    scenario: str = "normal",
    onset_s: Optional[int] = None,
    end_s: Optional[int] = None,
    device: str = "esp-sim",
    base_temp: Optional[float] = None,
    base_hum: Optional[float] = None,
    base_gas: Optional[float] = None,
) -> pd.DataFrame:
    """
    Simule `duration_s` secondes de télémétrie (1 ligne par seconde publiée).
    Vérité terrain : temp_excess, gas_excess, hum_excess (effet réel de
    l'incident) et les étiquettes label_temperature / label_humidity / label_gas.
    """
    rng = np.random.default_rng(seed)
    base_temp = rng.uniform(19, 29) if base_temp is None else base_temp
    base_hum = rng.uniform(32, 62) if base_hum is None else base_hum
    base_gas = rng.uniform(220, 380) if base_gas is None else base_gas
    if onset_s is None:
        onset_s = duration_s // 3
    sc = make_scenario(scenario, onset_s, rng, end_s)

    # Le firmware chauffe le MQ-135 pendant 60 s avant de fixer sa référence :
    # on simule ce préchauffage sans le publier.
    pre = GAS_WARMUP_S + 5
    gas_fw = FirmwareGas()

    # Dérives lentes de la pièce (sans incident) : vitesse en unité/min,
    # tirée d'un processus aléatoire, + rappel vers la valeur moyenne.
    temp_rate = hum_rate = gas_drift_rate = 0.0
    temp_off = hum_off = gas_off = 0.0
    temp_excess = gas_excess = hum_excess = 0.0
    micro_temp = micro_hum = micro_gas = 0.0
    micro_left = 0
    micro_target = (0.0, 0.0, 0.0)
    temp_meas = hum_meas = None

    rows = []
    for t in range(-pre, duration_s):
        temp_rate = _ou_step(temp_rate, rng, tau_s=600, sigma=0.06)       # ≈ ±0,06 °C/min
        hum_rate = _ou_step(hum_rate, rng, tau_s=300, sigma=0.4)          # ≈ ±0,4 %/min
        gas_drift_rate = _ou_step(gas_drift_rate, rng, tau_s=600, sigma=0.8)
        temp_off += temp_rate / 60 - temp_off / 3600
        hum_off += hum_rate / 60 - hum_off / 1800
        gas_off += gas_drift_rate / 60 - gas_off / 1800

        # Micro-événement : montée pendant sa durée, puis retour en ~1 min
        if micro_left == 0 and rng.random() < 1.0 / MICRO_EVENT_EVERY_S:
            micro_left = int(rng.uniform(10, 60))
            micro_target = (rng.uniform(0.0, 0.3), rng.uniform(0.5, 4.0), rng.uniform(0.0, 6.0))
        if micro_left > 0:
            micro_left -= 1
            micro_temp += (micro_target[0] - micro_temp) / 15
            micro_hum += (micro_target[1] - micro_hum) / 10
            micro_gas += (micro_target[2] - micro_gas) / 10
        else:
            micro_temp -= micro_temp / 90
            micro_hum -= micro_hum / 60
            micro_gas -= micro_gas / 60

        # Effet de l'incident : il s'installe pendant [onset, end[, puis s'estompe
        active = t >= sc.onset_s and (sc.end_s is None or t < sc.end_s)
        if active:
            temp_excess += sc.temp_rate / 60
            gas_excess += sc.gas_rate / 60
            if sc.gas_step:
                gas_excess = max(gas_excess, sc.gas_step * min(1.0, (t - sc.onset_s + 1) / sc.gas_step_s))
            if sc.hum_step:
                hum_excess = max(hum_excess, sc.hum_step * min(1.0, (t - sc.onset_s + 1) / sc.hum_step_s))
        elif t >= sc.onset_s:
            temp_excess -= temp_excess / TEMP_RECOVERY_TAU
            gas_excess -= gas_excess / GAS_RECOVERY_TAU
            hum_excess -= hum_excess / HUM_RECOVERY_TAU

        true_temp = base_temp + temp_off + temp_excess + micro_temp
        true_hum = float(np.clip(base_hum + hum_off + hum_excess + micro_hum, 5, 98))
        ambient_gas = base_gas + gas_off + gas_excess + micro_gas

        # MQ-135 : 10 échantillons par seconde, puis mise à jour de la référence
        for _ in range(10):
            gas_fw.sample(ambient_gas + GAS_ADC_NOISE * rng.standard_normal())
        gas_fw.update(warmed_up=(t + pre) >= GAS_WARMUP_S)

        # DHT22 : une lecture toutes les 2 s, la dernière valeur est republiée
        if temp_meas is None or t % 2 == 0:
            temp_meas = round(true_temp + TEMP_NOISE * rng.standard_normal(), 1)
            hum_meas = round(float(np.clip(true_hum + HUM_NOISE * rng.standard_normal(), 0, 100)), 1)

        if t < 0:
            continue
        # Étiquette « incident » seulement tant que l'incident est en cours :
        # le retour à la normale qui suit n'est pas un incident.
        gas_kind = "fuite_rapide" if sc.gas_step else "fuite_lente"
        rows.append({
            "device": device,
            "uptime_s": 120 + t,
            "temperature": temp_meas,
            "humidity": hum_meas,
            "gas_raw": float(gas_fw.value),
            "gas_baseline": float(int(gas_fw.baseline)) if gas_fw.baseline >= 0 else None,
            "gas_level": gas_fw.level,
            "presence": False,
            # Vérité terrain (non publiée)
            "true_temp": true_temp,
            "temp_excess": temp_excess,
            "gas_excess": gas_excess,
            "hum_excess": hum_excess,
            "label_temperature": "surchauffe" if active and temp_excess >= LABEL_TEMP_EXCESS else "normal",
            "label_humidity": "humidite" if active and hum_excess >= LABEL_HUM_EXCESS else "normal",
            "label_gas": gas_kind if active and gas_excess >= LABEL_GAS_EXCESS else "normal",
            "incident_active": active,
            "critical": bool(true_temp >= CRITICAL_TEMP or gas_excess >= CRITICAL_GAS_EXCESS),
        })

    df = pd.DataFrame(rows)
    df.attrs["scenario"] = sc
    return df


def to_message(row: dict) -> dict:
    """Ligne simulée → JSON au format exact du firmware."""
    return {
        "device": row["device"],
        "uptime_s": int(row["uptime_s"]),
        "temperature": row["temperature"],
        "humidity": row["humidity"],
        "gas": {
            "raw": int(row["gas_raw"]),
            "baseline": None if row["gas_baseline"] is None or pd.isna(row["gas_baseline"]) else int(row["gas_baseline"]),
            "level": row["gas_level"],
        },
        "presence": bool(row["presence"]),
        "rssi": -60,
        "actuators": {"buzzer": "off", "led": "off"},
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--scenario", choices=SCENARIOS, default="demo")
    parser.add_argument("--minutes", type=float, default=20)
    parser.add_argument("--onset", type=int, default=None, help="début de l'incident (s), défaut : 1/3 de la durée")
    parser.add_argument("--end", type=int, default=None, help="fin de l'incident (s), défaut : jusqu'au bout")
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--device", default="esp-sim")
    parser.add_argument("--out", help="fichier JSONL de sortie")
    parser.add_argument("--publish", action="store_true", help="publier en temps réel sur le broker MQTT")
    parser.add_argument("--speed", type=float, default=1.0, help="accélération de la publication (x)")
    args = parser.parse_args()

    df = simulate(int(args.minutes * 60), seed=args.seed, scenario=args.scenario,
                  onset_s=args.onset, end_s=args.end, device=args.device)
    sc = df.attrs["scenario"]
    print(f"Scénario {sc.name} : début à t={sc.onset_s}s, "
          f"+{sc.temp_rate:.2f} °C/min, +{sc.gas_rate:.1f} gaz/min, bouffée {sc.gas_step:.0f}, "
          f"humidité +{sc.hum_step:.0f} %")

    records = df.to_dict("records")
    if args.out:
        with open(args.out, "w", encoding="utf-8") as f:
            for row in records:
                f.write(json.dumps(to_message(row)) + "\n")
        print(f"{len(records)} lignes écrites dans {args.out}")

    if args.publish:
        from common import connect_mqtt, create_mqtt_client

        client = create_mqtt_client(f"sentinel-sim-{args.device}")
        connect_mqtt(client)
        client.loop_start()
        topic = f"sentinelx/{args.device}/telemetry"
        print(f"Publication sur {topic} (Ctrl+C pour arrêter)")
        try:
            for i, row in enumerate(records):
                client.publish(topic, json.dumps(to_message(row)), qos=0)
                if i % 30 == 0:
                    print(f"t={i}s temp={row['temperature']} gaz={row['gas_raw']:.0f} ({row['gas_level']})")
                time.sleep(1.0 / args.speed)
        except KeyboardInterrupt:
            pass
        finally:
            client.loop_stop()
            client.disconnect()


if __name__ == "__main__":
    main()
