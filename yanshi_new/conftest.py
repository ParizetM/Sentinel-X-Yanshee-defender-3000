import os

# Garantit que l'import de yanshi_video fonctionne même sans .env
# (load_dotenv ne remplace pas les variables déjà présentes).
os.environ.setdefault("ROBOT_API_KEY", "test-key")
os.environ.setdefault("MQTT_BROKER_HOST", "127.0.0.1")
