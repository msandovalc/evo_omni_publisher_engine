# api/routes_oauth.py
import os
import logging
import urllib.parse
import requests  # Required for real-time token exchange
from fastapi import APIRouter, Depends, Request, HTTPException
from fastapi.responses import RedirectResponse
from sqlalchemy.orm import Session
from google_auth_oauthlib.flow import Flow
from dotenv import load_dotenv

from database.session import get_db
from database.models import SocialCredential

# Load environment variables
load_dotenv()

logger = logging.getLogger("OAuth-API")

# Allow insecure transport for development (Ensure HTTPS in production)
os.environ['OAUTHLIB_INSECURE_TRANSPORT'] = '1'

router = APIRouter(
    prefix="/api/v1/oauth",
    tags=["OAuth Operations"]
)

# --- GLOBAL CONFIGURATION ---
BASE_URL = os.getenv("DOMAIN_URL", "https://evo-omni-engine.duckdns.org")

# --- YOUTUBE CONFIGURATION ---
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CLIENT_SECRETS_FILE = os.path.join(BASE_DIR, "credentials", "client_secret_251021151101.json")
YOUTUBE_SCOPES = ["https://www.googleapis.com/auth/youtube.upload"]

# --- TIKTOK CREDENTIALS ---
TIKTOK_CLIENT_ID = os.getenv("TIKTOK_CLIENT_ID")
TIKTOK_CLIENT_SECRET = os.getenv("TIKTOK_CLIENT_SECRET")


@router.get("/login/{platform}/{client_id}")
def login(platform: str, client_id: int):
    """
    Initializes the OAuth flow for the requested platform.
    """
    logger.info(f"🟢 Initializing {platform.upper()} login for client: {client_id}")
    state_payload = f"client_id_{client_id}"

    if platform == "youtube":
        redirect_uri = f"{BASE_URL}/api/v1/oauth/callback/youtube"
        flow = Flow.from_client_secrets_file(
            CLIENT_SECRETS_FILE,
            scopes=YOUTUBE_SCOPES,
            redirect_uri=redirect_uri
        )
        authorization_url, _ = flow.authorization_url(
            access_type='offline',
            include_granted_scopes='true',
            prompt='consent',
            state=state_payload
        )
        return RedirectResponse(authorization_url)

    elif platform == "tiktok":
        redirect_uri = f"{BASE_URL}/api/v1/oauth/callback/tiktok"
        # Scopes: user.info.basic is needed for identity, video.publish for uploading
        scopes = "user.info.basic,video.publish"

        params = {
            "client_key": TIKTOK_CLIENT_ID,
            "response_type": "code",
            "scope": scopes,
            "redirect_uri": redirect_uri,
            "state": state_payload
        }
        auth_url = f"https://www.tiktok.com/v2/auth/authorize/?{urllib.parse.urlencode(params)}"
        logger.info(f"🚀 Redirecting to TikTok: {auth_url}")
        return RedirectResponse(auth_url)

    raise HTTPException(status_code=400, detail=f"Platform {platform} is not supported.")


@router.get("/callback/{platform}")
def callback(platform: str, request: Request, db: Session = Depends(get_db)):
    """
    Handles the redirect from the provider and exchanges the code for real tokens.
    """
    logger.info(f"🟢 Callback received for {platform.upper()}")

    code = request.query_params.get("code")
    state = request.query_params.get("state")
    error = request.query_params.get("error")

    if error:
        logger.error(f"❌ {platform.upper()} Error: {error}")
        raise HTTPException(status_code=400, detail=f"OAuth Error: {error}")

    if not code:
        raise HTTPException(status_code=400, detail="Authorization code missing")

    # Extract client_id from state
    client_id = 1
    if state and state.startswith("client_id_"):
        try:
            client_id = int(state.split("_")[2])
        except Exception:
            logger.warning("Could not parse client_id, defaulting to 1")

    token_data = {}

    # --- YOUTUBE TOKEN EXCHANGE (Flow based) ---
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
            "client_id": credentials.client_id
        }

    # --- TIKTOK TOKEN EXCHANGE (Request based) ---
    elif platform == "tiktok":
        redirect_uri = f"{BASE_URL}/api/v1/oauth/callback/tiktok"

        # We must perform a POST request to exchange the code for the access_token
        logger.info(f"Exchanging code for TikTok access_token for client {client_id}")
        response = requests.post(
            "https://open.tiktokapis.com/v2/oauth/token/",
            headers={"Content-Type": "application/x-www-form-urlencoded"},
            data={
                "client_key": TIKTOK_CLIENT_ID,
                "client_secret": TIKTOK_CLIENT_SECRET,
                "code": code,
                "grant_type": "authorization_code",
                "redirect_uri": redirect_uri,
            }
        )

        token_data = response.json()

        if response.status_code != 200 or "access_token" not in token_data:
            logger.error(f"❌ TikTok Token Exchange failed: {token_data}")
            raise HTTPException(status_code=400, detail="Could not retrieve TikTok tokens")

    # --- DATABASE PERSISTENCE ---
    existing_cred = db.query(SocialCredential).filter_by(
        client_id=client_id, platform=platform
    ).first()

    if existing_cred:
        existing_cred.token_data = token_data
        logger.info(f"💾 Updated {platform.upper()} credentials for Client {client_id}")
    else:
        new_cred = SocialCredential(
            client_id=client_id,
            platform=platform,
            token_data=token_data
        )
        db.add(new_cred)
        logger.info(f"💾 Saved NEW {platform.upper()} credentials for Client {client_id}")

    db.commit()
    logger.info(f"🎉 {platform.upper()} linking process complete.")

    return {
        "status": "success",
        "platform": platform,
        "client_id": client_id,
        "message": f"{platform.capitalize()} account linked successfully!"
    }