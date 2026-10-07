# Sentinel-X — Firmware ESP8266

Micrologiciel du boîtier Sentinel-X (Workshop 2026, groupe 7).
L'ESP8266 lit les capteurs (température, humidité, gaz, présence), affiche l'état sur l'écran OLED
et publie toutes les mesures sur le broker MQTT. Le buzzer et la LED ne s'allument **que sur commande MQTT**.

```
ESP8266 ──publish──▶ Mosquitto (172.16.137.4:8883, TLS) ◀──subscribe── API / IA / Dashboard
        ◀──── cmd ────                                ──── cmd ────
```

---

## 1. Démarrage rapide (Mac)

### Prérequis
- VS Code + extension **PlatformIO IDE**
- Un câble micro-USB **qui transmet les données** (certains ne font que la charge)
- La carte utilise une puce USB CH340 : reconnue nativement par macOS récent, sinon installer le pilote CH340

### Configurer les identifiants
Les secrets ne sont pas dans git. Copier le modèle puis le remplir :

```bash
cp include/secrets.example.h include/secrets.h
```

```c
#define WIFI_SSID     "..."          // Wi-Fi 2,4 GHz uniquement
#define WIFI_PASSWORD "..."
#define MQTT_HOST "172.16.137.4"
#define MQTT_PORT 8883              // MQTTS (TLS)
#define MQTT_USER "..."
#define MQTT_PASS "..."              // demander à l'équipe infra
```

### Brancher et téléverser
1. Brancher la carte **directement sur le Mac** (éviter les hubs et docks).
2. Vérifier qu'elle est vue :
   ```bash
   ls /dev/cu.usbserial*        # doit afficher par ex. /dev/cu.usbserial-110
   ```
3. Téléverser : bouton **→ (Upload)** dans la barre PlatformIO en bas de VS Code, ou :
   ```bash
   ~/.platformio/penv/bin/pio run -t upload
   ```
   ⚠️ Ne pas cliquer sur l'icône fiole (**Test**) : elle lance les tests unitaires, pas le téléversement.
4. Ouvrir le moniteur série : icône 🔌 dans PlatformIO, ou :
   ```bash
   ~/.platformio/penv/bin/pio device monitor     # 115200 bauds, Ctrl+C pour quitter
   ```

### Ce qu'on doit voir
- Moniteur série : `[WiFi] OK, IP : ...`, puis `[MQTT] connexion TLS a 172.16.137.4:8883 ... OK`, puis une ligne `[MQTT] envoye -> {...}` par seconde.
- Écran OLED : IP de la carte, température/humidité, gaz, présence, statut MQTT.
- Pendant la première minute : `Gaz: chauffe` et `PIR: calib.` (normal, voir §3).

---

## 2. Câblage

Carte : NodeMCU ESP8266 (clone Lolin V3). Le 5 V de la carte s'appelle **VU** (la broche VIN est inutilisable).

| Élément | Broche | GPIO | Remarque |
|---|---|---|---|
| Buzzer actif | D0 | 16 | HIGH = son |
| LED rouge | D1 | 5 | résistance 220 Ω en série |
| DHT22 (DATA) | D2 | 4 | pull-up 10 kΩ entre VCC et DATA |
| PIR HC-SR501 (OUT) | D5 | 14 | sortie 3,3 V, directe |
| OLED SCL | D6 | 12 | I2C logiciel (U8g2) |
| OLED SDA | D7 | 13 | I2C logiciel (U8g2) |
| MQ-135 (AO) | A0 | ADC | via pont diviseur 10 kΩ / 20 kΩ (AO monte à 5 V, A0 max 3,3 V) |

| Module | Alimentation |
|---|---|
| DHT22, OLED | 3,3 V |
| MQ-135, PIR | 5 V (VU) |

**Ne rien brancher sur D3, D4 et D8** : ce sont des broches de démarrage. Si un module les tire au mauvais niveau, la carte
refuse le téléversement (`Failed to connect to ESP8266`). C'est pour ça que l'OLED est sur D6/D7.

---

## 3. Les capteurs : ce qu'il faut savoir

| Capteur | Cadence | Points importants |
|---|---|---|
| DHT22 | toutes les 2 s | Les lectures invalides (NaN, hors plage) sont rejetées → `temperature`/`humidity` à `null`. |
| PIR HC-SR501 | en continu | Ignoré pendant les **30 premières secondes** (calibration). Réglages sensibilité/durée par les potentiomètres du module. |
| MQ-135 | échantillon toutes les 100 ms, moyenné | Chauffe de **60 s**. Ne pas toucher le module, il chauffe. |
| OLED SSD1306 | rafraîchi toutes les 500 ms | Si l'écran reste noir et que c'est un SH1106, changer le constructeur dans `main.cpp`. |

### Détection gaz
Le MQ-135 ne donne pas une concentration fiable : on regarde l'**écart par rapport à l'air calme**.

