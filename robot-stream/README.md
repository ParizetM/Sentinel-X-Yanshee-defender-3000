# Sentinel-X — Streaming Vidéo Sécurisé (Fast Camera API)

Ce module capture la caméra frontale du robot Yanshee avec **accélération matérielle GPU** et diffuse le flux en direct protégé par **Clé API**.

---

## 1. Sécurité du Flux

Pour empêcher les écoutes illégitimes et les captures d'images par des attaquants lors du pentest :
* **Accès conditionné par Clé API :** Toute tentative d'accès sans clé est bloquée avec `HTTP 401 Unauthorized`.
* **Modes d'authentification :**
  * Par URL : `http://10.0.3.234:8000/stream.mjpg?key=sentinel-x-secret-key-2026`
  * Par Header HTTP : `X-API-KEY: sentinel-x-secret-key-2026`

---

## 2. Consommer le Flux Sécurisé dans Docker / OpenCV

```python
import cv2

STREAM_URL = "http://10.0.3.234:8000/stream.mjpg?key=sentinel-x-secret-key-2026"

cap = cv2.VideoCapture(STREAM_URL)

while True:
    ret, frame = cap.read()
    if not ret:
        continue

    # Détection IA YOLO / OpenCV ici...
    cv2.imshow("Secure Sentinel Stream", frame)
    if cv2.waitKey(1) == 27:
        break

cap.release()
cv2.destroyAllWindows()
```
