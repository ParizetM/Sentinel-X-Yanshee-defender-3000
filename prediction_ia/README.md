# Sentinel-X : IA de maintenance prédictive

Détecte en temps réel les dérives des capteurs du boîtier (DHT22, MQ-135) **avant** qu'elles n'atteignent un seuil critique, et envoie des alertes `ia_anomaly` à l'API.

Ce module répond à la partie « maintenance prédictive » du sujet. Les modèles utilisés sont Isolation Forest et Random Forest (scikit-learn). Aucun seuil n'est codé à la main sur une valeur de capteur : chaque décision vient d'un score de modèle, comparé à un seuil appris sur des données normales.

> Explication pour toute l'équipe (rôles, démo, questions du jury) : [GUIDE_EQUIPE.md](GUIDE_EQUIPE.md)

## En une phrase pour le jury

> Le firmware déclenche sur des seuils fixes, avec une référence qui s'adapte ; l'IA apprend le comportement normal de chaque capteur et repère une fuite lente ou une surchauffe **9 à 22 minutes avant le seuil critique**, alors que le firmware, lui, ne la voit jamais.

## Pourquoi le firmware ne suffit pas (constaté, pas supposé)

En simulant exactement la logique gaz du firmware ([firmware_gas.py](firmware_gas.py), portage de `updateGas()`), on observe deux angles morts :

1. **Fuite lente** : quand l'écart est inférieur à 75, la référence rattrape 5 % de l'écart par seconde. Une fuite de +12/min laisse donc un écart stable d'environ 4 : le firmware reste à `normal` pendant toute la fuite, même quand la concentration réelle dépasse +150.
2. **Fuite installée** : au-dessus de 150, la référence remonte lentement. Une fuite de +156 est absorbée en environ 5 minutes, puis le firmware **repasse à `normal` alors que la fuite continue**.

Par ailleurs, le firmware n'a **aucune alerte de température**. Ces deux angles morts sont visibles sur [reports/scenario_demo.png](reports/scenario_demo.png) : la référence du firmware (en pointillés) colle au gaz pendant toute la fuite.

## Comment ça marche

```
ESP8266 ──MQTTS──► Mosquitto ──► anomaly_service.py ──HTTPS──► POST /api/v1/alerts ──► BDD + WebSocket
                                       │
                                       └──MQTTS──► sentinelx/<device>/anomaly ──► API ──WS {"type":"anomaly"}──► dashboard
```

**1. Features** ([features.py](features.py)), calculées chaque seconde par capteur sur un tampon glissant :

| Capteur | Court terme (fenêtres 15 s à 5 min) | Long terme |
|---|---|---|
| Température | valeur, écart à la médiane sur 5 min, vitesse (°C/min) | écart à une référence qui redescend en ~2 min mais ne remonte qu'en ~1 h |
| Humidité | valeur, écart à la médiane sur 5 min, variation sur 15 s | idem |
| Gaz | écart à la référence du firmware, écart à la médiane sur 5 min, vitesse, écart-type sur 10 s | écart à la référence « air propre » long terme |

La mémoire long terme est ce qui permet de voir un incident installé que le firmware a absorbé.

**2. Deux modèles par capteur** ([detector.py](detector.py)) :

- **Isolation Forest** (non supervisé), appris *uniquement* sur du fonctionnement normal. Il signale tout comportement inhabituel, y compris un incident jamais vu.
- **Random Forest** (supervisé), appris sur des incidents simulés étiquetés par la vérité terrain. Il donne le **diagnostic** (surchauffe, fuite lente, fuite franche, humidité) et reste formel quand l'incident est installé. Un Isolation Forest, lui, sature hors de sa plage d'entraînement.

Pourquoi un modèle par capteur : avec 13 features dans un seul Isolation Forest, un écart sur une seule feature n'est isolé que si l'arbre tombe dessus. Les scores d'anomalie restaient alors à peine plus bas que le normal. Avec 4 ou 5 features par modèle, la séparation est nette, et l'alerte dit directement quel capteur dérive.

