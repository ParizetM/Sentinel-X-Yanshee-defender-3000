#include <Arduino.h>
#include <ESP8266WiFi.h>
#include <WiFiClientSecure.h>
#include <time.h>
#include <PubSubClient.h>
#include <ArduinoJson.h>
#include <DHT.h>
#include <U8g2lib.h>
#include "secrets.h"
#include "ca_cert.h"

// Sentinel-X : capteurs (DHT22, MQ-135, PIR) + écran OLED + MQTT sur TLS (MQTTS).
// Câblage : voir le mapping matériel (OLED sur D6/D7, D3/D4/D8 libres).

// --- Broches ---
const int BUZZER_PIN = D0;
const int LED_PIN    = D1;
const int DHT_PIN    = D2;
const int PIR_PIN    = D5;
const int OLED_SCL   = D6;
const int OLED_SDA   = D7;
const int GAS_PIN    = A0;

#define DHTTYPE DHT22
DHT dht(DHT_PIN, DHTTYPE);

// Si ton écran est un SH1106, remplace SSD1306 par SH1106 sur la ligne suivante
U8G2_SSD1306_128X64_NONAME_F_SW_I2C u8g2(U8G2_R0, OLED_SCL, OLED_SDA, U8X8_PIN_NONE);

// --- Réseau ---
const char* DEVICE_ID = "esp-01";

// Serveur NTP (surchargeable dans secrets.h, ex. l'IP de la passerelle si Internet est filtré)
#ifndef NTP_SERVER
#define NTP_SERVER "pool.ntp.org"
#endif
char topicTelemetry[48];
char topicStatus[48];
char topicCmd[48];

// TLS : le certificat du broker doit être signé par la CA interne (include/ca_cert.h).
BearSSL::X509List caCert(CA_CERT);
BearSSL::WiFiClientSecure tlsClient;
PubSubClient mqtt(tlsClient);

// --- Durées (ms) ---
const unsigned long PUBLISH_INTERVAL    = 1000;
const unsigned long RECONNECT_INTERVAL  = 5000;
const unsigned long DHT_INTERVAL        = 2000;
const unsigned long GAS_SAMPLE_INTERVAL = 100;
const unsigned long GAS_INTERVAL        = 1000;
const unsigned long OLED_INTERVAL       = 500;
const unsigned long PIR_WARMUP          = 30000;
const unsigned long GAS_WARMUP          = 60000;  // le MQ-135 doit chauffer, plus c'est long, plus c'est stable

// --- Seuils gaz (écart par rapport à l'air calme mesuré après le chauffage) ---
const int GAS_THRESHOLD_HIGH  = 150;
const int GAS_THRESHOLD_ALERT = 300;
const int GAS_HYSTERESIS      = 30;   // il faut redescendre de 30 sous un seuil pour quitter le niveau

// Vitesse à laquelle la référence suit l'air ambiant (fraction de l'écart rattrapée par seconde)
const float GAS_TRACK_FAST = 0.05;    // petit écart : bruit normal, suivi en ~20 s
const float GAS_TRACK_SLOW = 0.003;   // niveau "eleve" : dérive lente du capteur, suivi en ~5 min
const float GAS_TRACK_DOWN = 0.1;     // l'air redevient plus propre que la référence

// --- État des capteurs ---
bool dhtOk = false;
float temperature = 0;
float humidity = 0;
float gasFiltered = -1;
int gasValue = 0;
float gasBaseline = -1;
int gasState = 0;  // 0 = normal, 1 = eleve, 2 = alerte
bool presence = false;
bool lastPresence = false;

// --- Actionneurs (pilotés par sentinelx/<device>/cmd) ---
// Mode alerte : le buzzer bipe une fois par seconde, la LED clignote au même rythme.
// Inactifs au démarrage, ils ne changent que sur commande : aucun déclenchement automatique.
const unsigned long ALERT_PERIOD = 1000;  // un cycle par seconde
const unsigned long BEEP_ON      = 200;   // durée du bip au début de chaque cycle
const unsigned long LED_ON       = 500;   // durée d'allumage de la LED au début de chaque cycle

bool buzzerAlert = false;
bool ledAlert = false;
unsigned long buzzerUntil = 0;  // arrêt automatique (0 = jusqu'à nouvel ordre)
unsigned long ledUntil = 0;
unsigned long alertStart = 0;   // origine commune des cycles : bip et LED restent synchronisés

unsigned long lastPublish = 0, lastReconnect = 0, lastDht = 0, lastGasSample = 0, lastGas = 0, lastOled = 0;
bool wifiWasConnected = false;

// ===================== Capteurs =====================

