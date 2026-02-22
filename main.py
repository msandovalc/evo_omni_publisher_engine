# main.py
import uvicorn
import logging
import os
import threading
from fastapi import FastAPI
from fastapi.responses import PlainTextResponse
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

@app.get("/tiktokkr6gkTdVdPNh4y3ne0Uok3B5xqWZFqWx.txt")
async def tiktok_verification():
    """
    Serves the TikTok verification code for app review.
    """
    return PlainTextResponse("tiktok-developers-site-verification=kr6gkTdVdPNh4y3ne0Uok3B5xqWZFqWx")

@app.get("/terms", response_class=PlainTextResponse)
async def terms_of_service():
    return """
        # Terms of Service - Evo Omni Publisher Engine
        
        **Last Updated: February 22, 2026**
        
        Welcome to Evo Omni Publisher Engine. By using our services, you agree to the following terms:
        
        1. **Service Description**: Evo Omni Publisher Engine is a content management tool designed to schedule and automate video publishing to social media platforms (YouTube, TikTok).
        2. **User Responsibility**: You are solely responsible for the content you upload and publish. You must comply with the community guidelines and terms of service of the third-party platforms (YouTube, TikTok).
        3. **Data Usage**: Our engine processes video files stored in your Oracle Cloud Infrastructure and publishes them on your behalf via OAuth authorization.
        4. **Limitation of Liability**: Evo Omni Publisher Engine is provided "as is". We are not responsible for account suspensions or content removal by third-party platforms.
        5. **Modification**: We reserve the right to update these terms as our engine evolves.
        
        **Contact**: Manuel Sandoval
    """

@app.get("/privacy", response_class=PlainTextResponse)
async def privacy_policy():
    return """
        # Privacy Policy - Evo Omni Publisher Engine
        
        **Last Updated: February 22, 2026**
        
        Your privacy is paramount. This policy explains how Evo Omni Publisher Engine handles your data:
        
        1. **Information Collection**: We only collect the necessary OAuth tokens (Access Tokens and Refresh Tokens) provided by Google and TikTok to perform publishing actions on your behalf.
        2. **Data Storage**: All tokens and metadata are stored securely in a private PostgreSQL database hosted on a secure Oracle VPS. We do not store your social media passwords.
        3. **Data Usage**: Your data is used exclusively to facilitate the automation of video uploads. We do not sell, trade, or share your data with third parties.
        4. **Data Deletion**: You can revoke our engine's access at any time through your Google or TikTok security settings.
        5. **Security**: We implement industry-standard security measures on our Oracle VPS to protect your information.
        
        **Owner**: Manuel Sandoval
    """

# Registering Routers
app.include_router(publish_router)
app.include_router(oauth_router)

if __name__ == "__main__":
    # Ensure uvicorn runs the app instance
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)