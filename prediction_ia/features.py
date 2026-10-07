"""
Features de maintenance prédictive calculées sur une série à 1 Hz.

Le modèle ne regarde pas des valeurs isolées mais la dynamique des capteurs :
  - court terme : écart à la médiane des 5 dernières minutes, vitesse de
    variation, instabilité → voit une dérive lente dès son début ;
  - long terme : écart à une référence « air propre » qui redescend vite
    mais ne remonte que très lentement (≈ 1 h) → un incident installé reste
    visible, alors que la référence du firmware finit par l'absorber.

Le même code sert à l'entraînement (série complète) et en direct
(tampon des dernières minutes + références long terme tenues par boîtier),
pour que les deux voient les mêmes valeurs.
"""

from __future__ import annotations

import numpy as np
import pandas as pd

# Fenêtres (en secondes, la série est à 1 Hz)
REFERENCE_WINDOW = 300   # référence « état normal récent » : médiane sur 5 min
RATE_WINDOW = 60         # vitesse de variation température/gaz : sur 1 min
FAST_WINDOW = 15         # variations rapides d'humidité (souffle, condensation)
GAS_SMOOTH = 5           # lissage du gaz avant calcul de dérive
GAS_STD_WINDOW = 10      # instabilité du gaz (bouffée)

# Référence long terme : suit une baisse en ~2 min, une hausse en ~1 h
LONG_UP_TAU = 3600
LONG_DOWN_TAU = 120
LONG_REFERENCES = {"temperature": "temp_ref", "humidity": "hum_ref", "gas_raw": "gas_ref"}

# Secondes d'historique nécessaires avant de produire un score fiable
WARMUP_S = RATE_WINDOW
# Taille de tampon à garder en direct pour recalculer la dernière ligne
BUFFER_S = REFERENCE_WINDOW + RATE_WINDOW

FEATURES = [
    "temp",        # température (°C)
    "temp_dev",    # écart à la médiane des 5 dernières minutes (°C)
    "temp_rate",   # variation sur 1 min (°C/min)
    "temp_long",   # écart à la référence long terme (°C)
    "hum",         # humidité relative (%)
    "hum_dev",     # écart à la médiane des 5 dernières minutes (%)
    "hum_rate",    # variation sur 15 s (%)
    "hum_long",    # écart à la référence long terme (%)
    "gas_delta",   # écart à la référence calculée par le firmware
    "gas_dev",     # écart à la médiane des 5 dernières minutes
    "gas_rate",    # variation sur 1 min
    "gas_std",     # écart-type sur 10 s
    "gas_long",    # écart à la référence « air propre » long terme
]

# Un modèle par capteur : un Isolation Forest isole mal un écart sur une
# seule feature quand il en a treize (il ne la tire qu'une fois sur treize
# à chaque coupure). Par groupe de 4-5 features, l'isolement est net, et
# l'alerte dit directement quel capteur dérive.
GROUPS = {
    "temperature": ["temp", "temp_dev", "temp_rate", "temp_long"],
    "humidity": ["hum", "hum_dev", "hum_rate", "hum_long"],
    "gas": ["gas_delta", "gas_dev", "gas_rate", "gas_std", "gas_long"],
}

# Libellés lisibles, utilisés dans les alertes envoyées au dashboard
FEATURE_INFO = {
    "temp":      ("temperature", "Température hors plage habituelle", "{:.1f} °C"),
    "temp_dev":  ("temperature", "Hausse de température anormale", "{:+.1f} °C vs 5 min"),
    "temp_rate": ("temperature", "Montée en température anormale", "{:+.2f} °C/min"),
    "temp_long": ("temperature", "Température durablement au-dessus de la normale", "{:+.1f} °C"),
    "hum":       ("humidity", "Humidité hors plage habituelle", "{:.1f} %"),
    "hum_dev":   ("humidity", "Variation d'humidité anormale", "{:+.1f} % vs 5 min"),
    "hum_rate":  ("humidity", "Variation brutale d'humidité", "{:+.1f} % en 15 s"),
    "hum_long":  ("humidity", "Humidité durablement au-dessus de la normale", "{:+.1f} %"),
    "gas_delta": ("gas", "Écart gaz / référence anormal", "{:+.0f}"),
    "gas_dev":   ("gas", "Dérive lente du capteur de gaz (fuite probable)", "{:+.0f} vs 5 min"),
    "gas_rate":  ("gas", "Montée progressive du gaz (fuite probable)", "{:+.0f} /min"),
    "gas_std":   ("gas", "Bouffée de gaz (capteur instable)", "σ={:.0f}"),
    "gas_long":  ("gas", "Gaz durablement au-dessus de l'air propre", "{:+.0f}"),
}


