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
        <head><title>Terms of Service | EVO Omni</title></head>
        <body style="font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif; padding: 50px; max-width: 900px; margin: auto; line-height: 1.8; color: #1e293b; background-color: #f8fafc;">
            <div style="background: white; padding: 40px; border-radius: 12px; box-shadow: 0 4px 6px -1px rgb(0 0 0 / 0.1);">
                <h1 style="color: #0f172a; border-bottom: 2px solid #e2e8f0; padding-bottom: 10px;">Terms of Service</h1>
                <p><strong>Last Updated: February 23, 2026</strong></p>
                <p>Welcome to <strong>Evo Omni Publisher Engine</strong>. By using our services, you agree to these terms:</p>
                <h3>1. Use of Service</h3>
                <p>Evo Omni provides automation for scheduling and publishing video content. You must comply with TikTok's Community Guidelines and Terms of Service at all times.</p>
                <h3>2. Content Ownership</h3>
                <p>You retain all rights to the content you publish. Evo Omni does not claim ownership of any media processed through our engine.</p>
                <h3>3. Limitation of Liability</h3>
                <p>We are not responsible for account restrictions resulting from the misuse of automation or the publication of prohibited content.</p>
                <hr style="border: 0; border-top: 1px solid #e2e8f0; margin: 30px 0;">
                <p><strong>Contact Support:</strong><br>
                Email: <a href="mailto:dev.ia.automation@gmail.com" style="color: #2563eb;">dev.ia.automation@gmail.com</a><br>
                Owner: Manuel Sandoval</p>
            </div>
        </body>
    </html>
    """

@app.get("/privacy", response_class=HTMLResponse)
async def privacy_policy():
    return """
    <html>
        <head><title>Privacy Policy | EVO Omni</title></head>
        <body style="font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif; padding: 50px; max-width: 900px; margin: auto; line-height: 1.8; color: #1e293b; background-color: #f8fafc;">
            <div style="background: white; padding: 40px; border-radius: 12px; box-shadow: 0 4px 6px -1px rgb(0 0 0 / 0.1);">
                <h1 style="color: #0f172a; border-bottom: 2px solid #e2e8f0; padding-bottom: 10px;">Privacy Policy</h1>
                <p><strong>Last Updated: February 23, 2026</strong></p>
                <p>Your privacy is our priority. This policy describes how we handle your information:</p>
                <ul>
                    <li><strong>Data Collection</strong>: We only store OAuth tokens (Access and Refresh) required to interact with social media APIs on your behalf.</li>
                    <li><strong>Security</strong>: Tokens are encrypted and stored in a private database. We never see or store your social media passwords.</li>
                    <li><strong>Third-Party Disclosure</strong>: We do not sell, trade, or share your data with external parties.</li>
                    <li><strong>Transparency</strong>: You can revoke Evo Omni's access at any time through your Google or TikTok security settings.</li>
                </ul>
                <hr style="border: 0; border-top: 1px solid #e2e8f0; margin: 30px 0;">
                <p><strong>Privacy Inquiries:</strong><br>
                Email: <a href="mailto:dev.ia.automation@gmail.com" style="color: #2563eb;">dev.ia.automation@gmail.com</a></p>
            </div>
        </body>
    </html>
    """

@app.get("/", response_class=HTMLResponse)
async def root_page():
    return """
    <html>
        <head>
            <title>Evo Omni Publisher Engine</title>
            <style>
                body { font-family: 'Inter', sans-serif; background-color: #0f172a; color: #f8fafc; text-align: center; padding: 100px; }
                .container { max-width: 600px; margin: auto; padding: 40px; background: #1e293b; border-radius: 16px; border: 1px solid #334155; }
                .btn { background-color: #fe2c55; color: white; padding: 16px 32px; text-decoration: none; font-size: 18px; border-radius: 12px; font-weight: bold; display: inline-block; transition: 0.3s; }
                .btn:hover { background-color: #e11d48; transform: translateY(-2px); }
                .links { margin-top: 30px; font-size: 14px; }
                .links a { color: #94a3b8; text-decoration: none; margin: 0 10px; }
            </style>
        </head>
        <body>
            <div class="container">
                <h1 style="font-size: 2.5rem; margin-bottom: 10px;">🚀 Evo Omni</h1>
                <p style="color: #94a3b8; margin-bottom: 40px;">Professional Cloud-to-Social Automation</p>
                <a href="/api/v1/oauth/login/tiktok/1" class="btn">Connect TikTok Account</a>
                <div class="links">
                    <a href="/terms">Terms of Service</a> • <a href="/privacy">Privacy Policy</a>
                </div>
            </div>
        </body>
    </html>
    """

# Registering Routers
app.include_router(publish_router)
app.include_router(oauth_router)

if __name__ == "__main__":
    # Ensure uvicorn runs the app instance
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)