**3. Indice de risque** : 0 = seconde normale typique, 1 = seuil d'anomalie, valeur maximale des deux modèles. Les seuils sont fixés sur des données normales de validation, jamais vues à l'entraînement, au quantile qui vise 0,05 % de secondes faussement anormales par capteur.

**4. Décision** (anti-rebond) :
- 8 s d'affilée au-dessus de 1 → **alerte** ;
- le diagnostic du Random Forest stable pendant 8 s → **diagnostic confirmé** ;
- un risque jamais vu en fonctionnement normal, ou une fuite franche → **critical** ;
- 20 s sous 1 → **retour à la normale**.

## Résultats

Rapport complet : [reports/evaluation.md](reports/evaluation.md), avec les graphiques par scénario. Tout est évalué sur des données **inédites**, avec la même logique que le service en direct.

| Scénario (20 tirages chacun) | Détection IA | Diagnostic correct | Firmware | Avance de l'IA sur le seuil critique |
|---|---|---|---|---|
| Surchauffe lente (+0,3 à 0,8 °C/min) | 71 s | 20/20 | jamais | 22 min |
| Fuite de gaz lente (+5 à 20 /min) | 61 s | 20/20 | jamais | 9 min |
| Fuite de gaz franche | 7 s (critical) | 20/20 | 4 s | aucune (le firmware est 3 s plus rapide) |
| Hausse d'humidité | 15 s | 19/20 | jamais | — |
| **Démo : chauffe lente + micro-dérive de gaz** | 99 s | 20/20 | jamais | 18 min |