void readDht() {
  float h = dht.readHumidity();
  float t = dht.readTemperature();

  if (isnan(h) || isnan(t) || t < -40 || t > 80 || h < 0 || h > 100) {
    dhtOk = false;
    Serial.println("DHT22 : lecture invalide");
    return;
  }

  temperature = t;
  humidity = h;
  dhtOk = true;
}

const char* gasLevel();

// Moyenne glissante sans delay() : un échantillon toutes les 100 ms.
void sampleGas() {
  int raw = analogRead(GAS_PIN);
  gasFiltered = gasFiltered < 0 ? raw : gasFiltered + (raw - gasFiltered) * 0.2;
}

void updateGas(unsigned long now) {
  gasValue = (int)gasFiltered;

  if (now >= GAS_WARMUP && gasBaseline < 0) {
    gasBaseline = gasFiltered;
    Serial.printf("Gaz : valeur de reference = %.0f\n", gasBaseline);
  } else if (gasBaseline >= 0) {
    // La référence suit la dérive lente du capteur, mais reste figée pendant une alerte
    // pour qu'une vraie fuite ne soit pas absorbée.
    float delta = gasValue - gasBaseline;
    if (delta < 0) {
      gasBaseline += delta * GAS_TRACK_DOWN;
    } else if (delta < GAS_THRESHOLD_HIGH / 2) {
      gasBaseline += delta * GAS_TRACK_FAST;
    } else if (delta < GAS_THRESHOLD_ALERT) {
      gasBaseline += delta * GAS_TRACK_SLOW;
    }
  }

  if (gasBaseline >= 0) {
    int delta = gasValue - gasBaseline;
    int previous = gasState;
    if (delta > GAS_THRESHOLD_ALERT) {
      gasState = 2;
    } else if (delta > GAS_THRESHOLD_HIGH) {
      gasState = (gasState == 2 && delta > GAS_THRESHOLD_ALERT - GAS_HYSTERESIS) ? 2 : 1;
    } else if (gasState >= 1 && delta > GAS_THRESHOLD_HIGH - GAS_HYSTERESIS) {
      gasState = 1;
    } else {
      gasState = 0;
    }
    if (gasState != previous) {
      Serial.printf("Gaz : %s (valeur %d, reference %.0f)\n", gasLevel(), gasValue, gasBaseline);
    }
  }
}

const char* gasLevel() {
  if (gasBaseline < 0) return "chauffe";
  if (gasState == 2) return "alerte";
  if (gasState == 1) return "eleve";
  return "normal";
}

void readPir(unsigned long now) {
  if (now < PIR_WARMUP) {
    presence = false;
    return;
  }

  presence = digitalRead(PIR_PIN) == HIGH;

  if (presence != lastPresence) {
    lastPresence = presence;
    Serial.println(presence ? "PRESENCE detectee" : "Plus de presence");
  }
}

// ===================== Actionneurs =====================

// Format attendu (contrat d'interface §4.3) :
//   {"target": "buzzer" | "led" | "all", "state": "toggle" | "on" | "off", "duration_ms": 10000}
// - state absent ou "toggle" : la même commande démarre puis arrête le mode alerte
// - "on" / "off" : force l'état (utile pour un bouton « tout arrêter »)
// - duration_ms (optionnel, avec on/toggle) : arrêt automatique après ce délai
void setAlert(bool& alert, unsigned long& until, bool enable, unsigned long durationMs, unsigned long now) {
  if (enable && !buzzerAlert && !ledAlert) alertStart = now;  // premier actionneur activé : nouveau cycle
  alert = enable;
  until = (enable && durationMs > 0) ? now + durationMs : 0;
}

void onCommand(char* topic, byte* payload, unsigned int length) {
  JsonDocument doc;
  DeserializationError err = deserializeJson(doc, payload, length);
  if (err) {
    Serial.printf("[CMD] JSON invalide : %s\n", err.c_str());
    return;
  }

  const char* target = doc["target"] | "";
  const char* state = doc["state"] | "toggle";
  unsigned long durationMs = doc["duration_ms"] | 0UL;

  bool all = strcmp(target, "all") == 0;
  bool forBuzzer = all || strcmp(target, "buzzer") == 0;
  bool forLed = all || strcmp(target, "led") == 0;
  if (!forBuzzer && !forLed) {
    Serial.printf("[CMD] target inconnu : \"%s\"\n", target);
    return;
  }

  bool enable;
  if (strcmp(state, "on") == 0) {
    enable = true;
  } else if (strcmp(state, "off") == 0) {
    enable = false;
  } else if (strcmp(state, "toggle") == 0) {
    // Avec "all", on bascule l'ensemble : si l'un des deux est en alerte, tout s'arrête.
    bool active = (forBuzzer && buzzerAlert) || (forLed && ledAlert);
    enable = !active;
  } else {
    Serial.printf("[CMD] state inconnu : \"%s\"\n", state);
    return;
  }

  unsigned long now = millis();
  if (forBuzzer) setAlert(buzzerAlert, buzzerUntil, enable, durationMs, now);
  if (forLed)    setAlert(ledAlert, ledUntil, enable, durationMs, now);

  Serial.printf("[CMD] alerte buzzer=%s led=%s\n", buzzerAlert ? "on" : "off", ledAlert ? "on" : "off");
}

