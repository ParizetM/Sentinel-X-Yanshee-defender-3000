# coding=utf-8
import os
import sys
import time
import urlparse
import threading
import BaseHTTPServer
import SocketServer
import rospy
import ubt_msgs.srv

# Clé API par défaut (peut être surchargée via la variable d'environnement SENTINEL_API_KEY)
DEFAULT_API_KEY = os.environ.get("SENTINEL_API_KEY", "sentinel-x-secret-key-2026")

is_busy = False
action_lock = threading.Lock()

def do_sentinel_combo(dry_run=False):
    global is_busy
    with action_lock:
        if is_busy:
            return
        is_busy = True

    try:
        if dry_run:
            print("[SENTINEL][DRY-RUN] Simulation combo : Aucun mouvement physique déclenché.")
            print("[SENTINEL][DRY-RUN] 1/3 Simulation Coucou (Victory)...")
            time.sleep(1.0)
            print("[SENTINEL][DRY-RUN] 2/3 Simulation Punch Gauche...")
            time.sleep(1.0)
            print("[SENTINEL][DRY-RUN] 3/3 Simulation Punch Droit...")
            time.sleep(1.0)
            print("[SENTINEL][DRY-RUN] Simulation terminée avec succès.")
            return

        # Exécution réelle sur les servomoteurs via ROS
        rospy.wait_for_service('/play_motion_hts', timeout=5)
        play = rospy.ServiceProxy('/play_motion_hts', ubt_msgs.srv.play_motion_hts)
        
        # 1. Geste Coucou (Victory : lève les 2 bras)
        print("[SENTINEL] 1/3 Geste Coucou des 2 bras (Victory)...")
        r0 = play("Victory", 1)
        wait_victory = (r0.total_time / 1000.0) if hasattr(r0, 'total_time') and r0.total_time > 0 else 4.7
        time.sleep(wait_victory + 0.3)

        # 2. Coup de poing GAUCHE (LeftHitForward)
        print("[SENTINEL] 2/3 Coup de poing GAUCHE (LeftHitForward)...")
        r1 = play("LeftHitForward", 1)
        wait_left = (r1.total_time / 1000.0) if hasattr(r1, 'total_time') and r1.total_time > 0 else 2.6
        time.sleep(wait_left + 0.3)

        # 3. Coup de poing DROIT (RightHitForward)
        print("[SENTINEL] 3/3 Coup de poing DROIT (RightHitForward)...")
        r2 = play("RightHitForward", 1)
        wait_right = (r2.total_time / 1000.0) if hasattr(r2, 'total_time') and r2.total_time > 0 else 2.6
        time.sleep(wait_right)

        print("[SENTINEL] COMBO COUCOU + PUNCH GAUCHE + PUNCH DROIT TERMINE !")
    except Exception as e:
        print("[SENTINEL] Erreur execution combo:", e)
    finally:
        with action_lock:
            is_busy = False

