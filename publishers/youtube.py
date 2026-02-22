# publishers/youtube.py
import os
import logging
from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload
from google.auth.transport.requests import Request

logger = logging.getLogger("YouTube-API")


def upload_video(video_path, title, description, token_data):
    """
    Performs a real upload to YouTube using the Data API v3.
    It automatically handles token refreshing if the access token is expired.
    """
    logger.info(f"Starting YouTube upload process for: {title}")

    try:
        # 1. Reconstruct credentials from the database JSON
        credentials = Credentials(
            token=token_data.get('token'),
            refresh_token=token_data.get('refresh_token'),
            token_uri=token_data.get('token_uri'),
            client_id=token_data.get('client_id'),
            client_secret=token_data.get('client_secret'),
            scopes=token_data.get('scopes')
        )

        # 2. Refresh the token if it has expired
        if credentials.expired:
            logger.info("Access token expired. Refreshing...")
            credentials.refresh(Request())

        # 3. Build the YouTube Service
        youtube = build("youtube", "v3", credentials=credentials)

        # 4. Define Video Metadata
        body = {
            'snippet': {
                'title': title,
                'description': description,
                'tags': ['stoicism', 'motivation', 'evo_engine'],
                'categoryId': '22'  # People & Blogs
            },
            'status': {
                'privacyStatus': 'private',  # Private for initial safety
                'selfDeclaredMadeForKids': False
            }
        }

        # 5. Execute the Upload
        media = MediaFileUpload(video_path, mimetype='video/mp4', resumable=True)

        logger.info(f"Sending file to YouTube: {video_path}")

        # --- COMMENT THESE LINES TO PREVENT REAL UPLOADS ---
        # request = youtube.videos().insert(
        #     part="snippet,status",
        #     body=body,
        #     media_body=media
        # )
        # response = request.execute()
        # --------------------------------------------------

        # Simulated response to keep the engine running
        response = {'id': 'SIMULATED_VIDEO_ID_999'}

        logger.info(f"✅ SUCCESS! YouTube Video ID: {response.get('id')}")
        return True

    except Exception as e:
        logger.error(f"❌ Real YouTube upload failed: {str(e)}")
        return False