// Fait vivre le mode alerte sans bloquer la boucle (pas de delay()).
void updateActuators(unsigned long now) {
  if (buzzerAlert && buzzerUntil && (long)(now - buzzerUntil) >= 0) buzzerAlert = false;
  if (ledAlert && ledUntil && (long)(now - ledUntil) >= 0) ledAlert = false;

  unsigned long phase = (now - alertStart) % ALERT_PERIOD;
  digitalWrite(BUZZER_PIN, buzzerAlert && phase < BEEP_ON);
  digitalWrite(LED_PIN, ledAlert && phase < LED_ON);
}

// ===================== MQTT =====================

// Le TLS vérifie les dates de validité des certificats : il faut une heure correcte.
// On prend l'heure NTP si elle est arrivée, sinon l'heure de compilation du firmware
// (suffisant pour être dans la période de validité si le réseau bloque NTP).
const time_t TIME_VALID_AFTER = 1700000000;  // 2023 : en dessous, l'heure NTP n'est pas encore reçue

time_t tlsTime() {
  time_t now = time(nullptr);
  if (now > TIME_VALID_AFTER) return now;
  return BUILD_EPOCH;
}

void publishTelemetry() {
  JsonDocument doc;
  doc["device"] = DEVICE_ID;
  doc["uptime_s"] = millis() / 1000;
  if (dhtOk) {
    doc["temperature"] = serialized(String(temperature, 1));
    doc["humidity"] = serialized(String(humidity, 1));
  } else {
    doc["temperature"] = nullptr;
    doc["humidity"] = nullptr;
  }
  JsonObject g = doc["gas"].to<JsonObject>();
  g["raw"] = gasValue;
  if (gasBaseline >= 0) g["baseline"] = (int)gasBaseline;
  else                  g["baseline"] = nullptr;
  g["level"] = gasLevel();
  doc["presence"] = presence;
  doc["rssi"] = WiFi.RSSI();
  JsonObject a = doc["actuators"].to<JsonObject>();
  a["buzzer"] = buzzerAlert ? "alert" : "off";
  a["led"] = ledAlert ? "alert" : "off";

  char buffer[384];
  serializeJson(doc, buffer, sizeof(buffer));

  bool ok = mqtt.publish(topicTelemetry, buffer);
  Serial.printf("[MQTT] %s -> %s\n", ok ? "envoye" : "ECHEC", buffer);
}

void connectMqtt() {
  Serial.printf("[MQTT] connexion TLS a %s:%u ... ", MQTT_HOST, MQTT_PORT);

  time_t now = tlsTime();
  tlsClient.setX509Time(now);
  if (now == BUILD_EPOCH) Serial.print("(heure NTP absente, heure de compilation utilisee) ");

  String clientId = String("sentinelx-") + DEVICE_ID;
  bool ok;
  if (strlen(MQTT_USER) > 0) {
    ok = mqtt.connect(clientId.c_str(), MQTT_USER, MQTT_PASS, topicStatus, 1, true, "offline");
  } else {
    ok = mqtt.connect(clientId.c_str(), nullptr, nullptr, topicStatus, 1, true, "offline");
  }

  if (ok) {
    Serial.println("OK");
    mqtt.publish(topicStatus, "online", true);
    mqtt.subscribe(topicCmd);
  } else {
    char err[96];
    int code = tlsClient.getLastSSLError(err, sizeof(err));
    if (code != 0) {
      Serial.printf("echec TLS (%d : %s)\n", code, err);
    } else {
      Serial.printf("echec (code MQTT %d)\n", mqtt.state());
    }
  }
}

