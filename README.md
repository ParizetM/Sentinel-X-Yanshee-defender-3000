# SENTINEL-X : Vision globale du projet

> Workshop national EPSI Bac+4, session octobre 2026 (sprint de 4 jours + soutenance)
> Groupe : Elios, Benoit, Felis, Martin, Matis
> Document de travail interne. Les éléments marqués **[PROPOSITION]** sont à valider en équipe, ceux marqués **[À VALIDER COACHS]** doivent passer par les coachs lundi.

---

## 1. Le projet en bref

AetherCorp Industrial Solutions (fiction, année 2050) exploite des micro-centrales énergétiques en zones isolées, exposées à trois menaces :

1. **Cyberattaques** de déstabilisation réseau
2. **Intrusions physiques** (espionnage industriel)
3. **Risques environnementaux** (fuite de gaz, surchauffe)

**Mission** : livrer un prototype cyber-physique complet, composé de :

- un **boîtier autonome** (Edge Node) équipé d'un ESP8266 et de capteurs
- un **PC Serveur Local** (centre de commandement) qui héberge la stack serveur, l'IA et le dashboard
- une **IA** de vision (détection d'intrus) et de maintenance prédictive (anomalies sur séries temporelles)
- une **sécurité de bout en bout** (TLS, hardening, pentest croisé)
- des **livrables Fablab** : boîtier imprimé en 3D, gravure laser, teaser vidéo de 60 s

**Règle éliminatoire** : l'interconnexion fonctionnelle de tous les blocs est obligatoire pour valider la démo finale du vendredi.

---

## 2. Équipe et répartition

| Pôle | Membres | Périmètre |
|---|---|---|
| **INFRA** | Elios, Benoit | Proxmox, VLAN, réseau, Docker, Galera, Mosquitto, Ansible, hardening |
| **DEV** | Felis, Martin, Matis | Firmware ESP8266, API REST, dashboard React, script IA |

> Note : le message d'origine listait « DevOps » deux fois. J'ai supposé que le second groupe est **DEV**. À corriger si besoin.

### Répartition des 3 devs **[PROPOSITION]**

| Dev | Périmètre principal | Périmètre secondaire |
|---|---|---|
| Dev 1 | Firmware ESP8266 (C++), câblage | Boîtier : CAO Fusion360, impression 3D, gravure laser |
| Dev 2 | API REST Python, ingestion MQTT, base de données | Intégration TLS côté applicatif |
| Dev 3 | Dashboard React | Script IA (vision + anomalies), à partager avec Dev 2 une fois l'API prête |

Le Dev 3 est le plus chargé. Prévoir de déléguer une partie de l'IA ou du teaser vidéo.

### Sécurité (point d'attention)

Le groupe n'a **aucun profil CYBER dédié**, alors que la sécurité pèse dans l'évaluation (Axe 2 de la soutenance) et que le pentest croisé a lieu le jeudi. La sécurité est donc **portée par INFRA** (hardening, TLS, pare-feu) et chaque dev est responsable de la sécurité de sa brique.

---

## 3. Architecture technique

### 3.1 Vue d'ensemble

```
                          ┌──────────────────────────────────────────┐
                          │         VLAN dédié "Table" (Proxmox)     │
                          │                                          │
 ┌────────────┐  Wi-Fi    │  ┌───────────────┐    ┌───────────────┐  │
 │  Boîtier   │  MQTTS    │  │  VM Mosquitto │    │ VM API #1     │  │
 │  ESP8266   ├───────────┼─►│  (broker)     │◄──►│ (docker-comp.)│  │
 │  + capteurs│◄──────────┼──┤               │    ├───────────────┤  │
 │  + OLED    │ commandes │  └───────┬───────┘    │ VM API #2     │  │
 └────────────┘           │          │            │ (docker-comp.)│  │
                          │          ▼            └───────┬───────┘  │
                          │  ┌───────────────────────────┐│          │
                          │  │ Cluster Galera (2 VM + ?) │◄┘         │
                          │  └───────────────────────────┘           │
                          └──────────────────┬───────────────────────┘
                                             │
   ┌───────────────┐   flux vidéo   ┌────────┴──────────┐
   │ Webcam USB    ├───────────────►│ Machine avec la   │  alertes IA → API
   │               │                │ webcam + script IA│─────────────────►
   └───────────────┘                └───────────────────┘
                                             
   ┌────────────────────┐   HTTPS / WebSocket
   │ Dashboard React    │◄─────────────────────  API
   └────────────────────┘
```

### 3.2 Flux de données

| # | Flux | Protocole | Sécurité |
|---|---|---|---|
| 1 | ESP8266 → Mosquitto (mesures) | MQTT sur TLS (8883) | MQTTS + auth |
| 2 | Mosquitto → API (ingestion) | MQTT | TLS + auth |
| 3 | API → Galera (stockage) | SQL | Utilisateur dédié, droits minimaux |
| 4 | Dashboard → API | HTTPS + WebSocket | Jeton d'authentification |
| 5 | Dashboard → API → Mosquitto → ESP8266 (commandes buzzer/LED) | HTTPS puis MQTTS | Auth + autorisation |
| 6 | Script IA → API (alertes d'intrusion/anomalie) | HTTPS (`POST /api/v1/alerts`) | Jeton |
| 7 | Webcam → script IA → dashboard (flux annoté) | USB puis MJPEG/HTTPS | Auth |

### 3.3 Composants

#### Matériel fourni (sujet)

| Composant | Quantité | Rôle |
|---|---|---|
| ESP8266 | 1 à 2 | Collecte capteurs, pilotage alertes locales |
| Webcam USB | 1 | Capture vidéo, **branchée directement sur le PC Serveur Local** |
| DHT22 | 1 | Température et humidité |
| MQ-2 | 1 | Gaz et fumées |
| PIR HC-SR501 | 1 | Détection de présence |
| Écran OLED I2C 0.96" | 1 | Statut IP/Wi-Fi |
| Buzzers, LEDs, breadboards, jumpers | n | Alertes et câblage |
| Imprimante 3D (Creality K2 Plus) | | Coque du boîtier |
| Graveuse/découpeuse laser (Creality Falcon A1) | | Logo, consignes, n° de série |

#### Stack logicielle

| Domaine | Choix de l'équipe |
|---|---|
| Firmware | C++ (Arduino IDE ou PlatformIO), ESP8266 |
| API | Python (REST + WebSocket) |
| Dashboard | React (courbes temps réel, flux caméra, panneau de contrôle) |
| IA | Python : détection de personne (YOLOv8-tiny ou OpenCV), anomalies (Isolation Forest / Random Forest, scikit-learn) |
| Base de données | MariaDB en cluster Galera |
| Broker | Eclipse Mosquitto |
| Conteneurs | Docker + docker-compose |
| Virtualisation | Proxmox (déjà en place) |
| Automatisation | Ansible |
| CAO | Fusion360 (imposé) |

### 3.4 Infrastructure cible

| Brique | VM | Détail |
|---|---|---|
| Broker Mosquitto | 1 VM | Conteneur Docker, TLS, authentification |
| API | 2 VM | docker-compose par VM, redondance |
| Base de données | 2 VM (+ arbitre) | Cluster Galera |
| Réseau | VLAN dédié | Isolation des autres groupes |

**Plan d'adressage [PROPOSITION]** (le sujet donne `192.168.10.0/24` comme exemple) :

| Rôle | IP |
|---|---|
| Passerelle / routeur du VLAN | 192.168.10.1 |
| VM Mosquitto | 192.168.10.10 |
| VM API 1 | 192.168.10.11 |
| VM API 2 | 192.168.10.12 |
| VM Galera 1 | 192.168.10.21 |
| VM Galera 2 | 192.168.10.22 |
| Machine IA + webcam | 192.168.10.30 |
| ESP8266 | 192.168.10.50 |

### 3.5 Points d'architecture à trancher **[À VALIDER COACHS]**

1. **Quorum Galera.** Avec 2 nœuds, la perte d'un seul bloque le cluster (pas de majorité). Solutions : un 3ᵉ nœud, ou un arbitre `garbd` (léger, peut tourner sur la VM du broker).
2. **Emplacement de la webcam et de l'IA.** Le sujet impose que la webcam USB soit branchée **directement sur le PC Serveur Local**. Or l'infra est sur des VM Proxmox. Le script IA doit donc tourner sur une machine qui a physiquement la webcam (un laptop d'apprenant, comme l'option B du sujet), ou il faut un passthrough USB vers une VM. À faire valider lundi.
3. **Option A ou B du sujet** (Raspberry Pi 5 embarqué, ou laptop d'apprenant). Notre architecture Proxmox ressemble à une variante de l'option B. À présenter comme « variante d'architecture sélectionnée » lors de la soutenance.
4. **« Connectivité Yanshee (Yang Chi) »** figure dans le tableau de départ mais n'apparaît pas dans le sujet. À clarifier (robot Yanshee d'UBTech ?). En attendant, classé P3.

---

## 4. Contrat d'interface **[À FIGER LUNDI]**

C'est le risque n°1 du projet : sans contrat partagé dès lundi, l'intégration de mercredi échouera.

### 4.1 Topics MQTT **[PROPOSITION]**

| Topic | Sens | Contenu |
|---|---|---|
| `sentinel/<device_id>/telemetry` | ESP → broker | Mesures périodiques |
| `sentinel/<device_id>/status` | ESP → broker | En ligne/hors ligne (Last Will) |
| `sentinel/<device_id>/event` | ESP → broker | Changement d'état (PIR déclenché, seuil franchi) |
| `sentinel/<device_id>/cmd` | API → ESP | Commandes buzzer/LED |

### 4.2 Payload de télémétrie **[PROPOSITION]**

```json
{
  "device_id": "sentinel-01",
  "ts": "2026-10-07T10:15:30Z",
  "temperature": 24.6,
  "humidity": 48.2,
  "gas": 312,
  "pir": false
}
```

### 4.3 Payload de commande **[PROPOSITION]**

```json
{ "target": "buzzer", "state": "on", "duration_ms": 3000 }
```

### 4.4 Routes API **[PROPOSITION]**

| Méthode | Route | Rôle |
|---|---|---|
| POST | `/api/v1/alerts` | **Imposé par le sujet** : réception des changements d'état et alertes (capteurs, IA) |
| GET | `/api/v1/measurements?from=&to=` | Historique pour les courbes |
| GET | `/api/v1/status` | État du boîtier |
| GET | `/api/v1/alerts` | Liste des alertes récentes |
| POST | `/api/v1/commands` | Commande d'un actionneur (relayée en MQTT) |
| WS | `/ws` | Flux temps réel vers le dashboard |
| GET | `/api/v1/camera/stream` | Flux annoté (ou servi directement par le script IA) |
| POST | `/api/v1/auth/login` | Obtention du jeton |

### 4.5 Modèle de données minimal **[PROPOSITION]**

| Table | Champs principaux |
|---|---|
| `measurements` | id, device_id, ts, temperature, humidity, gas, pir |
| `alerts` | id, device_id, ts, source (sensor/ia_vision/ia_anomaly), level, message, payload |
| `commands` | id, ts, user, target, state, status |
| `users` | id, login, password_hash, role |

---

## 5. Détail par pôle

### 5.1 INFRA

**Proxmox et réseau**
- Accès aux VM **uniquement par clé SSH** (`PasswordAuthentication no`)
- VLAN dédié sur un bridge VLAN-aware, **aucune communication** avec les autres tables
- Plan d'adressage (IP, masques, passerelle) et schéma réseau **validés par les coachs lundi** (obligatoire)
- Point d'accès Wi-Fi de table pour l'ESP8266, isolé des autres groupes

**Docker**
- Mosquitto (1 VM) : volumes persistants, auth activée, TLS
- Galera : cluster réplicable, utilisateur applicatif aux droits minimaux
- API : docker-compose sur 2 VM, répartition de charge ou bascule documentée
- `restart: unless-stopped` et `healthcheck` sur chaque service
- Secrets dans des `.env` **hors dépôt**

**Ansible**
- Inventaire par rôle (api, db, broker)
- Playbook socle idempotent (paquets, Docker, utilisateurs, SSH)
- Un rôle par service + un rôle `hardening`
- Objectif : reconstruire toute l'infra en une commande

**Hardening et monitoring (exigés par le sujet)**
- Pare-feu UFW/iptables : politique par défaut `deny`, matrice flux/ports documentée
- Conteneurs non-root, pas de `--privileged`, réseaux Docker séparés
- Suivi CPU/RAM et volume de logs MQTT (MCO), rotation des logs
- PKI interne (CA + certificats) pour MQTTS et HTTPS

### 5.2 DEV

**Firmware ESP8266 (C++)**
- Lecture cadencée DHT22, MQ-2, PIR
- Affichage OLED : IP, état Wi-Fi/MQTT, dernière mesure
- Publication MQTT/TLS (certificat CA embarqué), payloads JSON structurés
- Abonnement au topic de commande : buzzer et LED (réaction < 1 s)
- Reconnexion automatique Wi-Fi et broker

**API Python**
- Ingestion MQTT vers Galera
- Endpoints REST (voir 4.4) + WebSocket
- Authentification par jeton, HTTPS
- Relais des commandes vers MQTT

**Dashboard React**
- Courbes temps réel (température, humidité, gaz, présence)
- Statut du boîtier et liste des alertes
- Flux webcam avec détections incrustées
- Panneau de contrôle (buzzer, LED)
- Page de connexion

**IA (script Python)**
- *Vision* : capture webcam, redimensionnement (ex. 640×480), inférence YOLOv8-tiny ou OpenCV, **< 100 ms par trame**, alerte vers l'API en cas de personne détectée
- *Maintenance prédictive* : modèle Isolation Forest ou Random Forest. **Les simples `if temp > 40` sont interdits.** Scénario de démo : hausse lente de température + micro-dérive de gaz détectée avant le seuil critique → implémenté dans [prediction_ia/](prediction_ia/README.md) (Isolation Forest + Random Forest par capteur, service temps réel, rapport d'évaluation)
- Documentation : modèle, données, métriques (pour le dossier)

**Fablab**
- Boîtier modélisé sous **Fusion360 exclusivement** : encapsule l'ESP8266 et les capteurs, laisse voir l'OLED, passe-câbles propres, aucun fil apparent
- Gravure laser : logo AetherCorp, consignes de sécurité, numéro de série (plexiglas, bois ou carton épais)

---

## 6. Planning du sprint

| Jour | Thème | Objectifs de l'équipe | Jalon |
|---|---|---|---|
| **Lundi 5 oct** | Kick-off, idéation, design | Constitution du groupe, schémas d'architecture réseau et flux de données, **contrat d'interface figé**, plan IP, première modélisation CAO, VLAN et accès SSH | Schémas validés par les coachs |
| **Mardi 6 oct** | Production core | Câblage sur plaque, conteneurs sur le serveur, firmware ESP8266, architecture de l'API, premiers entraînements IA, PKI et TLS, Ansible socle | Mesures qui remontent ESP → broker → API → base |
| **Mercredi 7 oct** | Intégration et studio vidéo | Interconnexion Edge-to-Server, graphiques temps réel, IA sur la webcam, commandes à distance, auto-audit, **tournage du teaser** l'après-midi (fond vert) | Chaîne complète fonctionnelle |
| **Jeudi 8 oct** | Hacking day | Matin : **gel du code**, finitions du boîtier. Après-midi : **pentest croisé**, rapport d'audit. **Dépôt des livrables le soir** | Livrables déposés |
| **Vendredi 9 oct** | Soutenance locale | **Dépôt du prototype au myDiL le matin**, soutenance devant le jury, résultats du campus | Champion de campus désigné |
| **17 nov 2026** | Finale nationale (Teams) | 10 campus champions, 5 min de passage en direct | : |

**Rappels du sujet** : émargement Edusign dans les 15 premières minutes de chaque demi-journée, salles et myDiL propres chaque soir, présence obligatoire aux soutenances et à la retransmission de la finale.

---

## 7. Livrables

Dépôt dans un dossier unique `Workshop2026-M1-G<n>` (lien fourni par les coachs lundi). `<n>` = numéro de groupe.

| Livrable | Nom exigé | Contenu | Échéance |
|---|---|---|---|
| Rapport d'ingénierie | `Workshop2026-M1-G<n>-Dossier.pdf` | Schéma réseau, schéma de câblage, matrice de sécurité (hardening, TLS), documentation IA, rapport d'audit post-pentest, **poster A3 en annexe** | Jeudi soir |
| Présentation | `Workshop2026-M1-G<n>-Pres.pptx` | Support de l'oral | Jeudi soir |
| Vidéo | `Workshop2026-M1-G<n>-VidDrop.mp4` | 60 s max, vertical 9:16, H.264 | Jeudi soir |
| Code | `Workshop2026-M1-G<n>-Code.zip` | Dépôt Git propre et structuré, README exhaustif, **aucun secret ni clé en clair** | Jeudi soir |
| Prototype | Boîtier SENTINEL-X fonctionnel | Électronique intégrée, prêt pour la démo live | **Vendredi matin**, au myDiL |

### Structure du teaser « Sentinel Drop » (60 s)

| Temps | Séquence |
|---|---|
| 00-10 s | **Hook métier** : la menace sur les centrales (ambiance d'alerte, sirène) |
| 10-30 s | **Produit physique** : gros plans du boîtier imprimé et gravé, OLED et capteurs |
| 30-50 s | **Stack en incrustation** (fond vert) : équipe au premier plan, derrière eux schémas animés, vrai code (firmware, Docker) ou interface de vision IA isolant un intrus |
| 50-60 s | **Outro** : équipe face caméra, « Sentinel-X : la sécurité à la bordure. » |

---

## 8. Évaluation

### 8.1 Locale (vendredi)

**Note finale = (Suivi individuel × 1 + Jury collectif × 2) / 3**

**Suivi individuel (/20, par les coachs lundi-jeudi)**, barème ND/1/2/3 :

| Critère | Points |
|---|---|
| Engagement, assiduité, posture | 4 |
| Expertise technique de la filière | 4 |
| Agilité et autonomie | 4 |
| Collaboration transversale | 4 |
| Rigueur d'ingénierie et Git (commits réguliers et sémantiques, câblage soigné) | 4 |

**Soutenance collective (/20, par le jury)** :

| Axe | Points | Ce que regarde le jury |
|---|---|---|
| 1. Démo live et intégration | 5 | Stabilité du flux complet ESP → serveur, réactivité du dashboard |
| 2. Technicité, innovation, sécurité | 4 | Preuve du chiffrement, niveau d'inférence IA, durcissement prouvé |
| 3. Marketing et teaser | 4 | Impact du clip, propreté de l'incrustation, finitions du boîtier |
| 4. Posture, storytelling, pitch | 4 | Clarté, dynamisme, respect strict du temps |
| 5. Qualité documentaire et Q&A | 3 | Rigueur du dossier, précision des réponses |

**Chrono de passage (10 min)** : 0-1 min présentation, 1-2 min teaser, 2-5 min démo live, 5-10 min pitch + Q&A (PowerPoint autorisé).

### 8.2 Nationale (17 novembre 2026, Teams)

Passage de **5 minutes maximum** (interruption immédiate au-delà) :
- 0-1 min : présentation et variante d'architecture
- 1-2 min : teaser
- 2-5 min : **démo live uniquement, pas de diaporama**

| Étape | Détail |
|---|---|
| Grille technique (/70) | Démo live 25 pts, vulgarisation et pitch 20 pts, complexité technique et innovation 15 pts, impact visuel du drop 10 pts |
| Scrutin croisé (43 pts par jury) | 2 jurys par campus (20 jurys). Le classement 1er à 10e donne 12, 10, 8, 6, 4, 2, 1, puis 0 point (8e, 9e, 10e) |
| Règle de neutralité | Un jury ne vote pas pour son propre campus. Ce campus fait partie des 3 groupes à 0 point, avec les deux moins bien notés de sa grille |

**Conséquence** : la démo live (25 pts sur 70) est le premier levier. Elle doit être **stable, scriptée et répétée**.

---

## 9. Risques et parades

| # | Risque | Impact | Parade |
|---|---|---|---|
| R1 | Contrat d'interface (topics, JSON, routes) pas figé lundi | Intégration impossible mercredi | Atelier de 1 h lundi, document partagé, versionné |
| R2 | Quorum Galera à 2 nœuds | Cluster bloqué à la perte d'un nœud | 3ᵉ nœud ou arbitre `garbd` |
| R3 | Webcam USB non accessible depuis une VM | IA inopérante | Faire tourner l'IA sur un laptop ou passthrough USB, validation coachs |
| R4 | Aucun profil Cyber, pentest jeudi | Failles exploitées, mauvaise note Axe 2 | TLS et hardening dès mardi, auto-audit Nmap mercredi |
| R5 | Dev 3 surchargé (dashboard + IA) | Retard sur l'IA ou le dashboard | Réaffecter l'IA ou la vidéo, prioriser les P1 |
| R6 | Panne réseau/Wi-Fi pendant la démo | Démo ratée | Reconnexion auto, mode démo de secours, répétition |
| R7 | Secret commité dans le dépôt | Pénalité sur le livrable code | `.gitignore`, `.env.example`, scan avant zip |
| R8 | Modèle IA sans données réelles | Détection d'anomalies peu crédible | Jeu de données simulé réaliste + scénario de démo scripté |
| R9 | Fablab (impression 3D) en retard | Boîtier non prêt vendredi | Lancer la CAO lundi, première impression mardi, gel jeudi matin |
| R10 | Charge du jeudi (pentest + rapport + livrables) | Livrables bâclés | Rédiger le dossier au fil de l'eau dès mardi |

---

## 10. Checklist de la démo finale

- [ ] ESP8266 alimenté, connecté au Wi-Fi, OLED affiche l'IP
- [ ] Mesures visibles en temps réel sur le dashboard
- [ ] Chauffer le DHT22 / approcher du gaz déclenche une alerte
- [ ] Anomalie prédictive détectée **avant** le seuil critique
- [ ] Personne devant la webcam : détection IA affichée
- [ ] Bouton dashboard : buzzer et LED réagissent
- [ ] Chiffrement démontrable (Wireshark : trafic illisible)
- [ ] Hardening démontrable (`ufw status`, SSH par clé uniquement)
- [ ] Reconstruction par Ansible possible à la demande
- [ ] Teaser prêt à être diffusé (MP4, 9:16, H.264)
- [ ] Prototype déposé au myDiL vendredi matin
- [ ] Démo répétée au chrono (5 min)

---

## 11. Questions ouvertes

1. Confirmer la répartition INFRA / DEV (Elios et Benoit en Infra, Felis, Martin, Matis en Dev ?).
2. Où tourne le script IA et où est branchée la webcam ?
3. Galera : 3 nœuds ou 2 + arbitre ?
4. « Connectivité Yanshee (Yang Chi) » : de quoi s'agit-il ?
5. Combien d'ESP8266 utilisons-nous (1 ou 2) ?
6. Quel numéro de groupe, pour le nommage des livrables ?
7. Quelles échéances horaires exactes fixées par les coachs (jeudi soir, vendredi matin) ?