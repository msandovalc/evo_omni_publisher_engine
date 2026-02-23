# api/routes_oauth.py
import os
import logging
import urllib.parse
import requests  # Added for token exchange
from fastapi import APIRouter, Depends, Request, HTTPException
from fastapi.responses import RedirectResponse
from sqlalchemy.orm import Session
from google_auth_oauthlib.flow import Flow
from dotenv import load_dotenv

from database.session import get_db
from database.models import SocialCredential

load_dotenv()
logger = logging.getLogger("OAuth-API")
os.environ['OAUTHLIB_INSECURE_TRANSPORT'] = '1'

router = APIRouter(
    prefix="/api/v1/oauth",
    tags=["OAuth Operations"]
)

BASE_URL = os.getenv("DOMAIN_URL", "https://evo-omni-engine.duckdns.org")

# YouTube Config
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CLIENT_SECRETS_FILE = os.path.join(BASE_DIR, "credentials", "client_secret_251021151101.json")
YOUTUBE_SCOPES = ["https://www.googleapis.com/auth/youtube.upload"]

# TikTok Config
TIKTOK_CLIENT_ID = os.getenv("TIKTOK_CLIENT_ID")
TIKTOK_CLIENT_SECRET = os.getenv("TIKTOK_CLIENT_SECRET")


@router.get("/login/{platform}/{client_id}")
def login(platform: str, client_id: int):
    state_payload = f"client_id_{client_id}"

    if platform == "youtube":
        redirect_uri = f"{BASE_URL}/api/v1/oauth/callback/youtube"
        flow = Flow.from_client_secrets_file(CLIENT_SECRETS_FILE, scopes=YOUTUBE_SCOPES, redirect_uri=redirect_uri)
        authorization_url, _ = flow.authorization_url(access_type='offline', prompt='consent', state=state_payload)
        return RedirectResponse(authorization_url)

    elif platform == "tiktok":
        redirect_uri = f"{BASE_URL}/api/v1/oauth/callback/tiktok"
        params = {
            "client_key": TIKTOK_CLIENT_ID,
            "response_type": "code",
            "scope": "user.info.basic,video.publish",
            "redirect_uri": redirect_uri,
            "state": state_payload
        }
        auth_url = f"https://www.tiktok.com/v2/auth/authorize/?{urllib.parse.urlencode(params)}"
        return RedirectResponse(auth_url)

    raise HTTPException(status_code=400, detail="Platform not supported")


@router.get("/callback/{platform}")
def callback(platform: str, request: Request, db: Session = Depends(get_db)):
    code = request.query_params.get("code")
    state = request.query_params.get("state")

    if not code:
        raise HTTPException(status_code=400, detail="Authorization code missing")

    client_id = 1
    if state and state.startswith("client_id_"):
        client_id = int(state.split("_")[2])

    token_data = {}

    # --- YOUTUBE FLOW (Unchanged) ---
    if platform == "youtube":
        redirect_uri = f"{BASE_URL}/api/v1/oauth/callback/youtube"
        flow = Flow.from_client_secrets_file(CLIENT_SECRETS_FILE, scopes=YOUTUBE_SCOPES, redirect_uri=redirect_uri)
        flow.fetch_token(code=code)
        credentials = flow.credentials
        token_data = {
            "token": credentials.token,
            "refresh_token": credentials.refresh_token,
            "token_uri": credentials.token_uri,
            "client_id": credentials.client_id
        }

    # --- TIKTOK FLOW (Real Token Exchange) ---
    elif platform == "tiktok":
        redirect_uri = f"{BASE_URL}/api/v1/oauth/callback/tiktok"
        # Exchange the authorization code for an access token
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
        if "error" in token_data:
            logger.error(f"TikTok Token Error: {token_data}")
            raise HTTPException(status_code=400, detail=token_data.get("error_description"))

    # Save to Database
    existing_cred = db.query(SocialCredential).filter_by(client_id=client_id, platform=platform).first()
    if existing_cred:
        existing_cred.token_data = token_data
    else:
        new_cred = SocialCredential(client_id=client_id, platform=platform, token_data=token_data)
        db.add(new_cred)

    db.commit()
    return {"status": "success", "message": f"{platform.capitalize()} account linked!"}