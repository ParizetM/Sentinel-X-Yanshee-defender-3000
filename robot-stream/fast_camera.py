# coding=utf-8
import os
import io
import time
import picamera
from threading import Condition
import BaseHTTPServer
import SocketServer
import urlparse

DEFAULT_API_KEY = os.environ.get("SENTINEL_API_KEY", "sentinel-x-secret-key-2026")

class StreamingOutput(object):
    def __init__(self):
        self.frame = None
        self.buffer = io.BytesIO()
        self.condition = Condition()

    def write(self, buf):
        if buf.startswith(b"\xff\xd8"):
            self.buffer.truncate()
            with self.condition:
                self.frame = self.buffer.getvalue()
                self.condition.notify_all()
            self.buffer.seek(0)
        return self.buffer.write(buf)

output = StreamingOutput()

class StreamingHandler(BaseHTTPServer.BaseHTTPRequestHandler):
    def _send_cors(self):
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "X-API-KEY, Content-Type")

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
        parsed_url = urlparse.urlparse(self.path)
        path = parsed_url.path
        query = urlparse.parse_qs(parsed_url.query)

        # Verification d authentification
        if not self._is_authenticated(query):
            self.send_response(401)
            self._send_cors()
            self.send_header("Content-Type", "application/json")
            body = '{"status": "unauthorized", "error": "Invalid or missing API Key for camera feed"}'
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)
            return

        if path in ("/", "/index.html"):
            api_k = query.get("key", ["sentinel-x-secret-key-2026"])[0]
            content = ("""<!DOCTYPE html>
<html>
<head><title>SENTINEL-X SECURE FEED</title></head>
<body style="background:#111;text-align:center;color:#00f3ff;font-family:monospace;padding-top:30px;">
    <h2>SENTINEL-X // SECURE CAMERA FEED</h2>
    <div style="margin-bottom:15px;color:#94a3b8;font-size:13px;">[SECURED BY API KEY]</div>
    <img src="/stream.mjpg?key=""" + str(api_k) + """" style="border:2px solid #00f3ff;border-radius:8px;max-width:90%;" />
</body></html>""")
            self.send_response(200)
            self._send_cors()
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Content-Length", str(len(content)))
            self.end_headers()
            self.wfile.write(content)
        elif path == "/stream.mjpg":
            self.send_response(200)
            self._send_cors()
            self.send_header("Age", "0")
            self.send_header("Cache-Control", "no-cache, no-store, must-revalidate")
            self.send_header("Pragma", "no-cache")
            self.send_header("Content-Type", "multipart/x-mixed-replace; boundary=FRAME")
            self.end_headers()
            try:
                while True:
                    with output.condition:
                        output.condition.wait()
                        frame = output.frame
                    self.wfile.write(b"--FRAME\r\n")
                    self.send_header("Content-Type", "image/jpeg")
                    self.send_header("Content-Length", str(len(frame)))
                    self.end_headers()
                    self.wfile.write(frame)
                    self.wfile.write(b"\r\n")
            except Exception:
                pass
        else:
            self.send_error(404)
            self.end_headers()

class StreamingServer(SocketServer.ThreadingMixIn, BaseHTTPServer.HTTPServer):
    allow_reuse_address = True
    daemon_threads = True

if __name__ == "__main__":
    with picamera.PiCamera(resolution="640x480", framerate=25) as camera:
        camera.video_stabilization = False
        camera.exposure_mode = "auto"
        camera.awb_mode = "auto"
        camera.start_recording(output, format="mjpeg", quality=60)
        print("Secured PiCamera stream running on port 8000 (API Key protection enabled)...")
        try:
            address = ("", 8000)
            server = StreamingServer(address, StreamingHandler)
            server.serve_forever()
        finally:
            camera.stop_recording()