void handleNetwork(unsigned long now) {
  bool wifiConnected = WiFi.status() == WL_CONNECTED;
  if (wifiConnected != wifiWasConnected) {
    wifiWasConnected = wifiConnected;
    if (wifiConnected) {
      Serial.printf("[WiFi] OK, IP : %s, passerelle : %s\n",
                    WiFi.localIP().toString().c_str(), WiFi.gatewayIP().toString().c_str());
      configTime(0, 0, NTP_SERVER);  // synchro en arrière-plan, non bloquante
    } else {
      Serial.println("[WiFi] deconnecte");
    }
  }
  if (!wifiConnected) return;

  if (!mqtt.connected()) {
    if (lastReconnect == 0 || now - lastReconnect >= RECONNECT_INTERVAL) {
      lastReconnect = now;
      connectMqtt();
    }
    return;
  }

  mqtt.loop();

  if (now - lastPublish >= PUBLISH_INTERVAL) {
    lastPublish = now;
    publishTelemetry();
  }
}

// ===================== OLED =====================

void drawOled(unsigned long now) {
  char line[28];

  u8g2.clearBuffer();
  u8g2.setFont(u8g2_font_6x10_tf);

  if (WiFi.status() == WL_CONNECTED) {
    snprintf(line, sizeof(line), "%s", WiFi.localIP().toString().c_str());
  } else {
    snprintf(line, sizeof(line), "WiFi: connexion...");
  }
  u8g2.drawStr(0, 10, line);

  if (dhtOk) {
    snprintf(line, sizeof(line), "T:%.1fC  H:%.1f%%", temperature, humidity);
  } else {
    snprintf(line, sizeof(line), "DHT22 : erreur");
  }
  u8g2.drawStr(0, 22, line);

  if (gasBaseline < 0) {
    unsigned long left = now < GAS_WARMUP ? (GAS_WARMUP - now) / 1000 : 0;
    snprintf(line, sizeof(line), "Gaz: chauffe %lus", left);
  } else {
    snprintf(line, sizeof(line), "Gaz:%d %s", gasValue, gasLevel());
  }
  u8g2.drawStr(0, 34, line);

  if (now < PIR_WARMUP) {
    snprintf(line, sizeof(line), "PIR: calib. %lus", (PIR_WARMUP - now) / 1000);
  } else {
    snprintf(line, sizeof(line), "Presence: %s", presence ? "OUI" : "non");
  }
  u8g2.drawStr(0, 46, line);

  snprintf(line, sizeof(line), "MQTTS: %s", mqtt.connected() ? "connecte" : "hors ligne");
  u8g2.drawStr(0, 58, line);

  u8g2.sendBuffer();
}

// ===================== Programme =====================

void setup() {
  pinMode(BUZZER_PIN, OUTPUT);
  pinMode(LED_PIN, OUTPUT);
  pinMode(PIR_PIN, INPUT);
  digitalWrite(BUZZER_PIN, LOW);
  digitalWrite(LED_PIN, LOW);

  Serial.begin(115200);
  Serial.println();
  Serial.println("Sentinel-X - capteurs + MQTTS");

  snprintf(topicTelemetry, sizeof(topicTelemetry), "sentinelx/%s/telemetry", DEVICE_ID);
  snprintf(topicStatus, sizeof(topicStatus), "sentinelx/%s/status", DEVICE_ID);
  snprintf(topicCmd, sizeof(topicCmd), "sentinelx/%s/cmd", DEVICE_ID);

  dht.begin();
  u8g2.begin();

  // Connexion Wi-Fi en arrière-plan : les capteurs tournent même sans réseau.
  WiFi.mode(WIFI_STA);
  WiFi.setAutoReconnect(true);
  WiFi.begin(WIFI_SSID, WIFI_PASSWORD);

  tlsClient.setTrustAnchors(&caCert);

  // BearSSL ne sait pas comparer un nom d'hôte à une IP du certificat (SAN "IP Address").
  // Avec une IP, on se connecte donc par adresse : la chaîne de certificats reste vérifiée
  // contre la CA interne, seule la comparaison du nom est sautée. Avec un nom DNS, tout est vérifié.
  IPAddress brokerIp;
  if (brokerIp.fromString(MQTT_HOST)) {
    mqtt.setServer(brokerIp, MQTT_PORT);
  } else {
    mqtt.setServer(MQTT_HOST, MQTT_PORT);
  }
  mqtt.setBufferSize(512);
  mqtt.setCallback(onCommand);

  readDht();
  sampleGas();
}

void loop() {
  unsigned long now = millis();

  readPir(now);

  if (now - lastDht >= DHT_INTERVAL) {
    lastDht = now;
    readDht();
  }

  if (now - lastGasSample >= GAS_SAMPLE_INTERVAL) {
    lastGasSample = now;
    sampleGas();
  }

  if (now - lastGas >= GAS_INTERVAL) {
    lastGas = now;
    updateGas(now);
  }

  handleNetwork(now);
  updateActuators(now);

  if (now - lastOled >= OLED_INTERVAL) {
    lastOled = now;
    drawOled(now);
  }
}
