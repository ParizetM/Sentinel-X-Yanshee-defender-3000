# Sentinel-X · Dashboard de supervision

Interface web (React 19, Vite, Recharts) du centre de commandement Sentinel-X. Elle affiche en temps réel les mesures du boîtier, les alertes, l'IA de vision et l'IA prédictive, et permet de déclencher les alarmes du boîtier à distance.

## Fonctionnalités

| Bloc | Contenu | Source |
|---|---|---|
| Capteurs | Courbes température, humidité, gaz, RSSI Wi-Fi ; présence PIR | `GET /api/v1/measurements` puis WebSocket `telemetry` |
| Alertes | Bandeau d'alerte et liste repliable (3 visibles par défaut) | `GET /api/v1/alerts` puis WebSocket `alert` |
| IA vision | Flux caméra, compteur de personnes, galerie des photos d'intrusion, actions du robot | `/api/v1/camera/*`, WebSocket `person_count`, `photo`, `robot_action` |
| IA prédictive | Jauge de risque (seuil à 1), capteur en cause, diagnostic | WebSocket `anomaly` |
| Panneau de contrôle | Buzzer (3 s), LED (3 s), alerte totale, arrêt d'urgence | `POST /api/v1/commands` |
| Statut | État du boîtier, du broker et de la base | `GET /api/v1/status` |

La connexion WebSocket se reconnecte automatiquement et envoie un `ping` régulier.

## Configuration

```bash
cp .env.example .env
```

| Variable | Rôle | Valeur vide |
|---|---|---|
| `VITE_API_URL` | URL de l'API | même origine (derrière le reverse proxy) |
| `VITE_WS_URL` | URL du WebSocket | `wss://<hôte>/ws` si la page est en HTTPS, `ws://` sinon |
| `VITE_CAMERA_URL` | Flux caméra MJPEG | `/api/v1/camera/stream` |

En production, laisser les variables vides : le dashboard et l'API sont servis sous la même origine HTTPS par le reverse proxy.

## Commandes

```bash
npm ci            # installation
npm run dev       # développement (http://localhost:5173)
npm run build     # production → dist/
npm run lint      # oxlint
```

## Structure

```
src/
├── App.jsx                     état global, chargement initial, WebSocket
└── components/
    ├── ControlPanel.jsx        commandes buzzer / LED
    ├── layout/                 en-tête, bandeau d'alerte
    ├── sensors/                cartes et courbes capteurs
    ├── alerts/                 liste des alertes
    └── ia/                     flux YOLO, compteur, photos, jauge de risque, actions robot
```
