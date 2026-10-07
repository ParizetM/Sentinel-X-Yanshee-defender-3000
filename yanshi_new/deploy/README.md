# Déploiement sur VM

Faire tourner `yanshi_video.py` (détection YOLO + flux annoté + MQTT) sur une VM
Debian/Ubuntu, et récupérer le flux vidéo annoté depuis une autre machine.

## Avant de commencer

- VM **sur le même réseau que le robot** (`10.0.3.x`) — sinon elle ne pourra pas
  lire le flux MJPG source.
- Carte réseau de la VM en **accès par pont / bridged** (pas NAT) : la VM doit
  avoir sa propre IP sur le réseau, joignable par le dashboard.
- Python ≥ 3.10 sur la VM (Ubuntu 22.04 = 3.10, 24.04 = 3.12).

## Installation

```bash
# 1. Depuis la machine de DEV (surtout pas depuis la VM),
#    se placer dans le dossier QUI CONTIENT yanshi_new
cd /chemin/vers/Sentinel-X-Yanshee-defender-3000
scp -r yanshi_new user@<ip-vm>:~/

# 2. Sur la VM
ssh user@<ip-vm>
cd ~/yanshi_new

# 3. Configurer
cp .env.example .env
chmod 600 .env          # contient la clé API, le mot de passe broker, etc.
nano .env               # voir la section suivante

# 4. Vérifier l'environnement, sans rien modifier
./deploy/install_vm.sh --check

# 5. Installer (venv + dépendances + service systemd)
./deploy/install_vm.sh
```

L'installateur crée un `.venv`, installe `requirements.txt`, bascule
automatiquement sur `opencv-python-headless` si `libGL` manque (cas normal sur
une VM sans écran), puis installe et démarre le service systemd.

> **La commande `scp` se lance depuis la machine de DEV**, jamais depuis la VM
> (sur la VM, `yanshi_new` n'existe pas encore — c'est justement ce qu'on copie).
>
> **Si `scp` refuse le chemin `~/`** : les versions récentes d'OpenSSH passent
> par SFTP, qui n'étend pas le `~`. Utiliser un chemin absolu
> (`root@<ip-vm>:/root/`) ou forcer l'ancien protocole (`scp -O`).
>
> **Ne pas installer en `root`** : le venv et le service appartiendraient à
> root. Créer un utilisateur dédié :
> ```bash
> adduser sentinel && usermod -aG sudo sentinel && su - sentinel
> ```
> Si tu restes en root malgré tout, `./deploy/install_vm.sh --allow-root`
> passe outre l'avertissement (déconseillé : le service tournerait en root).

## Configuration `.env` sur la VM

Reprendre le `.env` de la machine de dev, avec ces différences :

```ini
SENTINEL_API_KEY=sentinel-x-secret-key-2026   # clé du flux exposé
STREAM_HOST=0.0.0.0                           # écoute sur toutes les interfaces
STREAM_PORT=8080
SHOW_WINDOW=false                             # OBLIGATOIRE : la VM n'a pas d'écran
```

Sans `SHOW_WINDOW=false`, `cv2.imshow` échoue au premier passage dans la boucle.
Le drapeau `--check` le signale.

Le certificat `certs/ca.crt` doit être présent (il est résolu par rapport au
dossier du script, pas au dossier courant).

## Exploitation

```bash
journalctl -u sentinel-video -f          # suivre les logs
sudo systemctl restart sentinel-video    # redémarrer
sudo systemctl stop sentinel-video       # arrêter
systemctl status sentinel-video          # état
```

Le service redémarre automatiquement (`Restart=always`, délai 5 s) et démarre
avec la machine (`enable`).

## Ouvrir le pare-feu

Le flux est en HTTP et la clé y circule en clair : restreindre au réseau local
plutôt qu'ouvrir à tout le monde.

```bash
sudo ufw allow from 10.0.3.0/24 to any port 8080 proto tcp
```

## Récupérer le flux depuis une autre machine

| Usage | Adresse |
|---|---|
| Navigateur | `http://<ip-vm>:8080/?key=<SENTINEL_API_KEY>` |
| VLC | Média → Ouvrir un flux réseau → `http://<ip-vm>:8080/stream.mjpg?key=<clé>` |
| Dashboard web | `<img src="http://<ip-vm>:8080/stream.mjpg?key=<clé>">` (CORS géré) |
| curl | `curl -N -H "X-API-KEY: <clé>" http://<ip-vm>:8080/stream.mjpg -o /dev/null` |
| Python | `cv2.VideoCapture("http://<ip-vm>:8080/stream.mjpg?key=<clé>")` |

L'alias `/api/v1/camera/stream` sert le même flux (route prévue au README racine).
Préférer l'en-tête `X-API-KEY` : la clé passée dans l'URL finit dans l'historique
du navigateur, les journaux du proxy et la sortie de `ps`.

## Dépannage

| Symptôme | Cause probable |
|---|---|
| `Bad substitution` au lancement | script lancé avec `sh` → utiliser `./install_vm.sh` ou `bash install_vm.sh` (sous dash, `${BASH_SOURCE[0]}` n'existe pas) |
| `curl: not found` | le script n'utilise plus curl (test réseau via python3) — mettre à jour `install_vm.sh` |
| `pip install` échoue sur `torch` | Python trop récent pour les roues disponibles (ex. 3.13) — installer `python3.12` et recréer le venv avec |
| `libGL.so.1: cannot open shared object file` | `sudo apt install libgl1 libglib2.0-0`, ou `opencv-python-headless` (l'installateur le fait seul) |
| `cv2.error` au premier tour de boucle | `SHOW_WINDOW` n'est pas à `false` |
| `yolo26n.pt` introuvable, `captures/` vide | le service ne tourne pas depuis `yanshi_new/` — vérifier `WorkingDirectory` |
| Flux injoignable depuis une autre machine | pare-feu de la VM, ou carte réseau en NAT au lieu de bridged |
| `401` sur `/stream.mjpg` | clé absente ou fausse (le 401 est normal sans clé) |
| Le service redémarre en boucle | `journalctl -u sentinel-video -n 50` : souvent `.env` incomplet ou robot injoignable |

## État de vérification

- `install_vm.sh --check` a été exécuté avec succès sur un environnement réel
  (robot joignable, broker joignable, port libre).
- `--print-unit` a été vérifié : l'unité générée contient les chemins absolus
  corrects.
- Le chemin d'installation complet (création du venv, `pip install`, pose du
  service) **n'a pas pu être exécuté** depuis la machine de dev : il écrit dans
  `/etc/systemd/system` et suppose une VM. À valider au premier déploiement,
  d'où le `--check` à lancer avant.
