# Sentinel-X — Contrôle Moteur Yanshee (Punch API Sécurisée)

Ce module fournit l'API HTTP protégée par **Clé API** pour déclencher à distance la séquence cinématique de la Sentinelle avec support d'un mode **Dry-Run (simulation sans mouvement physique)**.

---

## 1. Sécurité & Authentification (Cahier des charges Cybersécurité)

Conformément aux attendus de durcissement et de protection contre le pentest croisé :
* **Authentification obligatoire :** Toute requête non authentifiée est immédiatement rejetée avec un code `HTTP 401 Unauthorized`.
* **Modes d'authentification supportés :**
  1. **Header HTTP (Recommandé en production / Docker) :** `X-API-KEY: <cle_api>`
  2. **Query Parameter (Pratique pour les tests web) :** `?key=<cle_api>`
* **Clé API configurée :** `sentinel-x-secret-key-2026` (personnalisable via variable d'environnement `SENTINEL_API_KEY`).

---

## 2. Le Mode Dry-Run (`dry_run=1`)

Pour tester l'infrastructure, l'intégration Docker, les tests de charge ou valider les pipelines sans risquer d'endommager les servomoteurs ou de vider la batterie :
* **`dry_run=1` (ou `true`) :** Le serveur simule l'ensemble du cycle d'étapes (logs d'exécution, timings réalistes, réponses HTTP 200) **sans envoyer de commandes aux servomoteurs**.
* **`dry_run=0` (ou `false`) :** Déclenchement physique réel sur les 17 servos via ROS.

---

## 3. Déclenchement via API & URLs

### A. Simulation (Dry-Run = 1)
```bash
curl -H "X-API-KEY: sentinel-x-secret-key-2026" "http://10.0.3.234:5000/punch?dry_run=1"
```
*Réponse retournée :*
```json
{
  "status": "ok",
  "action": "victory_uppercut_punch_left_right",
  "mode": "simulated_dry_run",
  "dry_run": true
}
```

### B. Action Réelle Moteurs (Dry-Run = 0)
```bash
curl -H "X-API-KEY: sentinel-x-secret-key-2026" "http://10.0.3.234:5000/punch?dry_run=0"
```
*Réponse retournée :*
```json
{
  "status": "ok",
  "action": "victory_uppercut_punch_left_right",
  "mode": "real_hardware_execution",
  "dry_run": false
}
```

### C. Test dans le Navigateur Web
Ouvrez l'interface graphique :
👉 **`http://10.0.3.234:5000/?key=sentinel-x-secret-key-2026`**
Une case à cocher permet d'activer ou désactiver le mode Dry-Run à la volée avant de cliquer sur le bouton de frappe.

---

## 4. Intégration Python (Conteneur Docker IA)

```python
import requests

ROBOT_ACTION_URL = "http://10.0.3.234:5000/punch"
API_KEY = "sentinel-x-secret-key-2026"

def trigger_punch(dry_run=False):
    headers = {
        "X-API-KEY": API_KEY
    }
    params = {
        "dry_run": "1" if dry_run else "0"
    }
    
    try:
        response = requests.get(ROBOT_ACTION_URL, headers=headers, params=params, timeout=5)
        if response.status_code == 200:
            print("Action acceptée :", response.json())
        elif response.status_code == 401:
            print("Erreur : Clé API invalide !")
        elif response.status_code == 429:
            print("Robot occupé : séquence déjà en cours.")
    except Exception as e:
        print("Erreur de connexion :", e)
```
