#!/usr/bin/env bash
#
# Installation de yanshi_new sur une VM Debian/Ubuntu.
#
#   ./deploy/install_vm.sh --check        vérifie l'environnement, ne modifie rien
#   ./deploy/install_vm.sh --print-unit   affiche l'unité systemd sans l'installer
#   ./deploy/install_vm.sh                installe venv + dépendances + service
#
# À lancer avec l'utilisateur qui fera tourner le service, PAS en root :
# le venv et le service appartiendraient à root. Le script n'élève les
# privilèges que pour installer l'unité systemd.

# Doit venir avant tout : sous dash (« sh install_vm.sh »), les tableaux et
# « set -o pipefail » ne sont pas supportés et le script échouerait sur un
# obscur « Bad substitution ».
if [ -z "${BASH_VERSION:-}" ]; then
    echo "[ERREUR] Ce script doit être lancé avec bash, pas avec sh." >&2
    echo "         ./install_vm.sh        ou        bash install_vm.sh" >&2
    exit 2
fi

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"          # yanshi_new/
ENV_FILE="$PROJECT_DIR/.env"
VENV_DIR="$PROJECT_DIR/.venv"
SERVICE_NAME="sentinel-video"
SERVICE_FILE="/etc/systemd/system/${SERVICE_NAME}.service"

MODE="install"
ALLOW_ROOT=0

for arg in "$@"; do
    case "$arg" in
        --check)      MODE="check" ;;
        --print-unit) MODE="print-unit" ;;
        --allow-root) ALLOW_ROOT=1 ;;
        -h|--help)    sed -n '2,11p' "$0" | sed 's/^# \{0,1\}//'; exit 0 ;;
        *) echo "[ERREUR] Option inconnue : $arg" >&2; exit 2 ;;
    esac
done

info() { echo "[INFO]   $*"; }
ok()   { echo "[OK]     $*"; }
warn() { echo "[ATTENTION] $*"; }
fail() { echo "[ECHEC]  $*" >&2; }

# ============================================================
# Lecture du .env
# ============================================================

# Lecture par sed plutôt que par `source` : un .env est un fichier de
# configuration, pas un script — le sourcer exécuterait son contenu.
read_env() {
    local raw
    raw=$(sed -n "s/^[[:space:]]*$1[[:space:]]*=[[:space:]]*//p" "$ENV_FILE" \
          | tail -1 | tr -d '\r')
    raw="${raw%\"}"
    raw="${raw#\"}"
    printf '%s' "$raw"
}

# ============================================================
# Vérifications
# ============================================================

CHECKS_FAILED=0

check_python() {
    if ! command -v python3 >/dev/null 2>&1; then
        fail "python3 absent"
        CHECKS_FAILED=1
        return
    fi

    local version
    version=$(python3 -c 'import sys; print("%d.%d" % sys.version_info[:2])')

    if python3 -c 'import sys; sys.exit(0 if sys.version_info >= (3, 10) else 1)'; then
        ok "python3 $version (>= 3.10 requis)"
    else
        fail "python3 $version trop ancien (>= 3.10 requis : le code utilise « int | None »)"
        CHECKS_FAILED=1
    fi
}

check_env_file() {
    if [ ! -f "$ENV_FILE" ]; then
        fail ".env absent — copier .env.example vers .env et renseigner les valeurs"
        CHECKS_FAILED=1
        return
    fi

    ok ".env présent"

    local mode
    mode=$(stat -c '%a' "$ENV_FILE")

    if [ "$mode" != "600" ]; then
        warn ".env lisible par d'autres (mode $mode) — conseillé : chmod 600 .env"
    fi

    local missing=""

    for key in ROBOT_API_KEY MQTT_BROKER_HOST SENTINEL_API_KEY; do
        if [ -z "$(read_env "$key")" ]; then
            missing="$missing $key"
        fi
    done

    if [ -n "$missing" ]; then
        fail "variables manquantes dans .env :$missing"
        CHECKS_FAILED=1
    else
        ok "ROBOT_API_KEY, MQTT_BROKER_HOST et SENTINEL_API_KEY renseignés"
    fi
}

check_display() {
    local show
    show=$(read_env SHOW_WINDOW)

    if [ "$show" = "true" ] || [ -z "$show" ]; then
        warn "SHOW_WINDOW vaut « ${show:-true} » : sur une VM sans écran, mettre"
        warn "  SHOW_WINDOW = false dans .env, sinon cv2.imshow échoue"
    else
        ok "SHOW_WINDOW = false (exécution sans écran)"
    fi
}

