# main.py
import uvicorn
import logging
import os
import threading
from fastapi import FastAPI
from contextlib import asynccontextmanager

from database.session import engine, Base
import database.models

from api.routes_publish import router as publish_router
from api.routes_oauth import router as oauth_router
from services.scheduler import start_scheduler, stop_scheduler

# Import the new Listener components
from database.listener import DBListener

# Configure global logging
logging.basicConfig(
    level=logging.INFO,
    format='[%(asctime)s] [%(levelname)s] [%(name)s] - %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)

logger = logging.getLogger("EVO-Main")


def run_db_listener():
    """
    Background worker that executes the DB Listener loop.
    """
    try:
        # 🚨 FIX: render_as_string ensures the password is NOT masked
        db_url = engine.url.render_as_string(hide_password=False)

        # Also, psycopg2 needs 'postgresql://', not 'postgresql+psycopg2://'
        if "+psycopg2" in db_url:
            db_url = db_url.replace("+psycopg2", "")

        listener = DBListener(db_url)
        listener.start_listening()
    except Exception as e:
        logger.error(f"[Listener-Thread] Critical failure in background listener: {e}")

@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("===================================================")
    logger.info("🚀 EVO OMNI PUBLISHER ENGINE - Starting Up...")
    logger.info("===================================================")

    # 1. Database Initialization
    try:
        Base.metadata.create_all(bind=engine)
        logger.info("[Database] PostgreSQL tables verified successfully.")
    except Exception as e:
        logger.error(f"[Database Error] Check your connection: {e}")

    # 2. OAuth Configuration Verification
    secrets_path = os.path.join("credentials", "client_secret_251021151101.json")
    if os.path.exists(secrets_path):
        logger.info(f"[OAuth] Secrets file detected at: {secrets_path}")
    else:
        logger.warning(f"[OAuth] Secrets file NOT FOUND at: {secrets_path}")

    # 3. Start the Event-Driven Listener in a background thread
    try:
        listener_thread = threading.Thread(target=run_db_listener, daemon=True)
        listener_thread.start()
        logger.info("[Events] Event-Driven Listener thread launched successfully.")
    except Exception as e:
        logger.error(f"[Events Error] Could not start listener thread: {e}")

    # 4. Start the background scheduler (optional backup)
    # Note: We keep this started for timed future tasks, but the
    # immediate reactions are now handled by the Listener.
    # start_scheduler()

    yield

    logger.info("Shutting down EVO Omni Publisher Engine gracefully...")
    stop_scheduler()


app = FastAPI(
    title="Evo Omni Publisher Engine API",
    lifespan=lifespan
)

# Registering Routers
app.include_router(publish_router)
app.include_router(oauth_router)

if __name__ == "__main__":
    # Ensure uvicorn runs the app instance
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)