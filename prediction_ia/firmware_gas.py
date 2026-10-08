"""
Portage Python de la logique gaz du firmware (sentinel-x-firmware/src/main.cpp,
sampleGas() et updateGas()), constantes identiques.

Sert à simuler exactement ce que le boîtier publierait (raw, baseline, level),
pour comparer l'IA aux seuils du firmware sur des scénarios contrôlés.
"""

from __future__ import annotations

GAS_THRESHOLD_HIGH = 150
GAS_THRESHOLD_ALERT = 300
GAS_HYSTERESIS = 30
GAS_TRACK_FAST = 0.05
GAS_TRACK_SLOW = 0.003
GAS_TRACK_DOWN = 0.1
GAS_EMA = 0.2            # sampleGas() : filtre exponentiel à chaque échantillon (100 ms)

LEVELS = ("normal", "eleve", "alerte")


class FirmwareGas:
    def __init__(self) -> None:
        self.filtered = -1.0
        self.baseline = -1.0
        self.state = 0
        self.value = 0

    def sample(self, raw: float) -> None:
        """Un échantillon ADC (appelé toutes les 100 ms par le firmware)."""
        raw = min(1023, max(0, int(round(raw))))
        self.filtered = raw if self.filtered < 0 else self.filtered + (raw - self.filtered) * GAS_EMA

    def update(self, warmed_up: bool = True) -> None:
        """Mise à jour de la référence et du niveau (appelée toutes les secondes)."""
        self.value = int(self.filtered)

        if warmed_up and self.baseline < 0:
            self.baseline = self.filtered
        elif self.baseline >= 0:
            delta = self.value - self.baseline
            if delta < 0:
                self.baseline += delta * GAS_TRACK_DOWN
            elif delta < GAS_THRESHOLD_HIGH / 2:
                self.baseline += delta * GAS_TRACK_FAST
            elif delta < GAS_THRESHOLD_ALERT:
                self.baseline += delta * GAS_TRACK_SLOW

        if self.baseline >= 0:
            delta = int(self.value - self.baseline)
            if delta > GAS_THRESHOLD_ALERT:
                self.state = 2
            elif delta > GAS_THRESHOLD_HIGH:
                self.state = 2 if (self.state == 2 and delta > GAS_THRESHOLD_ALERT - GAS_HYSTERESIS) else 1
            elif self.state >= 1 and delta > GAS_THRESHOLD_HIGH - GAS_HYSTERESIS:
                self.state = 1
            else:
                self.state = 0

    @property
    def level(self) -> str:
        return "chauffe" if self.baseline < 0 else LEVELS[self.state]
