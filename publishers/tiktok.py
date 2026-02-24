# publishers/tiktok.py
import requests
import logging
import os
import json
from sqlalchemy.orm import Session
from database.models import SocialCredential

logger = logging.getLogger("TikTok-API")


def refresh_tiktok_token(client_id: int, db: Session, old_token_data: dict):
    """
    Calls TikTok API to refresh the access_token using the refresh_token.
    """
    try:
        logger.info(f"Refreshing TikTok token for client {client_id}")
        response = requests.post(
            "https://open.tiktokapis.com/v2/oauth/token/",
            headers={"Content-Type": "application/x-www-form-urlencoded"},
            data={
                "client_key": os.getenv("TIKTOK_CLIENT_ID"),
                "client_secret": os.getenv("TIKTOK_CLIENT_SECRET"),
                "grant_type": "refresh_token",
                "refresh_token": old_token_data.get("refresh_token")
            }
        )
        new_data = response.json()

        if response.status_code == 200 and "access_token" in new_data:
            # Update DB
            cred = db.query(SocialCredential).filter_by(
                client_id=client_id, platform="tiktok"
            ).first()
            if cred:
                cred.token_data = new_data
                db.commit()
                return new_data

        logger.error(f"Failed to refresh TikTok token: {new_data}")
        return None
    except Exception as e:
        logger.error(f"Error during TikTok token refresh: {e}")
        return None

def upload_video_to_tiktok(video_path, title, token_data, client_id=None, db=None):
    """
    Uploads a video to TikTok using the official Content Posting API V2.
    NOTE: For un-audited apps, the TikTok ACCOUNT must be set to 'Private'.
    Error 416 is resolved by adding the 'Content-Range' header.
    """
    logger.info(f"Starting REAL TikTok upload process for: {title}")

    access_token = token_data.get('access_token')

    if not access_token:
        logger.error("No access token found in token_data. Cannot proceed.")
        return False

    try:
        file_size = os.path.getsize(video_path)

        # 1. Initialize the upload
        init_url = "https://open.tiktokapis.com/v2/post/publish/video/init/"
        headers = {
            "Authorization": f"Bearer {access_token}",
            "Content-Type": "application/json; charset=UTF-8"
        }

        body = {
            "post_info": {
                "title": title,
                "privacy_level": "SELF_ONLY",
                "disable_duet": False,
                "disable_comment": False,
                "disable_stitch": False,
                "video_ad_tag": False
            },
            "source_info": {
                "source": "FILE_UPLOAD",
                "video_size": file_size,
                "chunk_size": file_size,
                "total_chunk_count": 1
            }
        }

        logger.info(f"Initializing upload for {os.path.basename(video_path)} ({file_size} bytes)")
        response = requests.post(init_url, headers=headers, json=body)
        res_json = response.json()

        # Handle Expired Token (Error 401 or specific TikTok error codes)
        if response.status_code == 401 or res_json.get("error", {}).get("code") == "access_token_invalid":
            logger.warning("⚠️ TikTok Access Token expired. Attempting refresh...")
            if db and client_id:
                new_tokens = refresh_tiktok_token(client_id, token_data, db)
                if new_tokens:
                    # Retry with new token
                    headers["Authorization"] = f"Bearer {new_tokens['access_token']}"
                    response = requests.post(init_url, headers=headers, json=body)
                    res_json = response.json()
                else:
                    return False
            else:
                logger.error("Cannot refresh token: Database session or Client ID missing.")
                return False

        if response.status_code != 200 or "data" not in res_json:
            logger.error(f"Failed to initialize: {json.dumps(res_json)}")
            return False

        upload_url = res_json['data']['upload_url']
        publish_id = res_json['data']['publish_id']

        # 2. Upload the binary file (Streaming)
        # Fix for Error 416: Added Content-Range header
        logger.info(f"Streaming binary data to TikTok. Publish ID: {publish_id}")

        with open(video_path, 'rb') as f:
            upload_headers = {
                "Content-Type": "video/mp4",
                "Content-Length": str(file_size),
                "Content-Range": f"bytes 0-{file_size - 1}/{file_size}"  # 👈 Crucial fix for 416 error
            }
            # TikTok expects the raw bytes via PUT to the provided upload_url
            put_response = requests.put(upload_url, data=f, headers=upload_headers)

        if put_response.status_code in [200, 201]:
            logger.info(f"✅ SUCCESS! TikTok Video successfully published. ID: {publish_id}")
            return True
        else:
            logger.error(f"Binary upload failed with status {put_response.status_code}")
            logger.error(f"PUT Response text: {put_response.text}")
            return False

    except Exception as e:
        logger.error(f"❌ TikTok upload critical failure: {str(e)}")
        return False