1. Après les 60 s de chauffe, la carte mémorise la valeur de référence (`baseline`).
2. Niveaux : `normal`, `eleve` si valeur > référence + 150, `alerte` si > référence + 300.
3. Pour redescendre d'un niveau, il faut repasser 30 en dessous du seuil (évite le clignotement entre deux niveaux).
4. La référence suit la dérive lente du capteur (en ~20 s pour le bruit, ~5 min en `eleve`) mais **reste figée en `alerte`**,
   pour qu'une vraie fuite ne soit pas absorbée.

Réglages en haut de `src/main.cpp` : `GAS_THRESHOLD_HIGH`, `GAS_THRESHOLD_ALERT`, `GAS_HYSTERESIS`, `GAS_WARMUP`.

Test : approcher un briquet **sans l'allumer** (gaz ouvert) ou un chiffon imbibé d'alcool.

Le niveau gaz est purement informatif : la carte ne déclenche **aucune alarme toute seule**. C'est au serveur (API / IA)
d'envoyer la commande buzzer.

---

## 4. MQTT

| Topic | Sens | Contenu |
|---|---|---|
| `sentinelx/esp-01/telemetry` | ESP → serveur | mesures JSON, toutes les 1 s |
| `sentinelx/esp-01/status` | ESP → serveur | `online` / `offline` (retained ; `offline` envoyé automatiquement par le broker si la carte disparaît) |
| `sentinelx/esp-01/cmd` | serveur → ESP | commandes buzzer / LED |

Pour suivre tous les boîtiers : s'abonner à `sentinelx/+/telemetry`.

### Chiffrement TLS (MQTTS)

Toute la liaison ESP ↔ broker passe en **TLS 1.2 sur le port 8883**.

- La carte fait confiance **uniquement** à la CA interne de l'infra (`MonInfra Root CA`). Le certificat est dans
  `cert/ca.crt` et embarqué dans le firmware via `include/ca_cert.h` (public, versionné ; aucune clé privée côté ESP).
- Le certificat du broker (`CN=mqtt.monInfra.local`, SAN `IP:172.16.137.4`) doit être signé par cette CA, sinon la
  connexion est refusée : un faux broker (MitM) ne passe pas.
- **Nom d'hôte** : la lib TLS de l'ESP8266 (BearSSL) ne sait pas comparer une IP aux SAN `IP Address`. Quand
  `MQTT_HOST` est une IP, la carte se connecte donc par adresse : la chaîne de certificats est vérifiée, la comparaison
  du nom est sautée. Si on passe à un nom DNS (`mqtt.monInfra.local`), la vérification du nom se fait aussi.
- **Heure** : TLS vérifie les dates de validité, il faut donc une heure correcte. La carte lance une synchro NTP
  (`pool.ntp.org`, modifiable avec `NTP_SERVER` dans `secrets.h`) ; si elle n'a pas abouti (Internet filtré au labo),
  elle utilise **l'heure de compilation du firmware**. Message affiché dans ce cas :
  `(heure NTP absente, heure de compilation utilisee)`. Normal.

Si l'infra régénère sa CA, remplacer `cert/ca.crt` puis régénérer l'en-tête :

```bash
{ echo '#pragma once'; echo '#include <pgmspace.h>'; echo 'static const char CA_CERT[] PROGMEM = R"PEM('; cat cert/ca.crt; echo ')PEM";'; } > include/ca_cert.h
```

Vérifier le certificat présenté par le broker depuis le Mac :

```bash
openssl s_client -connect 172.16.137.4:8883 -CAfile cert/ca.crt -tls1_2 </dev/null | grep -E "subject|Verify return"
```

### Format des mesures
```json
{
  "device": "esp-01",
  "uptime_s": 173,
  "temperature": 27.1,
  "humidity": 52.6,
  "gas": { "raw": 204, "baseline": 204, "level": "normal" },
  "presence": false,
  "rssi": -73,
  "actuators": { "buzzer": "off", "led": "off" }
}
```