HTML_PAGE = """<!DOCTYPE html>
<html>
<head>
    <meta charset="utf-8">
    <title>Sentinel-X // Action Controller</title>
    <style>
        body { background: #0c0d14; color: #fff; font-family: monospace; text-align: center; padding-top: 40px; }
        .card { background: #161925; border: 1px solid #23283c; border-radius: 16px; padding: 35px; display: inline-block; box-shadow: 0 10px 40px rgba(0,0,0,0.6); max-width: 580px; width: 90%; }
        h1 { color: #00f3ff; margin-bottom: 8px; font-size: 22px; }
        .badge { display: inline-block; background: rgba(0,243,255,0.1); color: #00f3ff; border: 1px solid #00f3ff; padding: 4px 10px; border-radius: 20px; font-size: 11px; margin-bottom: 20px; }
        .steps { color: #8892b0; margin-bottom: 25px; font-size: 13px; line-height: 1.6; }
        .steps span { color: #ff0055; font-weight: bold; }
        .input-group { margin-bottom: 20px; text-align: left; }
        label { display: block; font-size: 12px; color: #94a3b8; margin-bottom: 5px; }
        input[type="text"] { width: 95%; background: #090a0f; border: 1px solid #334155; color: #38bdf8; padding: 10px; border-radius: 8px; font-family: monospace; font-size: 14px; }
        .checkbox-container { display: flex; align-items: center; justify-content: center; gap: 10px; margin-bottom: 25px; font-size: 14px; color: #f59e0b; }
        .checkbox-container input { width: 18px; height: 18px; cursor: pointer; }
        .btn-group { display: flex; gap: 10px; justify-content: center; }
        .btn { background: linear-gradient(135deg, #ff0055, #ff5500); color: white; border: none; padding: 16px 28px; font-size: 16px; font-weight: 700; border-radius: 10px; cursor: pointer; box-shadow: 0 0 20px rgba(255, 0, 85, 0.4); transition: 0.2s all; }
        .btn:hover { transform: translateY(-2px); box-shadow: 0 0 30px rgba(255, 0, 85, 0.7); }
        #res { margin-top: 25px; padding: 15px; border-radius: 8px; font-size: 13px; background: #090a0f; color: #00f3ff; min-height: 24px; text-align: left; }
        .url-box { margin-top: 25px; font-size: 12px; color: #64748b; text-align: left; background: #0f121d; padding: 15px; border-radius: 8px; border: 1px dashed #334155; }
        code { background: #20263c; color: #38bdf8; padding: 2px 6px; border-radius: 4px; }
    </style>
</head>
<body>
    <div class="card">
        <h1>SENTINEL-X ACTION CONTROLLER</h1>
        <div class="badge">SECURED BY API KEY</div>
        <div class="steps">
            Séquence : <span>1. Coucou (Victory)</span> ➜ <span>2. Punch Gauche</span> ➜ <span>3. Punch Droit</span>
        </div>

        <div class="input-group">
            <label for="apiKey">Clé d'authentification API (Header X-API-KEY ou ?key=) :</label>
            <input type="text" id="apiKey" value="sentinel-x-secret-key-2026">
        </div>

        <div class="checkbox-container">
            <input type="checkbox" id="dryRun">
            <label for="dryRun">Mode Dry-Run (simulation sans bouger les moteurs)</label>
        </div>

        <div class="btn-group">
            <button class="btn" onclick="triggerPunch()">DÉCLENCHER LE COMBO</button>
        </div>

        <div id="res">En attente d'action...</div>

        <div class="url-box">
            <b>Exemples d'appels sécurisés :</b><br>
            • Action Réelle :<br>
            <code>GET /punch?key=sentinel-x-secret-key-2026&dry_run=0</code><br><br>
            • Simulation (Dry-Run = 1) :<br>
            <code>GET /punch?key=sentinel-x-secret-key-2026&dry_run=1</code><br><br>
            • Via Header HTTP :<br>
            <code>curl -H "X-API-KEY: sentinel-x-secret-key-2026" "http://10.0.3.234:5000/punch?dry_run=0"</code>
        </div>
    </div>

    <script>
        function triggerPunch() {
            var box = document.getElementById('res');
            var key = document.getElementById('apiKey').value.trim();
            var dry = document.getElementById('dryRun').checked ? '1' : '0';

            box.innerText = '⚡ Envoi de la commande sécurisée (Dry-run: ' + dry + ')...';
            
            fetch('/punch?dry_run=' + dry + '&key=' + encodeURIComponent(key), {
                headers: { 'X-API-KEY': key }
            })
            .then(function(r) {
                return r.json().then(function(data) {
                    return { status: r.status, data: data };
                });
            })
            .then(function(res) {
                if (res.status === 200) {
                    box.innerText = '✅ Succès [HTTP ' + res.status + '] : ' + JSON.stringify(res.data, null, 2);
                } else if (res.status === 401) {
                    box.innerText = '⛔ ACCÈS REFUSÉ [HTTP 401] : Clé API invalide ou manquante !';
                } else {
                    box.innerText = '⚠️ Code ' + res.status + ' : ' + JSON.stringify(res.data);
                }
            })
            .catch(function(e) {
                box.innerText = '❌ Erreur réseau: ' + e;
            });
        }
    </script>
</body>
</html>"""

class PunchHandler(BaseHTTPServer.BaseHTTPRequestHandler):
    def _send_cors(self):
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type, X-API-KEY")

    def do_OPTIONS(self):
        self.send_response(200)
        self._send_cors()
        self.end_headers()

    def _is_authenticated(self, query_params):
        header_key = self.headers.getheader("X-API-KEY")
        if header_key and header_key.strip() == DEFAULT_API_KEY:
            return True
        if "key" in query_params:
            if query_params["key"][0] == DEFAULT_API_KEY:
                return True
        return False

    def do_GET(self):
        global is_busy

        parsed_url = urlparse.urlparse(self.path)
        path = parsed_url.path
        query = urlparse.parse_qs(parsed_url.query)

        if path in ("/punch", "/punch/", "/action", "/action/"):
            if not self._is_authenticated(query):
                self.send_response(401)
                self._send_cors()
                self.send_header("Content-Type", "application/json")
                body = '{"status": "unauthorized", "error": "Invalid or missing API Key"}'
                self.send_header("Content-Length", str(len(body)))
                self.end_headers()
                self.wfile.write(body)
                print("[SENTINEL][SECURITY] Tentative non autorisee bloquee sur /punch !")
                return

            dry_param = query.get("dry_run", query.get("dry-run", ["0"]))[0]
            is_dry_run = dry_param in ("1", "true", "True", "yes")

            if is_busy:
                self.send_response(429)
                self._send_cors()
                self.send_header("Content-Type", "application/json")
                body = '{"status": "busy", "message": "Action sequence already in progress"}'
                self.send_header("Content-Length", str(len(body)))
                self.end_headers()
                self.wfile.write(body)
                return

            t = threading.Thread(target=do_sentinel_combo, args=(is_dry_run,))
            t.daemon = True
            t.start()

            mode_str = "simulated_dry_run" if is_dry_run else "real_hardware_execution"
            body = '{"status": "ok", "action": "victory_punch_left_right", "mode": "%s", "dry_run": %s}' % (mode_str, "true" if is_dry_run else "false")
            self.send_response(200)
            self._send_cors()
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        elif path == "/":
            self.send_response(200)
            self._send_cors()
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Content-Length", str(len(HTML_PAGE)))
            self.end_headers()
            self.wfile.write(HTML_PAGE)
        else:
            self.send_error(404)
            self.end_headers()

class ThreadedHTTPServer(SocketServer.ThreadingMixIn, BaseHTTPServer.HTTPServer):
    allow_reuse_address = True
    daemon_threads = True

if __name__ == "__main__":
    rospy.init_node("punch_api_service", anonymous=True, disable_signals=True)
    server = ThreadedHTTPServer(("0.0.0.0", 5000), PunchHandler)
    print("Secured Punch HTTP API running on port 5000 (API Key protection enabled)...")
    server.serve_forever()