check_tls_cert() {
    local ca
    ca=$(read_env MQTT_CA_CERT)
    ca="${ca:-certs/ca.crt}"

    case "$ca" in
        /*) ;;
        *) ca="$PROJECT_DIR/$ca" ;;
    esac

    if [ -f "$ca" ]; then
        ok "certificat CA présent ($ca)"
    else
        warn "certificat CA introuvable ($ca) — la connexion MQTT en TLS échouera"
    fi
}

check_robot() {
    local key url code
    key=$(read_env ROBOT_API_KEY)

    if [ -z "$key" ]; then
        return
    fi

    # python3 plutôt que curl : curl n'est pas installé sur toutes les VM,
    # alors que python3 est de toute façon requis par le projet. On ne lit
    # que l'en-tête de réponse, le flux MJPEG étant infini.
    local code
    code=$(python3 - "$key" <<'PY' 2>/dev/null || true
import sys
import urllib.error
import urllib.request

url = f"http://10.0.3.234:8000/stream.mjpg?key={sys.argv[1]}"

try:
    response = urllib.request.urlopen(url, timeout=4)
    print(response.status)
    response.close()
except urllib.error.HTTPError as e:
    print(e.code)
except Exception:
    print("")
PY
)

    if [ "$code" = "200" ]; then
        ok "flux MJPG du robot joignable (10.0.3.234:8000)"
    else
        # Avertissement et non échec : le robot peut être éteint pendant
        # l'installation, et le script se reconnecte au démarrage.
        warn "flux MJPG du robot injoignable (réponse : « ${code:-aucune} »)"
        warn "  vérifier le réseau de la VM (mode pont/bridged) et que le robot tourne"
    fi
}

check_broker() {
    local host port
    host=$(read_env MQTT_BROKER_HOST)
    port=$(read_env MQTT_BROKER_PORT)
    port="${port:-1883}"

    if [ -z "$host" ]; then
        return
    fi

    if timeout 4 bash -c "cat < /dev/null > /dev/tcp/$host/$port" 2>/dev/null; then
        ok "broker MQTT joignable ($host:$port)"
    else
        # Avertissement : le client MQTT retente en arrière-plan.
        warn "broker MQTT injoignable ($host:$port) — reconnexion automatique"
    fi
}

check_stream_port() {
    local port
    port=$(read_env STREAM_PORT)
    port="${port:-8080}"

    if timeout 2 bash -c "cat < /dev/null > /dev/tcp/127.0.0.1/$port" 2>/dev/null; then
        warn "le port $port est déjà utilisé — le service ne pourra pas démarrer"
    else
        ok "port $port libre pour le flux exposé"
    fi
}

check_imports() {
    if [ ! -x "$VENV_DIR/bin/python" ]; then
        info "environnement virtuel pas encore créé — l'installation s'en charge"
        return
    fi

    if "$VENV_DIR/bin/python" -c 'import cv2, ultralytics, paho.mqtt, dotenv' 2>/dev/null; then
        ok "dépendances Python importables (cv2, ultralytics, paho, dotenv)"
    else
        # Avertissement et jamais échec : des dépendances cassées sont
        # exactement ce que l'installation répare. Bloquer ici empêcherait
        # de lancer la réparation (blocage en boucle).
        warn "dépendances Python non importables — l'installation va les réinstaller"
        warn "  cause :"
        # « || true » obligatoire : sous « set -e », cette commande de
        # diagnostic échoue par définition (c'est ce qu'elle constate) et
        # ferait avorter le script.
        "$VENV_DIR/bin/python" -c 'import cv2' 2>&1 | tail -3 \
            | sed 's/^/           /' || true
        warn "  si l'échec persiste après installation :"
        warn "  sudo apt install libgl1 libglib2.0-0   (ou opencv-python-headless)"
    fi
}

run_checks() {
    echo "=== Vérification de l'environnement ==="
    echo "    [ATTENTION] n'empêche pas l'installation — [ECHEC] si."
    check_python
    check_env_file
    check_display
    check_tls_cert
    check_robot
    check_broker
    check_stream_port
    check_imports
    echo
}

# ============================================================
# Unité systemd
# ============================================================

# Le service tourne depuis le dossier du projet : yolo26n.pt et captures/
# sont des chemins relatifs au dossier courant.
generate_unit() {
    cat <<EOF
[Unit]
Description=Sentinel-X - flux YOLO Yanshee
After=network-online.target
Wants=network-online.target

[Service]
User=$(id -un)
WorkingDirectory=$PROJECT_DIR
Environment=PYTHONUNBUFFERED=1
ExecStart=$VENV_DIR/bin/python $PROJECT_DIR/yanshi_video.py
Restart=always
RestartSec=5

[Install]
WantedBy=multi-user.target
EOF
}

# ============================================================
# Installation
# ============================================================

install_dependencies() {
    # Un .venv créé lors d'un essai en root appartient à root : pip
    # échouerait ensuite sur « permission denied », avec une erreur brute
    # difficile à relier à sa cause.
    if [ -e "$VENV_DIR" ] && [ ! -w "$VENV_DIR" ]; then
        fail "$VENV_DIR existe mais ne t'appartient pas (créé en root ?)"
        fail "  le supprimer puis relancer :"
        fail "    sudo rm -rf $VENV_DIR"
        exit 1
    fi

    info "Création de l'environnement virtuel..."
    python3 -m venv "$VENV_DIR"

    info "Installation des dépendances (peut prendre plusieurs minutes)..."
    "$VENV_DIR/bin/pip" install --quiet --upgrade pip
    "$VENV_DIR/bin/pip" install --quiet -r "$PROJECT_DIR/requirements.txt"

    # Une VM sans écran n'a pas libGL : opencv-python refuse alors de
    # s'importer. Le code ne touche jamais à l'interface graphique quand
    # SHOW_WINDOW=false, la variante headless convient donc parfaitement.
    if ! "$VENV_DIR/bin/python" -c 'import cv2' 2>/dev/null; then
        warn "import de cv2 impossible (libGL manquant ?)"
        info "Bascule vers opencv-python-headless (aucune GUI nécessaire)"
        "$VENV_DIR/bin/pip" uninstall -y --quiet opencv-python || true
        "$VENV_DIR/bin/pip" install --quiet opencv-python-headless
    fi

    if "$VENV_DIR/bin/python" -c 'import cv2, ultralytics, paho.mqtt, dotenv'; then
        ok "dépendances installées"
    else
        fail "dépendances toujours non importables"
        exit 1
    fi
}

install_service() {
    info "Installation du service systemd (mot de passe sudo demandé)..."

    generate_unit | sudo tee "$SERVICE_FILE" >/dev/null
    sudo systemctl daemon-reload
    sudo systemctl enable --now "$SERVICE_NAME"

    sleep 2

    if systemctl is-active --quiet "$SERVICE_NAME"; then
        ok "service $SERVICE_NAME démarré"
    else
        fail "le service n'a pas démarré — voir : journalctl -u $SERVICE_NAME -n 50"
        exit 1
    fi
}

# ============================================================
# Programme principal
# ============================================================

if [ "$MODE" = "print-unit" ]; then
    generate_unit
    exit 0
fi

if [ "$MODE" = "check" ]; then
    run_checks
    if [ "$CHECKS_FAILED" -eq 0 ]; then
        ok "configuration valide — relire les [ATTENTION] ci-dessus"
    else
        fail "configuration incomplète : corriger les [ECHEC] ci-dessus"
    fi
    exit "$CHECKS_FAILED"
fi

if [ "$(id -u)" -eq 0 ] && [ "$ALLOW_ROOT" -ne 1 ]; then
    fail "ne pas lancer ce script en root : le venv et le service"
    fail "appartiendraient à root. Relancer avec ton utilisateur normal,"
    fail "ou forcer avec --allow-root (déconseillé)."
    exit 2
fi

if [ "$(id -u)" -eq 0 ]; then
    warn "installation en root : le service tournera en root (déconseillé)"
fi

echo "=== Installation de yanshi_new ==="
run_checks

if [ "$CHECKS_FAILED" -ne 0 ]; then
    fail "environnement incomplet : installation interrompue"
    exit 1
fi

install_dependencies
install_service

STREAM_PORT_VALUE=$(read_env STREAM_PORT)
STREAM_PORT_VALUE="${STREAM_PORT_VALUE:-8080}"

echo
ok "Installation terminée"
echo
echo "Utilisation :"
echo "  journalctl -u $SERVICE_NAME -f          # suivre les logs"
echo "  sudo systemctl restart $SERVICE_NAME    # redémarrer"
echo "  sudo systemctl stop $SERVICE_NAME       # arrêter"
echo
echo "Pare-feu (à ouvrir une fois, restreint au réseau local) :"
echo "  sudo ufw allow from 10.0.3.0/24 to any port $STREAM_PORT_VALUE proto tcp"
echo
echo "Flux annoté : http://$(hostname -I | awk '{print $1}'):$STREAM_PORT_VALUE/?key=<SENTINEL_API_KEY>"