class LongReference:
    """
    Références long terme d'un boîtier, mises à jour à chaque message.
    Récursives : le service en garde une par boîtier, l'entraînement les
    recalcule depuis le début de chaque série avec la même fonction.
    """

    def __init__(self) -> None:
        self.values: dict = {}

    def update(self, record: dict) -> dict:
        for column, ref_name in LONG_REFERENCES.items():
            x = record.get(column)
            if x is None or pd.isna(x):
                continue
            ref = self.values.get(ref_name)
            if ref is None:
                ref = float(x)
            else:
                tau = LONG_UP_TAU if x > ref else LONG_DOWN_TAU
                ref += (float(x) - ref) / tau
            self.values[ref_name] = ref
        return {name: self.values.get(name) for name in LONG_REFERENCES.values()}


def long_references(seg: pd.DataFrame) -> pd.DataFrame:
    """Références long terme sur une série complète (depuis son début)."""
    tracker = LongReference()
    columns = list(LONG_REFERENCES)
    rows = [tracker.update(dict(zip(columns, values))) for values in seg[columns].itertuples(index=False)]
    return pd.DataFrame(rows, index=seg.index, dtype=float)


def _rolling_median(series: pd.Series, window: int) -> pd.Series:
    return series.rolling(window, min_periods=min(30, window)).median()


def _rate(series: pd.Series, window: int) -> pd.Series:
    """Variation sur `window` s (les `window` premières lignes sont masquées ensuite)."""
    return series - series.shift(window)


def compute_features(seg: pd.DataFrame) -> pd.DataFrame:
    """
    seg : série continue à 1 Hz (index = uptime_s) avec les colonnes
    temperature, humidity, gas_raw, gas_baseline (voir common.split_segments),
    et éventuellement temp_ref, hum_ref, gas_ref (références long terme
    tenues par le service ; sinon recalculées depuis le début de seg).
    Renvoie un DataFrame aligné sur seg.index, colonnes = FEATURES.
    """
    temp = seg["temperature"].astype(float)
    hum = seg["humidity"].astype(float)
    gas = seg["gas_raw"].astype(float)
    gas_smooth = gas.rolling(GAS_SMOOTH, min_periods=1).mean()

    # Pendant la chauffe du MQ-135, le firmware n'a pas encore de référence
    baseline = seg["gas_baseline"].astype(float) if "gas_baseline" in seg else pd.Series(np.nan, index=seg.index)
    gas_ref = _rolling_median(gas_smooth, REFERENCE_WINDOW)
    baseline = baseline.fillna(gas_ref)

    refs = seg if set(LONG_REFERENCES.values()) <= set(seg.columns) else long_references(seg)

    out = pd.DataFrame(index=seg.index)
    out["temp"] = temp
    out["temp_dev"] = temp - _rolling_median(temp, REFERENCE_WINDOW)
    out["temp_rate"] = _rate(temp, RATE_WINDOW) * (60 / RATE_WINDOW)
    out["temp_long"] = temp - refs["temp_ref"].astype(float)
    out["hum"] = hum
    out["hum_dev"] = hum - _rolling_median(hum, REFERENCE_WINDOW)
    out["hum_rate"] = _rate(hum, FAST_WINDOW)
    out["hum_long"] = hum - refs["hum_ref"].astype(float)
    out["gas_delta"] = gas - baseline
    out["gas_dev"] = gas_smooth - gas_ref
    out["gas_rate"] = _rate(gas_smooth, RATE_WINDOW) * (60 / RATE_WINDOW)
    out["gas_std"] = gas.rolling(GAS_STD_WINDOW, min_periods=2).std()
    out["gas_long"] = gas_smooth - refs["gas_ref"].astype(float)

    # Les premières secondes d'une série n'ont pas assez d'historique
    elapsed = np.arange(len(out))
    out.loc[elapsed < WARMUP_S, :] = np.nan
    return out[FEATURES]
