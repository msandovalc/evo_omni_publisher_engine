# publishers/tiktok.py
import requests
import logging
import os
import json
import math
import time
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
            # Update DB with new tokens
            cred = db.query(SocialCredential).filter_by(
                client_id=client_id, platform="tiktok"
            ).first()
            if cred:
                cred.token_data = new_data
                db.commit()
                return new_data

        logger.error(f"Failed to refresh token: {new_data}")
        return None
    except Exception as e:
        logger.error(f"Exception during TikTok token refresh: {e}")
        return None


def upload_video_to_tiktok(video_path: str, title: str, token_data: dict, client_id: int, db: Session, privacy_level: str = "SELF_ONLY"):
    """
    Publishes a video to TikTok using dynamic chunking and resilient retry logic.
    """
    access_token = token_data.get("access_token")
    if not access_token:
        logger.error("No TikTok access token provided.")
        return False

    try:
        file_size = os.path.getsize(video_path)
        CHUNK_SIZE = 20 * 1024 * 1024
        total_chunk_count = math.ceil(file_size / CHUNK_SIZE)

        logger.info(f"[TikTok] Video size: {file_size} bytes. Calculated chunks: {total_chunk_count}")

        # 1. Initialize the video upload session
        init_url = "https://open.tiktokapis.com/v2/post/publish/video/init/"
        headers = {
            "Authorization": f"Bearer {access_token}",
            "Content-Type": "application/json; charset=UTF-8"
        }

        payload = {
            "post_info": {
                "title": title,
                "privacy_level": privacy_level,
                "disable_duet": False,
                "disable_comment": False,
                "disable_stitch": False
            },
            "source_info": {
                "source": "FILE_UPLOAD",
                "video_size": file_size,
                "chunk_size": CHUNK_SIZE if total_chunk_count > 1 else file_size,
                "total_chunk_count": total_chunk_count
            }
        }

        res = requests.post(init_url, headers=headers, json=payload)
        res_json = res.json()

        # Handle token expiration
        if "error" in res_json and res_json["error"].get("code") == "access_token_invalid":
            logger.warning("TikTok token expired. Attempting refresh...")
            new_tokens = refresh_tiktok_token(client_id, db, token_data)
            if new_tokens:
                headers["Authorization"] = f"Bearer {new_tokens['access_token']}"
                res = requests.post(init_url, headers=headers, json=payload)
                res_json = res.json()
            else:
                return False

        if "data" not in res_json or not res_json["data"].get("upload_url"):
            logger.error(f"Failed to initialize video upload: {json.dumps(res_json)}")
            return False

        upload_url = res_json['data']['upload_url']
        publish_id = res_json['data']['publish_id']

        # 2. Upload the binary file using dynamic chunking with RETRY LOGIC
        logger.info(f"[TikTok] Streaming binary data. Publish ID: {publish_id}")

        MAX_RETRIES = 3  # ✨ Maximum attempts per chunk

        with open(video_path, 'rb') as f:
            for i in range(total_chunk_count):
                start = i * CHUNK_SIZE
                end = min(start + CHUNK_SIZE - 1, file_size - 1)
                chunk_data = f.read(CHUNK_SIZE)

                upload_headers = {
                    "Content-Type": "video/mp4",
                    "Content-Length": str(len(chunk_data)),
                    "Content-Range": f"bytes {start}-{end}/{file_size}"
                }

                # ✨ START RETRY LOOP FOR CURRENT CHUNK
                chunk_success = False
                for attempt in range(1, MAX_RETRIES + 1):
                    try:
                        # Added timeout to prevent the worker from hanging indefinitely
                        put_response = requests.put(upload_url, data=chunk_data, headers=upload_headers, timeout=60)

                        if put_response.status_code in [200, 201, 206]:
                            logger.info(f"[TikTok] Chunk {i + 1}/{total_chunk_count} uploaded successfully.")
                            chunk_success = True
                            break

                        elif put_response.status_code >= 500:
                            # 500+ errors (like 504 Gateway Timeout) are candidates for retry
                            logger.warning(
                                f"[TikTok] Server error {put_response.status_code} on chunk {i + 1}. Attempt {attempt}/{MAX_RETRIES}...")
                            time.sleep(5 * attempt)  # Exponential backoff
                        else:
                            # 400 errors are client-side; retrying won't help
                            logger.error(f"[TikTok] Fatal upload error {put_response.status_code}: {put_response.text}")
                            break

                    except requests.exceptions.RequestException as req_err:
                        logger.warning(
                            f"[TikTok] Network error on chunk {i + 1}: {req_err}. Attempt {attempt}/{MAX_RETRIES}...")
                        time.sleep(5 * attempt)

                if not chunk_success:
                    logger.error(
                        f"[TikTok] Failed to upload chunk {i + 1} after {MAX_RETRIES} attempts. Aborting post.")
                    return False

        logger.info(f"✅ SUCCESS! TikTok Video successfully submitted for processing. ID: {publish_id}")
        return True

    except Exception as e:
        logger.error(f"[TikTok] Critical error during video upload: {str(e)}")
        return False


def upload_photos_to_tiktok(photo_urls: list, title: str, token_data: dict, client_id: int, db: Session):
    """
    Publishes a Photo Carousel to TikTok.
    Uses 'PULL_FROM_URL' method, requiring public URLs for the images.
    """
    access_token = token_data.get("access_token")
    if not access_token:
        logger.error("No TikTok access token provided.")
        return False

    if not photo_urls or len(photo_urls) == 0:
        logger.error("[TikTok] No photo URLs provided for carousel upload.")
        return False

    try:
        # TikTok allows up to 35 photos, but we enforce the limit safely
        safe_photo_urls = photo_urls[:35]

        logger.info(f"[TikTok] Initializing photo carousel upload with {len(safe_photo_urls)} images...")

        init_url = "https://open.tiktokapis.com/v2/post/publish/content/init/"
        headers = {
            "Authorization": f"Bearer {access_token}",
            "Content-Type": "application/json; charset=UTF-8"
        }

        payload = {
            "post_info": {
                "title": title,
                "privacy_level": "PUBLIC",
                "disable_duet": False,
                "disable_comment": False,
                "disable_stitch": False
            },
            "source_info": {
                "source": "PULL_FROM_URL",
                "photo_cover_index": 1,  # First photo will be the cover
                "photo_images": safe_photo_urls
            },
            "post_mode": "DIRECT_POST",
            "media_type": "PHOTO"
        }

        res = requests.post(init_url, headers=headers, json=payload)
        res_json = res.json()

        # Handle token expiration automatically
        if "error" in res_json and res_json["error"].get("code") == "access_token_invalid":
            logger.warning("TikTok token expired. Attempting refresh...")
            new_tokens = refresh_tiktok_token(client_id, db, token_data)
            if new_tokens:
                headers["Authorization"] = f"Bearer {new_tokens['access_token']}"
                res = requests.post(init_url, headers=headers, json=payload)
                res_json = res.json()
            else:
                return False

        # TikTok returns success status inside the 'error' object with code 'ok'
        if res_json.get("error", {}).get("code") == "ok":
            publish_id = res_json.get("data", {}).get("publish_id", "UNKNOWN")
            logger.info(f"✅ SUCCESS! TikTok Photo Carousel initiated successfully. Publish ID: {publish_id}")
            return True
        else:
            logger.error(f"[TikTok] Failed to upload photos: {json.dumps(res_json)}")
            return False

    except Exception as e:
        logger.error(f"[TikTok] Critical error during photo upload: {str(e)}")
        return False