- **Fausses alertes : 0,15 par heure** (7 en 47 h de fonctionnement normal simulé), soit 1,2 % de risque pendant une démo de 5 min.
- **Enregistrement réel du 06/10** (10 min, jamais vu à l'entraînement) : l'IA lève les alertes au bon moment. Elle diagnostique la surchauffe pendant la chauffe à 31,6 °C, l'humidité au moment du souffle, la fuite franche au pic de gaz, puis signale le retour à la normale une fois le boîtier stabilisé.
- Le délai sur une fuite franche est de 7 s : l'anti-rebond coûte 3 s face au firmware. C'est voulu : sur un incident brutal, le firmware reste le premier rempart, et l'IA apporte le diagnostic et le niveau critical.

## Mode d'emploi

```bash
cd prediction_ia
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements-dev.txt
cp .env.example .env        # puis renseigner broker, identifiants, URL et jeton de l'API
```

### 1. Enregistrer du fonctionnement normal réel (à faire en priorité)

Pour l'instant, le modèle est entraîné sur du normal **simulé**, calibré sur le bruit réel des capteurs, faute de données normales réelles : l'enregistrement du 06/10 est une suite de tests. Il faut l'entraîner sur la vraie salle :

```bash
python data_take.py --out data/normal_salle.jsonl --minutes 60
```

Pendant l'enregistrement, le boîtier doit rester **sans manipulation**, à sa place de démo. Des personnes peuvent circuler normalement autour : c'est même souhaitable, le modèle doit l'apprendre comme normal.

### 2. Entraîner et évaluer (≈ 1 min)

```bash
python train.py             # prend automatiquement data/normal_*.jsonl en plus du simulé
python evaluate.py          # régénère reports/ (rapport, graphiques, métriques)
python -m pytest tests      # 10 tests, dont l'équivalence direct / entraînement
```

À relancer sur la machine qui exécutera le service si la version de scikit-learn diffère : un avertissement s'affiche au démarrage dans ce cas.

### 3. Lancer le service

```bash
python anomaly_service.py
```

Il s'abonne à `sentinelx/+/telemetry` et a besoin de **60 s d'historique** avant de produire un score : il faut le lancer avant la démo. Il se reconnecte seul au broker, et les alertes partent dans un thread séparé, avec 3 tentatives.

### 4. Démo

- **Avec le boîtier** :
  - chauffer **lentement**, en approchant progressivement une source de chaleur (sèche-cheveux à distance, main sur le DHT22). Une chauffe brutale est aussi détectée, mais la démo doit montrer la dérive lente ;
  - pour la micro-dérive de gaz : du gel hydroalcoolique ou un feutre à alcool **à quelques dizaines de centimètres**, sans pic franc ;
  - montrer sur le dashboard que l'alerte IA arrive alors que l'OLED affiche toujours `normal`.
- **Démo de secours** (boîtier ou Wi-Fi en panne) : la simulation est publiée sur le broker comme un vrai boîtier (`esp-sim`). Avec `--speed 5`, 20 min de scénario passent en 4 min.

  ```bash
  python simulate.py --scenario demo --minutes 20 --onset 120 --publish --speed 5
  ```

## Intégration (API et dashboard)

**Alertes**, envoyées en `POST /api/v1/alerts` (schéma `AlertCreate` existant) :

```json
{
  "device_id": "esp-01", "source": "ia_anomaly", "alert_type": "gas_drift",
  "level": "warning", "value": 1.5,
  "message": "IA : diagnostic confirmé : Fuite de gaz lente — dérive lente du capteur de gaz (fuite probable) (+13 vs 5 min)",
  "payload": {"event": "diagnosis", "diagnosis": "fuite_lente", "sensor": "gas", "risk": 1.5,
              "rf_probability": 0.75, "if_risk": 0.93, "feature": "gas_dev", "feature_z": 7.2}
}
```

| Champ | Valeurs |
|---|---|
| `alert_type` | `temperature_drift`, `humidity_drift`, `gas_drift` |
| `level` | `warning`, `critical`, `info` (retour à la normale) |
| `payload.event` | `start`, `escalate`, `diagnosis`, `end` |

**Risque en continu** : le service publie sur `sentinelx/<device>/anomaly` chaque seconde. L'API relaie ce topic aux dashboards par WebSocket ([mqtt_client.py](../sentinel-api/app/mqtt_client.py)), sans stockage, et garde la dernière valeur dans `GET /api/v1/status` → `devices.<id>.anomaly`.

```json
{"type": "anomaly", "data": {"device": "esp-01", "risk": 1.96, "risks": {"temperature": 1.07, "humidity": 0.0, "gas": 1.96},
  "alert_active": true, "level": "warning", "diagnosis": "fuite_lente", "diagnosis_label": "Fuite de gaz lente"}}
```

Côté dashboard, il suffit d'une **jauge ou d'une courbe de `risk`** avec une ligne à 1. C'est la meilleure preuve visuelle de « l'inférence IA » pour le jury.

## Données

- `telemetry.jsonl` : session réelle du 06/10. Elle sert à l'évaluation uniquement, pas à l'entraînement, car ce n'est pas du normal.
- `data/normal_*.jsonl` : fonctionnement normal réel, utilisé par `train.py`.
- Simulé ([simulate.py](simulate.py)) : bruit calibré sur les mesures réelles. Résidu gaz ≈ 1,2 contre 0,9 à 1,4 en réel, changements de température 10 % du temps contre 9 %, humidité ± 0,15. Le simulé inclut aussi les dérives lentes de la pièce, les passages près du boîtier et la logique gaz exacte du firmware.
- `data_process.ipynb`, `telemetry.csv`, `telemetry_filtre.csv` : exploration initiale, remplacée par ce pipeline.

## Limites, à dire si on nous les pose

- **Le normal d'entraînement est simulé** tant que l'étape 1 n'est pas faite. Les performances annoncées valent pour un capteur qui se comporte comme le simulateur, calibré sur 10 min de mesures réelles.
- Les **diagnostics** viennent d'incidents simulés : un incident d'un type nouveau est quand même signalé par l'Isolation Forest, comme « comportement inhabituel ».
- La mémoire long terme démarre au lancement du service. S'il est lancé **pendant** un incident, la référence part de la valeur de l'incident.
- Après un incident, le refroidissement ou la décrue du MQ-135 est signalé comme inhabituel jusqu'à stabilisation (1 à 5 min).
