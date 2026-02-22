# api/routes_oauth.py
import os
import logging
import json
from fastapi import APIRouter, Depends, Request, HTTPException
from fastapi.responses import RedirectResponse
from sqlalchemy.orm import Session
from google_auth_oauthlib.flow import Flow

from database.session import get_db
from database.models import SocialCredential

logger = logging.getLogger("OAuth-API")

os.environ['OAUTHLIB_INSECURE_TRANSPORT'] = '1'

router = APIRouter(
    prefix="/api/v1/oauth",
    tags=["OAuth Operations"]
)

# 1. Get the directory where THIS file is located (api/)
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

# 2. Build the correct path starting from the project root
# F:\Development\Pycharm\Projects\evo_omni_publisher_engine\credentials\client_secret_...json
CLIENT_SECRETS_FILE = os.path.join(BASE_DIR, "credentials", "client_secret_251021151101.json")

# This must match EXACTLY what you put in Google Console
REDIRECT_URI = "http://localhost:8000/api/v1/oauth/callback"
SCOPES = ["https://www.googleapis.com/auth/youtube.upload"]


@router.get("/login/{client_id}")
def login(client_id: int):
    """Starts the Google OAuth flow for a specific client."""
    logger.info(f"Starting YouTube OAuth flow for client: {client_id}")

    flow = Flow.from_client_secrets_file(
        CLIENT_SECRETS_FILE,
        scopes=SCOPES,
        redirect_uri=REDIRECT_URI
    )

    # access_type='offline' ensures we get a REFRESH TOKEN
    authorization_url, state = flow.authorization_url(
        access_type='offline',
        include_granted_scopes='true',
        prompt='consent'
    )

    # In a production app, save 'state' to verify it in the callback
    return RedirectResponse(authorization_url)


@router.get("/callback")
def callback(request: Request, db: Session = Depends(get_db)):
    """Handles the return from Google and saves tokens to the database."""

    # --- LOG DE DIAGNÓSTICO ---
    logger.info("¡CALLBACK RECIBIDO! Google está intentando entregarnos el código.")
    query_params = request.query_params
    logger.info(f"Parámetros recibidos: {query_params}")
    # --------------------------

    code = request.query_params.get("code")
    # In a real scenario, you'd pass the client_id through the 'state' parameter
    # For testing, we'll assume Client ID 1
    client_id = 1

    if not code:
        logger.error("No authorization code received from Google.")
        raise HTTPException(status_code=400, detail="Authorization code missing")

    logger.info("Exchanging authorization code for tokens...")

    flow = Flow.from_client_secrets_file(
        CLIENT_SECRETS_FILE,
        scopes=SCOPES,
        redirect_uri=REDIRECT_URI
    )

    flow.fetch_token(code=code)
    credentials = flow.credentials

    # Convert credentials to a dictionary for JSON storage
    token_data = {
        "token": credentials.token,
        "refresh_token": credentials.refresh_token,
        "token_uri": credentials.token_uri,
        "client_id": credentials.client_id,
        "client_secret": credentials.client_secret,
        "scopes": credentials.scopes
    }

    # Save or Update in Database
    existing_cred = db.query(SocialCredential).filter_by(
        client_id=client_id, platform="youtube"
    ).first()

    if existing_cred:
        existing_cred.token_data = token_data
        logger.info(f"Updated YouTube tokens for Client {client_id}")
    else:
        new_cred = SocialCredential(
            client_id=client_id,
            platform="youtube",
            token_data=token_data
        )
        db.add(new_cred)
        logger.info(f"Saved NEW YouTube tokens for Client {client_id}")

    db.commit()

    return {"status": "success", "message": "YouTube channel linked successfully!"}