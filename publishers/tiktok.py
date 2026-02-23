# publishers/tiktok.py
import requests
import logging
import os

logger = logging.getLogger("TikTok-API")


def upload_video_to_tiktok(video_path, title, token_data):
    """
    Uploads a video to TikTok using the official Content Posting API V2.
    Note: For unaudited apps (Draft mode), privacy_level MUST be 'SELF_ONLY'.
    """
    logger.info(f"Starting REAL TikTok upload process for: {title}")

    access_token = token_data.get('access_token')

    if not access_token:
        logger.error("No access token found in token_data")
        return False

    try:
        file_size = os.path.getsize(video_path)

        # 1. Initialize the upload (Query TikTok for an upload URL)
        # Endpoint: https://developers.tiktok.com/doc/content-posting-api-reference-post-video/
        init_url = "https://open.tiktokapis.com/v2/post/publish/video/init/"
        headers = {
            "Authorization": f"Bearer {access_token}",
            "Content-Type": "application/json; charset=UTF-8"
        }

        # We must use 'SELF_ONLY' because the app is not yet audited by TikTok
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

        logger.info(f"Initializing TikTok upload for file: {os.path.basename(video_path)}")
        response = requests.post(init_url, headers=headers, json=body)
        res_json = response.json()

        if response.status_code != 200 or "data" not in res_json:
            logger.error(f"Failed to initialize TikTok upload: {res_json}")
            return False

        upload_url = res_json['data']['upload_url']
        publish_id = res_json['data']['publish_id']

        # 2. Upload the binary file (Streaming to the provided URL)
        logger.info(f"Streaming {file_size} bytes to TikTok...")
        with open(video_path, 'rb') as f:
            upload_headers = {
                "Content-Type": "video/mp4",
                "Content-Length": str(file_size)
            }
            # The binary data must be sent via a PUT request to the upload_url
            put_response = requests.put(upload_url, data=f, headers=upload_headers)

        if put_response.status_code in [200, 201]:
            logger.info(f"✅ SUCCESS! TikTok Video successfully published in private mode. ID: {publish_id}")
            return True
        else:
            logger.error(f"Binary upload failed: {put_response.text}")
            return False

    except Exception as e:
        logger.error(f"❌ TikTok upload failed: {str(e)}")
        return False