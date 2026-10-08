# L'IA prédictive de Sentinel-X, expliquée à l'équipe

Ce document s'adresse à toute l'équipe, Infra comme Dev. Il explique sans jargon ce que fait l'IA de maintenance prédictive, ce que chacun doit faire pour qu'elle marche le jour J, et comment en parler devant le jury.

Pour le détail technique (features, seuils, format JSON exact), voir le [README](README.md). Pour les chiffres et les graphiques, voir le [rapport d'évaluation](reports/evaluation.md).

---

## 1. En 30 secondes

Le boîtier mesure la température, l'humidité et le gaz chaque seconde.

- Le **firmware** déclenche une alerte quand le gaz dépasse un seuil. C'est rapide sur un pic de gaz, mais il a des angles morts.
- L'**IA** a appris à quoi ressemble un boîtier « normal ». Elle signale tout ce qui s'en écarte : une température qui monte doucement, un gaz qui dérive lentement. Elle le fait **plusieurs minutes avant** que le seuil critique soit atteint, et dit **de quel incident il s'agit**.

C'est exactement ce que demande le sujet : « hausse lente de température + micro-dérive de gaz détectée **avant** le seuil critique », sans `if temp > 40`.

---

## 2. Pourquoi le firmware ne suffit pas

Ce n'est pas une supposition : on l'a vérifié en recopiant la logique gaz du firmware en Python ([firmware_gas.py](firmware_gas.py)) et en la soumettant aux mêmes scénarios que l'IA.

Le firmware compare le gaz à une **référence** qui s'adapte doucement, pour suivre la dérive naturelle du capteur. C'est une bonne idée, mais elle a deux effets de bord :

| Situation | Ce que fait le firmware | Ce que fait l'IA |
|---|---|---|
| **Fuite lente** (le gaz monte de quelques points par minute) | La référence monte avec le gaz → l'écart reste petit → **`normal` du début à la fin** | Détecte la montée en ~1 min, diagnostic « fuite lente » |
| **Fuite installée** (le gaz monte d'un coup puis reste haut) | Alerte, puis la référence rattrape le gaz → **repasse à `normal` au bout de ~5 min alors que la fuite continue** | Garde une mémoire long terme de « l'air propre » → l'alerte reste active |
| **Surchauffe** | Le firmware n'a **aucune alerte de température** | Détecte la montée en ~1 min, diagnostic « surchauffe » |
| **Pic de gaz brutal** | Alerte en ~4 s | Alerte en ~7 s, niveau `critical` + diagnostic |

On le voit sur [reports/scenario_demo.png](reports/scenario_demo.png) : la référence du firmware (en pointillés) colle à la courbe du gaz pendant toute la fuite.

**Le message à retenir : le firmware reste le premier réflexe face à un incident brutal, et l'IA voit ce qu'il ne peut pas voir.**

---

## 3. Comment ça marche, simplement

```
 Boîtier ESP8266                         PC serveur
 ┌─────────────┐  MQTTS   ┌───────────┐       ┌─────────────────────┐   HTTPS    ┌─────┐   WebSocket   ┌───────────┐
 │ temp, hum,  ├─────────►│ Mosquitto ├──────►│ anomaly_service.py  ├───────────►│ API ├──────────────►│ Dashboard │
 │ gaz / 1 s   │          └─────┬─────┘       │ (l'IA)              │  alertes   └──┬──┘               └───────────┘
 └─────────────┘                ▲             └──────────┬──────────┘               ▲
                                └────────────────────────┘                          │
                                  risque publié chaque seconde ──────────────────────┘
                                  sur sentinelx/<boîtier>/anomaly
```

Chaque seconde, le service IA :

1. **Regarde l'historique récent** du boîtier (les 6 dernières minutes) et calcule des indicateurs. Non pas « quelle est la température », mais « de combien elle a monté en une minute », « de combien elle s'écarte de son niveau habituel », « est-ce que le gaz est instable ».
2. **Les passe à deux modèles par capteur** :
   - un **Isolation Forest**, qui a appris uniquement le fonctionnement normal et répond à « est-ce que c'est inhabituel ? » ;
   - un **Random Forest**, qui a appris des exemples d'incidents et répond à « si c'est un incident, lequel ? » (surchauffe, fuite lente, fuite franche, humidité).
3. **Calcule un indice de risque** : 0 = tout va bien, **1 = seuil d'alerte**, 2 = très anormal.
4. **Décide**, avec un anti-rebond pour éviter les fausses alertes :
   - risque > 1 pendant 8 s d'affilée → **alerte** envoyée à l'API ;
   - le type d'incident reste le même pendant 8 s → **diagnostic confirmé** ;
   - risque jamais vu en fonctionnement normal, ou fuite franche → niveau **`critical`** ;
   - risque < 1 pendant 20 s → **retour à la normale**.

> **D'où vient le seuil 1 ?** Il n'est pas choisi à la main. On fait passer au modèle des heures de fonctionnement normal qu'il n'a jamais vues, et on place le seuil là où seulement 0,05 % des secondes normales le dépassent. C'est pour ça qu'on peut dire qu'il n'y a « aucun seuil codé en dur ».

---

## 4. Les résultats

Testé sur des données que le modèle n'avait **jamais vues**, avec 20 essais par scénario (pièce, bruit et intensité différents à chaque fois) :

| Scénario | L'IA détecte en | Bon diagnostic | Le firmware détecte | Avance de l'IA sur le seuil critique |
|---|---|---|---|---|
| **Démo : chauffe lente + micro-dérive de gaz** | **~1 min 40** | 20/20 | jamais | **~18 min** |
| Surchauffe lente | ~1 min 10 | 20/20 | jamais | ~22 min |
| Fuite de gaz lente | ~1 min | 20/20 | jamais | ~9 min |
| Fuite de gaz franche | 7 s | 20/20 | 4 s | aucune (le firmware est plus rapide) |
| Hausse d'humidité | 15 s | 19/20 | jamais | — |

- **Fausses alertes** : 0,15 par heure, soit environ **1 % de risque** pendant une démo de 5 minutes.
- **Sur le vrai boîtier** (enregistrement du 06/10, 10 min de tests) : l'IA a levé les bonnes alertes au bon moment. Surchauffe pendant la chauffe, humidité au moment du souffle, fuite au pic de gaz, puis retour à la normale.

---

## 5. Qui fait quoi

### Tout le monde, avant jeudi soir : l'enregistrement « normal »

**C'est le point le plus important.** Aujourd'hui, le fonctionnement « normal » que le modèle a appris est **simulé**, calibré sur le bruit réel de nos capteurs. Il faut lui apprendre la vraie salle.

1. Poser le boîtier **à sa place de démo**, branché, Wi-Fi OK.
2. Lancer :
   ```bash
   python data_take.py --out data/normal_salle.jsonl --minutes 60
   ```
3. **Ne pas toucher le boîtier pendant 1 h** : pas de souffle, pas de chauffe, pas de briquet. Les gens peuvent circuler normalement autour, c'est même souhaitable.
4. Réentraîner (~30 s) : `python train.py`

### Infra

- Le service doit pouvoir joindre **Mosquitto en MQTTS (8883)** et l'**API en HTTPS**.
- Fournir à la personne qui lance le service : l'IP du broker, un compte MQTT (lecture `sentinelx/+/telemetry`, écriture `sentinelx/+/anomaly`), le chemin du `ca.crt`, l'URL de l'API.
- **Changer le mot de passe du broker** : il traîne dans l'historique Git et en dur dans `sentinel-api`. Le pentest de jeudi le trouvera.
- Sur quelle machine tourne le service : n'importe laquelle qui voit le broker et l'API (VM API ou laptop IA). Il ne faut pas de GPU, et il consomme très peu.

### API

- Rien d'obligatoire : les alertes IA arrivent déjà par `POST /api/v1/alerts` avec `source: "ia_anomaly"`.
- **Déjà ajouté** dans [mqtt_client.py](../sentinel-api/app/mqtt_client.py) : le relais du risque vers le dashboard (WebSocket `type: "anomaly"`) et la dernière valeur dans `GET /api/v1/status` → `devices.<id>.anomaly`. Les 13 tests de l'API passent toujours. **À relire par le responsable de l'API.**
- Le service envoie un jeton `Authorization: Bearer` si `API_TOKEN` est rempli dans le `.env`. Si `/api/v1/alerts` exige une auth, donnez-lui un jeton.

### Dashboard

C'est **la preuve visuelle** de l'IA pour le jury, à ne pas négliger :

- **Une jauge ou une courbe du risque**, avec une ligne horizontale à 1. Elle se nourrit des messages WebSocket :
  ```json
  {"type": "anomaly", "data": {"device": "esp-01", "risk": 1.96,
    "risks": {"temperature": 1.07, "humidity": 0.0, "gas": 1.96},
    "alert_active": true, "level": "warning", "diagnosis_label": "Fuite de gaz lente"}}
  ```
- **Les alertes IA** dans la liste d'alertes, avec un badge distinct pour `source = "ia_anomaly"` et le `message`, qui est déjà rédigé en français lisible.
- Idéalement, afficher **côte à côte** l'état firmware (`gas.level` de la télémétrie) et le diagnostic IA. C'est ce contraste qui fait la démo.

### Teaser vidéo

Plan possible pour l'incrustation : la courbe de risque qui franchit la ligne à 1 pendant que l'OLED affiche encore `normal`.

---

## 6. Le jour de la démo

**Avant de passer :**

- [ ] Service IA lancé **au moins 2 minutes avant** (il lui faut 60 s d'historique, et le temps de se stabiliser)
- [ ] Le dashboard affiche la courbe de risque et elle est **sous 1**
- [ ] Le terminal de secours est prêt avec la commande de simulation (voir plus bas)

**Le script (environ 2 min) :**

1. « Le boîtier est au calme : le risque IA est proche de 0. »
2. Chauffer **doucement** : sèche-cheveux à distance ou main autour du DHT22. Pour le gaz, un gel hydroalcoolique ou un feutre à alcool **à quelques dizaines de centimètres**, pas collé au capteur. On veut une dérive lente, pas un pic.
3. Montrer la courbe de risque qui monte, puis l'alerte IA « Surchauffe en cours » ou « Fuite de gaz lente » qui apparaît.
4. **Montrer l'OLED du boîtier : il affiche toujours `normal`.** C'est le moment clé.
5. « L'IA a vu la dérive environ 18 minutes avant le seuil critique, là où les seuils fixes ne voient rien. »

**Plan B** (boîtier ou Wi-Fi en panne) : un faux boîtier `esp-sim` publie sur le broker exactement comme le vrai, en accéléré.

```bash
python simulate.py --scenario demo --minutes 20 --onset 120 --publish --speed 5
```

---

## 7. Questions du jury, réponses préparées

**« Pourquoi pas un simple seuil ? »**
Le sujet l'interdit. Surtout, un seuil fixe ne voit pas une dérive lente : notre propre firmware rate toutes les fuites lentes, on l'a mesuré. L'IA regarde la dynamique (vitesse, écart à l'habitude, mémoire long terme), pas une valeur isolée.

**« Pourquoi deux modèles ? »**
L'Isolation Forest n'a besoin que de données normales et repère même un incident qu'on n'a jamais imaginé. Le Random Forest a appris des exemples d'incidents et dit lequel c'est. Le premier sert d'alarme, le second de diagnostic.

**« Où avez-vous trouvé des données d'incidents ? »**
On a écrit un simulateur calibré sur le bruit réel de nos capteurs (mesuré sur notre enregistrement), qui reproduit exactement la logique du firmware. On peut y provoquer des incidents contrôlés avec une vérité terrain exacte. On n'allait pas créer de vraies fuites de gaz.

**« Comment savez-vous que ça marche ? »**
Évaluation sur des données jamais vues : 20 essais par scénario, 47 h de fonctionnement normal pour compter les fausses alertes, et l'enregistrement réel du boîtier. Rapport complet et graphiques dans `reports/`.

**« Et les fausses alertes ? »**
0,15 par heure, grâce à des seuils calés sur des heures de normal et à un anti-rebond de 8 s.

**« Quelles sont les limites ? »** Mieux vaut les annoncer nous-mêmes :
- le fonctionnement normal a d'abord été appris en simulation, puis complété avec la vraie salle (si l'enregistrement de 1 h a été fait) ;
- sur un pic de gaz brutal, le firmware est 3 s plus rapide : c'est voulu, l'IA apporte le diagnostic et le niveau `critical` ;
- après un incident, le retour à la normale prend 1 à 5 min, le temps que le capteur MQ-135 redescende.

---

## 8. Où est quoi

| Fichier | Rôle |
|---|---|
| [anomaly_service.py](anomaly_service.py) | **Le service à lancer** : écoute le boîtier, calcule le risque, envoie les alertes |
| [train.py](train.py) | Entraîne les modèles (~30 s) → `models/anomaly_model.joblib` |
| [evaluate.py](evaluate.py) | Génère le rapport et les graphiques dans `reports/` |
| [simulate.py](simulate.py) | Simulateur de boîtier : entraînement, tests et **plan B de démo** |
| [data_take.py](data_take.py) | Enregistre la télémétrie réelle dans `data/` |
| [features.py](features.py), [detector.py](detector.py) | Le cœur : indicateurs calculés et décision |
| [firmware_gas.py](firmware_gas.py) | Copie Python de la logique gaz du firmware, pour comparer |
| [reports/](reports/evaluation.md) | Rapport, graphiques et métriques, **à reprendre dans le dossier** |
| `.env.example` | Configuration à copier en `.env` (identifiants, **jamais commité**) |
| `data_process.ipynb`, `telemetry*.csv` | Première exploration, remplacée par le pipeline ci-dessus |

**Installation et lancement :**

```bash
cd prediction_ia
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements-dev.txt
cp .env.example .env          # remplir broker, identifiants, URL et jeton de l'API
python anomaly_service.py
```

Pour régénérer exactement les chiffres de ce document : `python evaluate.py --runs 20 --normal-hours 48`. Une question, un problème : voir Felis.
