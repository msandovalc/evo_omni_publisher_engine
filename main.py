# main.py
import uvicorn
import logging
import os
import threading
from fastapi import FastAPI
from fastapi.responses import PlainTextResponse, HTMLResponse
from fastapi.staticfiles import StaticFiles
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

# Create temp directory if it doesn't exist
TEMP_MEDIA_DIR = "temp_media"
if not os.path.exists(TEMP_MEDIA_DIR):
    os.makedirs(TEMP_MEDIA_DIR)


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

# Mount the static directory so Meta can access videos via URL
app.mount("/temp", StaticFiles(directory=TEMP_MEDIA_DIR), name="temp")

logger.info(f"[Main] Static route /temp mounted pointing to {TEMP_MEDIA_DIR}")

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
    <!DOCTYPE html>
    <html lang="en">
    <head>
        <meta charset="UTF-8">
        <title>Terms of Service - Evo Omni Publisher</title>
        <style>
            body { font-family: 'Inter', sans-serif; padding: 40px; max-width: 800px; margin: auto; background-color: #0f172a; color: #f8fafc; line-height: 1.6; }
            h1, h3 { color: #38bdf8; }
            a { color: #fe2c55; text-decoration: none; }
            a:hover { text-decoration: underline; }
            .container { background: #1e293b; padding: 30px; border-radius: 15px; border: 1px solid #334155; }
        </style>
    </head>
    <body>
        <div class="container">
            <h1>Terms of Service for Evo Omni Publisher</h1>
            <p><strong>Last Updated: February 2026</strong></p>

            <p>These Terms of Service govern your use of <strong>Evo Omni Publisher</strong>. By accessing our platform, you agree to these terms.</p>

            <h3>1. Use of Service</h3>
            <p><strong>Evo Omni Publisher</strong> is an automation hub designed for content creators. You agree to use the service in compliance with the rules, guidelines, and API terms of third-party platforms including TikTok, Meta, and Google.</p>

            <h3>2. Account Termination</h3>
            <p>We reserve the right to terminate or suspend access to our service if we determine that you are violating platform policies, such as publishing spam or prohibited content.</p>

            <h3>3. Contact Information</h3>
            <p>For support, inquiries, or to report issues regarding the <strong>Evo Omni Publisher</strong> service, please contact us at:</p>

            <p><strong>Email:</strong> <a href="mailto:dev.ia.automation@gmail.com">dev.ia.automation@gmail.com</a></p>

            <p style="margin-top: 30px;"><a href="/">&larr; Back to Home</a></p>
        </div>
    </body>
    </html>
    """

@app.get("/privacy", response_class=HTMLResponse)
async def privacy_policy():
    return """
    <!DOCTYPE html>
    <html lang="en">
    <head>
        <meta charset="UTF-8">
        <title>Privacy Policy - Evo Omni Publisher</title>
        <style>
            body { font-family: 'Inter', sans-serif; padding: 40px; max-width: 800px; margin: auto; background-color: #0f172a; color: #f8fafc; line-height: 1.6; }
            h1, h3 { color: #38bdf8; }
            a { color: #fe2c55; text-decoration: none; }
            a:hover { text-decoration: underline; }
            .container { background: #1e293b; padding: 30px; border-radius: 15px; border: 1px solid #334155; }
        </style>
    </head>
    <body>
        <div class="container">
            <h1>Privacy Policy for Evo Omni Publisher</h1>
            <p><strong>Last Updated: February 2026</strong></p>

            <p>Welcome to <strong>Evo Omni Publisher</strong> ("we," "our," or "us"). This Privacy Policy explains how we collect, use, and protect your information when you use our web application (https://evo-omni-engine.duckdns.org) and our services to publish content to platforms like TikTok, Instagram, and YouTube.</p>

            <h3>1. Information We Collect</h3>
            <p>When you authorize <strong>Evo Omni Publisher</strong> to connect with your social accounts, we receive an access token that allows us to publish videos on your behalf. We do not store your passwords.</p>

            <h3>2. How We Use Your Information</h3>
            <p>The access tokens are used strictly to execute automated publishing commands initiated by you. We do not use your data for advertising or sell it to third parties.</p>

            <h3>3. Data Retention and Contact</h3>
            <p>You can revoke access to <strong>Evo Omni Publisher</strong> at any time directly from your platform settings. If you wish to delete your data from our servers, or if you have any privacy-related questions, please contact our support team:</p>

            <p><strong>Email:</strong> <a href="mailto:dev.ia.automation@gmail.com">dev.ia.automation@gmail.com</a></p>

            <p style="margin-top: 30px;"><a href="/">&larr; Back to Home</a></p>
        </div>
    </body>
    </html>
    """

@app.get("/", response_class=HTMLResponse)
async def root_page():
    return """
    <!DOCTYPE html>
    <html lang="en">
    <head>
        <meta charset="UTF-8">
        <title>Evo Omni Publisher - Social Media Automation</title>
        <style>
            body { font-family: 'Inter', sans-serif; background-color: #0f172a; color: #f8fafc; text-align: center; padding: 40px 20px; margin: 0; }
            .hero { max-width: 800px; margin: auto; padding-bottom: 40px; }
            .container { max-width: 500px; margin: auto; padding: 40px; background: #1e293b; border-radius: 20px; border: 1px solid #334155; box-shadow: 0 10px 30px rgba(0,0,0,0.5); }
            .features { display: flex; justify-content: center; gap: 20px; margin-bottom: 30px; color: #94a3b8; font-size: 0.9rem;}
            .button-group { display: flex; flex-direction: column; gap: 15px; margin-top: 20px; }
            .btn { color: white; padding: 16px 20px; text-decoration: none; font-size: 16px; border-radius: 12px; font-weight: bold; display: flex; align-items: center; justify-content: center; transition: 0.3s; border: none; cursor: pointer; }
            .btn:hover { transform: translateY(-2px); filter: brightness(1.1); }
            .btn-tiktok { background-color: #fe2c55; }
            .btn-instagram { background: linear-gradient(45deg, #f09433 0%, #e6683c 25%, #dc2743 50%, #cc2366 75%, #bc1888 100%); }
            .btn-youtube { background-color: #FF0000; }
            .links { margin-top: 40px; font-size: 14px; color: #94a3b8; }
            .links a { color: #38bdf8; text-decoration: none; margin: 0 10px; }
        </style>
    </head>
    <body>
        <div class="hero">
            <h1 style="font-size: 3rem; margin-bottom: 10px;">Evo Omni Publisher</h1>
            <p style="color: #94a3b8; font-size: 1.2rem;">The Professional Cloud-to-Social Automation Hub.</p>
            <div class="features">
                <span>✅ Auto-Publishing</span>
                <span>✅ Multi-Platform</span>
                <span>✅ Cloud Integrated</span>
            </div>
        </div>

        <div class="container">
            <h3 style="margin-top: 0;">Connect your Accounts</h3>
            <div class="button-group">
                <a href="/api/v1/oauth/login/tiktok/1" class="btn btn-tiktok">Connect TikTok Account</a>
                <a href="/api/v1/oauth/login/instagram/1" class="btn btn-instagram">Connect Instagram Business</a>
                <a href="/api/v1/oauth/login/youtube/1" class="btn btn-youtube">Connect YouTube Channel</a>
            </div>
        </div>

        <div class="links">
            <p>Evo Omni Publisher © 2026. All rights reserved.</p>
            <a href="/terms">Terms of Service</a> • <a href="/privacy">Privacy Policy</a>
            <p style="margin-top: 15px;">Support: <a href="mailto:dev.ia.automation@gmail.com" style="color: #38bdf8;">dev.ia.automation@gmail.com</a></p>
        </div>
    </body>
    </html>
    """

@app.get("/dashboard.html", include_in_schema=False)
async def serve_tiktok_dashboard():
    """
    Serves the MVP TikTok Dashboard HTML file for the UI audit.
    """
    # Gets the absolute path to the dashboard.html file located in the root directory
    file_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "dashboard.html")

    # Check if file exists to prevent server errors
    if not os.path.exists(file_path):
        return PlainTextResponse("Dashboard file not found. Please ensure dashboard.html is in the root directory.",
                                 status_code=404)

    return FileResponse(file_path)


# Registering Routers
app.include_router(publish_router)
app.include_router(oauth_router)

if __name__ == "__main__":
    # Ensure uvicorn runs the app instance
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)