| Champ | Description |
|---|---|
| `temperature`, `humidity` | °C et %, `null` si lecture DHT22 invalide |
| `gas.raw` | valeur analogique lissée (0–1023) |
| `gas.baseline` | référence air calme, `null` pendant la chauffe |
| `gas.level` | `chauffe` \| `normal` \| `eleve` \| `alerte` |
| `presence` | PIR, `false` pendant la calibration |
| `rssi` | qualité Wi-Fi en dBm (en dessous de −75, rapprocher la carte du point d'accès) |
| `actuators` | état actuel du buzzer et de la LED |

Pas d'horodatage dans le message : **le serveur horodate à la réception**.

### Commandes buzzer / LED
```json
{"buzzer": "on"}
{"led": "off"}
{"led": "on", "buzzer": "on"}
```
- Valeurs acceptées : `on` / `off`. Tout le reste est ignoré.
- Au démarrage, buzzer et LED sont **éteints**.
- La carte confirme l'état appliqué dans `actuators` du message suivant.
- Si la commande est envoyée en *retained*, la carte la réapplique après un redémarrage.

### Commandes utiles depuis le Mac
Installer le client : `brew install mosquitto` (ou utiliser [MQTT Explorer](https://mqtt-explorer.com/)).

```bash
# Voir tout le flux
mosquitto_sub -h 172.16.137.4 -p 8883 --cafile cert/ca.crt -u <user> -P '<mdp>' -t 'sentinelx/#' -v

# Allumer / éteindre
mosquitto_pub -h 172.16.137.4 -p 8883 --cafile cert/ca.crt -u <user> -P '<mdp>' -t sentinelx/esp-01/cmd -m '{"led":"on","buzzer":"on"}'
mosquitto_pub -h 172.16.137.4 -p 8883 --cafile cert/ca.crt -u <user> -P '<mdp>' -t sentinelx/esp-01/cmd -m '{"led":"off","buzzer":"off"}'

# Vérifier que le broker est joignable
nc -vz 172.16.137.4 8883
```

### Exemple Python (abonnement)
```python
import json, paho.mqtt.client as mqtt
from datetime import datetime, timezone

def on_message(client, userdata, msg):
    data = json.loads(msg.payload)
    data["received_at"] = datetime.now(timezone.utc).isoformat()
    print(msg.topic, data)

client = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2)
client.username_pw_set("<user>", "<mdp>")
client.tls_set(ca_certs="cert/ca.crt")
client.on_message = on_message
client.connect("172.16.137.4", 8883, 60)
client.subscribe("sentinelx/+/telemetry")
client.loop_forever()
```

---

## 5. Dépannage

| Symptôme | Cause probable / solution |
|---|---|
| `Failed to connect to ESP8266: Timed out waiting for packet header` | Un module tire D3/D4/D8. Débrancher l'OLED ou maintenir le bouton **FLASH** pendant `Connecting...`. |
| `Device not configured` / le port `/dev/cu.usbserial*` disparaît | Chute d'alimentation (le MQ-135 consomme beaucoup), hub USB, câble ou connecteur fragile. Brancher en direct sur le Mac, débrancher le 5 V du MQ-135 le temps du téléversement. |
| `could not open port` | Carte débranchée, ou moniteur série déjà ouvert : le fermer avant de téléverser. |
| Erreurs rouges dans VS Code (`'Arduino.h' file not found`) | Erreurs de l'éditeur, pas du compilateur. *PlatformIO: Rebuild IntelliSense Index*. |
| Wi-Fi ne se connecte pas | Nom/mot de passe, et réseau **2,4 GHz** obligatoire. |
| `[MQTT] ... echec (code -2)` | Broker injoignable : IP, port, ou réseau Wi-Fi qui ne route pas vers 172.16.137.x (`nc -vz` depuis le Mac sur le même Wi-Fi). |
| `[MQTT] ... echec (code 5)` | Identifiants MQTT refusés. |
| `echec TLS (... Certificate is expired or not yet valid ...)` | Mauvaise heure : NTP injoignable et firmware compilé avant la création du certificat. Recompiler/téléverser, ou définir `NTP_SERVER` vers un serveur joignable. |
| `echec TLS (... Chain could not be linked to a trust anchor ...)` | Le broker présente un certificat qui n'est pas signé par `cert/ca.crt` (CA régénérée ? mauvais broker ?). |
| `echec TLS (... Expected server name was not found ...)` | `MQTT_HOST` est un nom DNS absent du certificat. Utiliser l'IP ou le nom du certificat. |
| Gaz toujours en `eleve`/`alerte` | Laisser chauffer plusieurs minutes ; la référence se recale seule. Sinon ajuster les seuils (§3). |
| Deux flux différents sur le même topic | Un autre client publie avec le même `device`. Chaque boîtier doit avoir un `DEVICE_ID` unique. |

---

## 6. Organisation du code

```
include/secrets.example.h   modèle des identifiants (versionné)
include/secrets.h           vrais identifiants (ignoré par git)
include/ca_cert.h           CA interne embarquée pour le TLS (copie de cert/ca.crt)
cert/ca.crt                 certificat de la CA interne (public)
src/main.cpp                firmware complet
platformio.ini              carte nodemcuv2, librairies
```

Librairies : DHT sensor library, Adafruit Unified Sensor, U8g2, PubSubClient, ArduinoJson 7.

Ajouter un second boîtier : changer `DEVICE_ID` (`esp-02`) dans `src/main.cpp`, tous les topics suivent.

---

## 7. À faire

- [x] **MQTTS (TLS, port 8883)** avec le certificat CA embarqué.
- [ ] Fermer le port MQTT en clair (1883) sur le broker, sinon un client peut encore se connecter sans chiffrement.
- [ ] Un compte MQTT dédié à l'ESP (`esp`) avec droits limités à `sentinelx/#`, au lieu du compte admin.
- [ ] Dépôt git + commits réguliers.
