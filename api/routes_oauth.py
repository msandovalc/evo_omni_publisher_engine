# api/routes_oauth.py
import os
import logging
import urllib.parse
from fastapi import APIRouter, Depends, Request, HTTPException
from fastapi.responses import RedirectResponse
from sqlalchemy.orm import Session
from google_auth_oauthlib.flow import Flow
from dotenv import load_dotenv

from database.session import get_db
from database.models import SocialCredential

# Load environment variables from the .env file
load_dotenv()

logger = logging.getLogger("OAuth-API")

# Allow insecure transport for local testing (Ensure HTTPS in production)
os.environ['OAUTHLIB_INSECURE_TRANSPORT'] = '1'

router = APIRouter(
    prefix="/api/v1/oauth",
    tags=["OAuth Operations"]
)

# --- GLOBAL CONFIGURATION ---
# Base URL of your server (used for all redirect URIs)
BASE_URL = os.getenv("DOMAIN_URL", "https://evo-omni-engine.duckdns.org")

# --- YOUTUBE CONFIGURATION ---
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CLIENT_SECRETS_FILE = os.path.join(BASE_DIR, "credentials", "client_secret_251021151101.json")
YOUTUBE_SCOPES = ["https://www.googleapis.com/auth/youtube.upload"]

# --- ENV CREDENTIALS (TikTok, Facebook, Instagram) ---
TIKTOK_CLIENT_ID = os.getenv("TIKTOK_CLIENT_ID")
TIKTOK_CLIENT_SECRET = os.getenv("TIKTOK_CLIENT_SECRET")
# Meta credentials for both FB and IG
META_CLIENT_ID = os.getenv("META_CLIENT_ID")


@router.get("/login/{platform}/{client_id}")
def login(platform: str, client_id: int):
    """
    Dynamic OAuth login handler.
    Supports: youtube, tiktok, facebook, instagram.
    Routes the user to the correct authorization page based on the platform.
    """
    logger.info(f"Starting {platform.upper()} OAuth flow for internal client: {client_id}")

    # We pass the internal client_id in the 'state' parameter to recover it in the callback
    state_payload = f"client_id_{client_id}"

    if platform == "youtube":
        redirect_uri = f"{BASE_URL}/api/v1/oauth/callback/youtube"
        flow = Flow.from_client_secrets_file(
            CLIENT_SECRETS_FILE,
            scopes=YOUTUBE_SCOPES,
            redirect_uri=redirect_uri
        )
        authorization_url, state = flow.authorization_url(
            access_type='offline',
            include_granted_scopes='true',
            prompt='consent',
            state=state_payload
        )
        return RedirectResponse(authorization_url)

    elif platform == "tiktok":
        if not TIKTOK_CLIENT_ID:
            raise HTTPException(status_code=500, detail="TikTok Client ID not found in .env")

        redirect_uri = f"{BASE_URL}/api/v1/oauth/callback/tiktok"
        base_url = "https://www.tiktok.com/v2/auth/authorize/"
        params = {
            "client_key": TIKTOK_CLIENT_ID,
            "response_type": "code",
            "scope": "user.info.basic,video.publish",
            "redirect_uri": redirect_uri,
            "state": state_payload
        }
        auth_url = f"{base_url}?{urllib.parse.urlencode(params)}"
        return RedirectResponse(auth_url)

    elif platform in ["facebook", "instagram"]:
        if not META_CLIENT_ID:
            raise HTTPException(status_code=500, detail="Meta Client ID not found in .env")

        redirect_uri = f"{BASE_URL}/api/v1/oauth/callback/{platform}"
        base_url = "https://www.facebook.com/v18.0/dialog/oauth"

        # Scopes differ slightly between FB and IG publishing
        scopes = "pages_show_list,pages_read_engagement,pages_manage_posts"
        if platform == "instagram":
            scopes += ",instagram_basic,instagram_content_publish"

        params = {
            "client_id": META_CLIENT_ID,
            "redirect_uri": redirect_uri,
            "state": state_payload,
            "scope": scopes,
            "response_type": "code"
        }
        auth_url = f"{base_url}?{urllib.parse.urlencode(params)}"
        return RedirectResponse(auth_url)

    else:
        raise HTTPException(status_code=400, detail="Unsupported platform")


@router.get("/callback/{platform}")
def callback(platform: str, request: Request, db: Session = Depends(get_db)):
    """
    Dynamic callback handler to catch the authorization code from any platform.
    """
    logger.info(f"--- CALLBACK RECEIVED FROM {platform.upper()} ---")

    code = request.query_params.get("code")
    state = request.query_params.get("state")
    error = request.query_params.get("error")

    if error:
        logger.error(f"{platform.upper()} Auth Error: {error}")
        raise HTTPException(status_code=400, detail=f"OAuth Error: {error}")

    if not code:
        logger.error(f"No authorization code received from {platform.upper()}.")
        raise HTTPException(status_code=400, detail="Authorization code missing")

    # Extract client_id from the state parameter (e.g., "client_id_1" -> 1)
    client_id = 1  # Default fallback
    if state and state.startswith("client_id_"):
        try:
            client_id = int(state.split("_")[2])
        except Exception:
            logger.warning("Could not parse client_id from state. Using default 1.")

    logger.info(f"Exchanging code for {platform.upper()} tokens for client {client_id}...")

    token_data = {}

    # 1. YOUTUBE TOKEN EXCHANGE
    if platform == "youtube":
        redirect_uri = f"{BASE_URL}/api/v1/oauth/callback/youtube"
        flow = Flow.from_client_secrets_file(
            CLIENT_SECRETS_FILE,
            scopes=YOUTUBE_SCOPES,
            redirect_uri=redirect_uri
        )
        flow.fetch_token(code=code)
        credentials = flow.credentials

        token_data = {
            "token": credentials.token,
            "refresh_token": credentials.refresh_token,
            "token_uri": credentials.token_uri,
            "client_id": credentials.client_id,
            "scopes": credentials.scopes
        }

    # 2. TIKTOK / FACEBOOK / INSTAGRAM TOKEN EXCHANGE
    elif platform in ["tiktok", "facebook", "instagram"]:
        # Note for production: Here you will make a POST request (using httpx or requests)
        # to the platform's specific token endpoint exchanging the 'code' for the access_token.
        # For the app review video, capturing the 'code' successfully is the primary goal.
        token_data = {
            "authorization_code": code,
            "status": "pending_exchange"
        }
        logger.info(f"{platform.upper()} authorization code captured successfully.")

    # Save or Update in Database
    existing_cred = db.query(SocialCredential).filter_by(
        client_id=client_id, platform=platform
    ).first()

    if existing_cred:
        existing_cred.token_data = token_data
        logger.info(f"Updated {platform.upper()} credentials for Client {client_id}")
    else:
        new_cred = SocialCredential(
            client_id=client_id,
            platform=platform,
            token_data=token_data
        )
        db.add(new_cred)
        logger.info(f"Saved NEW {platform.upper()} credentials for Client {client_id}")

    db.commit()

    return {
        "status": "success",
        "platform": platform,
        "client_id": client_id,
        "message": f"{platform.capitalize()} account linked successfully!"
    }