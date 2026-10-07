"""Application principale FastAPI pour Sentinel-X (EPIC 5)."""

import asyncio
import logging
from contextlib import asynccontextmanager
from fastapi import FastAPI, Request, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import RedirectResponse, JSONResponse
from fastapi.exceptions import RequestValidationError

from app.config import settings
from app.database import init_db, engine
from app.mqtt_client import mqtt_manager
from app.routers import alerts_router, telemetry_router, actuators_router, status_router

# Configuration des logs
logging.basicConfig(
    level=logging.INFO if not settings.API_DEBUG else logging.DEBUG,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s"
)
logger = logging.getLogger("sentinel.api")


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Cycle de vie de l'application : initialisation BDD et démarrage MQTT."""
    logger.info("Démarrage de l'API Sentinel-X...")
    # Initialisation des tables SQL
    try:
        await init_db()
        logger.info("Base de données initialisée avec succès.")
    except Exception as e:
        logger.error(f"Erreur d'initialisation de la base de données : {e}")

    # Démarrage du client MQTT d'ingestion en arrière-plan
    loop = asyncio.get_running_loop()
    mqtt_manager.setup(loop)
    mqtt_manager.start()

    yield

    # Arrêt propre
    logger.info("Arrêt de l'API Sentinel-X...")
    mqtt_manager.stop()
    await engine.dispose()


app = FastAPI(
    title="SENTINEL-X REST API",
    description="""
API REST & Moteur d'Ingestion pour le système de surveillance cyber-physique SENTINEL-X (Workshop 2026 BAC+4).

### Fonctionnalités principales :
* **Ingestion Télémétrie MQTT :** Consommation temps réel des flux capteurs ESP8266 (DHT22, Gaz MQ-2, Détection PIR).
* **Point d'entrée obligatoire POST /api/v1/alerts :** Réception et validation stricte des alertes d'intrusion et de danger.
* **Supervision & Historique :** Consultation des séries temporelles pour affichage des courbes du Dashboard.
* **Contrôle Réactif :** Déclenchement à distance des actionneurs de table (Buzzer, LED) et des actions physiques du Robot Yanshee.
* **Durcissement Cybersécurité :** Authentification par token Bearer / API Key et résilience anti-pentest.
    """,
    version="1.0.0",
    lifespan=lifespan,
    docs_url="/docs",
    redoc_url="/redoc"
)

# Configuration CORS pour permettre la communication avec le Dashboard React/Vue
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Peut être restreint à des domaines spécifiques en production
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request: Request, exc: RequestValidationError):
    """Formatage propre et strict des erreurs de validation JSON (422)."""
    return JSONResponse(
        status_code=status.HTTP_422_UNPROCESSABLE_CONTENT if hasattr(status, "HTTP_422_UNPROCESSABLE_CONTENT") else 422,
        content={
            "error": "Validation Error",
            "message": "Le schéma JSON fourni n'est pas conforme aux spécifications requises.",
            "details": exc.errors()
        }
    )


# Inclusion des sous-routeurs
app.include_router(alerts_router)
app.include_router(telemetry_router)
app.include_router(actuators_router)
app.include_router(status_router)


@app.get("/", include_in_schema=False)
async def root_redirect():
    """Redirection conviviale vers la documentation interactive Swagger."""
    return RedirectResponse(url="/docs")
