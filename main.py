# main.py
import uvicorn
import logging
import os
import threading
from fastapi import FastAPI
from fastapi.responses import PlainTextResponse, HTMLResponse
from contextlib import asynccontextmanager

from starlette.responses import FileResponse

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

@app.post("/")
async def root_post_handler():
    """Silences Oracle Cloud Health Check probes by returning 200 OK"""
    return {"status": "alive"}

@app.get("/{filename}.txt")
async def serve_tiktok_txt(filename: str):
    """
    Dynamically generates the exact verification signature TikTok expects.
    Matches any request for a .txt file where the name starts with 'tiktok'.
    """
    if filename.startswith("tiktok"):
        # Extract only the alphanumeric code by removing the "tiktok" prefix
        # Example: "tiktok9hoT5JX..." becomes "9hoT5JX..."
        verification_code = filename.replace("tiktok", "")

        # Build the EXACT signature string the TikTok bot is looking for
        signature = f"tiktok-developers-site-verification={verification_code}"

        # Return it as pure plain text (no hidden newline characters)
        return PlainTextResponse(signature)

    # Reject any other .txt requests that don't start with 'tiktok'
    return PlainTextResponse("File not found", status_code=404)

@app.get("/terms", response_class=HTMLResponse)
async def terms_of_service():
    return """
    <html>
        <body style="font-family: Arial, sans-serif; padding: 40px; max-width: 800px; margin: auto; line-height: 1.6; color: #333;">
            <h1>Terms of Service - Evo Omni Publisher Engine</h1>
            <p><strong>Last Updated: February 22, 2026</strong></p>
            <p>Welcome to Evo Omni Publisher Engine. By using our services, you agree to the following terms:</p>
            <ol>
                <li><strong>Service Description</strong>: Evo Omni Publisher Engine is a content management tool designed to schedule and automate video publishing to social media platforms.</li>
                <li><strong>User Responsibility</strong>: You are solely responsible for the content you upload and publish.</li>
                <li><strong>Data Usage</strong>: Our engine processes video files stored in your Oracle Cloud Infrastructure and publishes them on your behalf via OAuth authorization.</li>
                <li><strong>Limitation of Liability</strong>: Evo Omni Publisher Engine is provided "as is". We are not responsible for account suspensions.</li>
            </ol>
            <p><strong>Contact</strong>: Manuel Sandoval</p>
        </body>
    </html>
    """

@app.get("/privacy", response_class=HTMLResponse)
async def privacy_policy():
    return """
    <html>
        <body style="font-family: Arial, sans-serif; padding: 40px; max-width: 800px; margin: auto; line-height: 1.6; color: #333;">
            <h1>Privacy Policy - Evo Omni Publisher Engine</h1>
            <p><strong>Last Updated: February 22, 2026</strong></p>
            <p>Your privacy is paramount. This policy explains how Evo Omni Publisher Engine handles your data:</p>
            <ul>
                <li><strong>Information Collection</strong>: We only collect the necessary OAuth tokens provided by Google and TikTok to perform publishing actions.</li>
                <li><strong>Data Storage</strong>: All tokens and metadata are stored securely in a private PostgreSQL database. We do not store your passwords.</li>
                <li><strong>Data Usage</strong>: Your data is used exclusively to facilitate the automation of video uploads.</li>
                <li><strong>Data Deletion</strong>: You can revoke our engine's access at any time through your Google or TikTok security settings.</li>
            </ul>
            <p><strong>Owner</strong>: Manuel Sandoval</p>
        </body>
    </html>
    """

@app.get("/", response_class=HTMLResponse)
async def root_page():
    """
    Página de inicio temporal para grabar el flujo de OAuth de TikTok.
    """
    return """
    <html>
        <head>
            <title>Evo Omni Publisher Engine</title>
            <style>
                body { font-family: Arial, sans-serif; background-color: #0f172a; color: #f8fafc; text-align: center; padding: 100px; }
                .btn { background-color: #fe2c55; color: white; padding: 15px 30px; text-decoration: none; font-size: 18px; border-radius: 8px; font-weight: bold; font-family: sans-serif; }
                .btn:hover { background-color: #e11d48; }
            </style>
        </head>
        <body>
            <h1>🚀 Evo Omni Publisher Engine</h1>
            <p>Automated Video Publishing System for Creators</p>
            <br><br>
            <a href="/api/v1/oauth/login/tiktok/1" class="btn">Connect TikTok Account</a>
        </body>
    </html>
    """

# Registering Routers
app.include_router(publish_router)
app.include_router(oauth_router)

if __name__ == "__main__":
    # Ensure uvicorn runs the app instance
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)