# api/routes_oauth.py
import os
import logging
import urllib.parse
import requests  # Required for real-time token exchange
from fastapi import APIRouter, Depends, Request, HTTPException
from fastapi.responses import RedirectResponse, HTMLResponse
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

# --- FACEBOOK / INSTAGRAM CONFIGURATION ---
FB_APP_ID = os.getenv("FACEBOOK_APP_ID")
FB_APP_SECRET = os.getenv("FACEBOOK_APP_SECRET")
FB_REDIRECT_URI = f"{BASE_URL}/api/v1/oauth/callback/facebook"

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

    elif platform == "instagram":
        redirect_uri = f"{BASE_URL}/api/v1/oauth/callback/instagram"
        # Scopes required for Reels publishing and account management
        scopes = "instagram_basic,instagram_content_publish,pages_read_engagement,pages_show_list,public_profile"

        params = {
            "client_id": FB_APP_ID,
            "redirect_uri": redirect_uri,
            "scope": scopes,
            "state": state_payload,
            "response_type": "code"
        }
        auth_url = f"https://www.facebook.com/v22.0/dialog/oauth?{urllib.parse.urlencode(params)}"
        logger.info(f"🚀 Redirecting to Facebook/Instagram: {auth_url}")
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

    # --- INSTAGRAM EXCHANGE (Request based) ---
    elif platform == "instagram":
        # 1. Exchange short-lived code for access token
        token_url = "https://graph.facebook.com/v19.0/oauth/access_token"
        params = {
            "client_id": os.getenv("FACEBOOK_APP_ID"),
            "client_secret": os.getenv("FACEBOOK_APP_SECRET"),
            "redirect_uri": f"{BASE_URL}/api/v1/oauth/callback/instagram",
            "code": code
        }
        res = requests.get(token_url, params=params).json()
        short_token = res.get("access_token")

        # 2. Exchange for Long-Lived Token
        ll_params = {
            "grant_type": "fb_exchange_token",
            "client_id": os.getenv("FACEBOOK_APP_ID"),
            "client_secret": os.getenv("FACEBOOK_APP_SECRET"),
            "fb_exchange_token": short_token
        }
        ll_res = requests.get(token_url, params=ll_params).json()
        long_token = ll_res.get("access_token")

        # 3. Discover Instagram Business Account
        # Fetch pages linked to the user
        pages_res = requests.get(
            f"https://graph.facebook.com/v19.0/me/accounts?access_token={long_token}"
        ).json()

        accounts_list = []
        selected_account_id = None

        if "data" in pages_res:
            for page in pages_res["data"]:
                page_id = page["id"]
                page_name = page["name"]

                ig_info = requests.get(
                    f"https://graph.facebook.com/v19.0/{page_id}?fields=instagram_business_account&access_token={long_token}"
                ).json()

                if "instagram_business_account" in ig_info:
                    ig_id = ig_info["instagram_business_account"]["id"]
                    account_entry = {"ig_id": ig_id, "page_name": page_name, "page_id": page_id}
                    accounts_list.append(account_entry)

                    if page_name == 'El origen del todo':
                        selected_account_id = ig_id

        if not selected_account_id and accounts_list:
            selected_account_id = accounts_list[0]['ig_id']

        token_data = {
            "access_token": long_token,
            "instagram_account_id": selected_account_id,
            "available_accounts": accounts_list,
            "token_type": "bearer"
        }

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

    # 1. Define platform-specific styles and icons
    platform_meta = {
        "youtube": {
            "color": "#FF0000",
            "icon": "https://cdn-icons-png.flaticon.com/512/1384/1384060.png",
            "label": "YouTube"
        },
        "tiktok": {
            "color": "#00f2ea", # TikTok Cyan/Red mix effect
            "icon": "https://cdn-icons-png.flaticon.com/512/3046/3046121.png",
            "label": "TikTok"
        },
        "instagram": {
            "color": "#E1306C",
            "icon": "https://cdn-icons-png.flaticon.com/512/174/174855.png",
            "label": "Instagram"
        }
    }

    # Get current platform metadata (default to generic if not found)
    meta = platform_meta.get(platform.lower(), {
        "color": "#22c55e",
        "icon": "✅",
        "label": platform.capitalize()
    })

    return HTMLResponse(content=f"""
        <html>
            <head>
                <title>{meta['label']} Connected | EVO Omni</title>
                <style>
                    body {{ 
                        font-family: 'Inter', -apple-system, sans-serif; 
                        display: flex; 
                        align-items: center; 
                        justify-content: center; 
                        height: 100vh; 
                        background: #0f172a; 
                        color: white; 
                        margin: 0;
                    }}
                    .card {{ 
                        background: #1e293b; 
                        padding: 60px; 
                        border-radius: 24px; 
                        box-shadow: 0 20px 50px rgba(0,0,0,0.5); 
                        border: 1px solid #334155; 
                        max-width: 400px;
                        width: 90%;
                        position: relative;
                        overflow: hidden;
                    }}
                    .card::before {{
                        content: "";
                        position: absolute;
                        top: 0; left: 0; width: 100%; height: 5px;
                        background: {meta['color']};
                    }}
                    .logo-container {{
                        width: 80px;
                        height: 80px;
                        background: #0f172a;
                        border-radius: 20px;
                        display: flex;
                        align-items: center;
                        justify-content: center;
                        margin: 0 auto 25px;
                        border: 2px solid #334155;
                    }}
                    .logo-container img {{
                        width: 45px;
                        height: 45px;
                        object-fit: contain;
                    }}
                    h1 {{ 
                        font-size: 24px;
                        margin-bottom: 10px; 
                        color: white;
                    }}
                    p {{ 
                        color: #94a3b8; 
                        font-size: 16px; 
                        line-height: 1.5;
                        margin-bottom: 30px;
                    }}
                    .platform-badge {{
                        display: inline-block;
                        padding: 5px 15px;
                        border-radius: 20px;
                        background: {meta['color']}33; /* 20% opacity */
                        color: {meta['color']};
                        font-weight: bold;
                        font-size: 14px;
                        text-transform: uppercase;
                        letter-spacing: 1px;
                    }}
                    .footer-text {{
                        font-size: 13px;
                        opacity: 0.6;
                        margin-top: 20px;
                    }}
                </style>
            </head>
            <body>
                <div class="card">
                    <div class="logo-container">
                        <img src="{meta['icon']}" alt="{meta['label']}">
                    </div>
                    <div class="platform-badge">{meta['label']}</div>
                    <h1>Success!</h1>
                    <p>Your <strong>{meta['label']}</strong> account has been securely linked to the <strong>EVO Omni Publisher</strong>.</p>
                    <div class="footer-text">You can safely close this tab now.</div>
                </div>
            </body>
        </html>
    """)