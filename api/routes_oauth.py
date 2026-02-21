# api/routes_oauth.py
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from database.session import get_db
from database.models import SocialCredential

router = APIRouter(
    prefix="/auth",
    tags=["OAuth Authentication"]
)


@router.get("/login/{platform}")
def login_to_platform(platform: str, client_id: int):
    """
    Initiates the OAuth2 flow for a specific platform (e.g., youtube, tiktok).
    In a real scenario, this redirects the user to the provider's consent screen.
    """
    allowed_platforms = ["youtube", "instagram", "tiktok"]
    if platform not in allowed_platforms:
        raise HTTPException(status_code=400, detail="Unsupported platform.")

    # TODO: Generate authorization URL based on the platform and redirect
    return {"message": f"Redirecting to {platform} OAuth consent screen for client {client_id}..."}


@router.get("/callback")
def oauth_callback(code: str, state: str, db: Session = Depends(get_db)):
    """
    Receives the authorization code from the provider, exchanges it for tokens,
    and saves them in the database.
    """
    # TODO: Exchange 'code' for access_token and refresh_token via HTTP request

    # Mock token saving logic for MVP
    return {"message": "OAuth successful. Tokens saved to database."}