import requests
import logging
import time

logger = logging.getLogger(__name__)


class FacebookPublisher:
    """
    Service to handle Video Reels publishing on Facebook Pages with status polling.
    """

    def __init__(self, access_token):
        self.access_token = access_token
        self.base_url = "https://graph.facebook.com/v19.0"

    def get_page_access_token(self, page_id):
        """
        Exchanges the User Access Token for a specific Page Access Token.
        """
        try:
            url = f"{self.base_url}/{page_id}"
            params = {
                "fields": "access_token",
                "access_token": self.access_token
            }
            res = requests.get(url, params=params).json()
            return res.get("access_token")
        except Exception as e:
            logger.error(f"[FB] Error fetching Page Token: {e}")
            return None

    def publish_reel(self, video_url, description, target_id):
        """
        Publishes a Reel using a 3-phase process with asynchronous status checking.
        """
        page_token = self.get_page_access_token(target_id)
        if not page_token:
            return False

        try:
            # Phase 1: Initialize the upload session
            init_url = f"{self.base_url}/{target_id}/video_reels"
            init_res = requests.post(init_url, data={
                "upload_phase": "start",
                "access_token": page_token
            }).json()

            video_id = init_res.get("video_id")
            if not video_id:
                logger.error(f"[FB] Initialization failed: {init_res}")
                return False

            logger.info(f"[FB] Session initialized. Video ID: {video_id}")

            # Phase 2: Instruct Meta to pull the video file
            upload_res = requests.post(f"{self.base_url}/{video_id}", data={
                "video_file_url": video_url,
                "access_token": page_token
            }).json()

            if not upload_res.get("success"):
                logger.error(f"[FB] Video pull request failed: {upload_res}")
                return False

            # Phase 2.5: Polling - Wait for Facebook to process the video
            # This prevents the 'Video Upload Is Missing' error
            max_attempts = 10
            attempt = 1
            is_ready = False

            while attempt <= max_attempts:
                logger.info(f"[FB] Checking processing status... (Attempt {attempt})")
                # Query the video status
                status_res = requests.get(f"{self.base_url}/{video_id}", params={
                    "fields": "video_status",
                    "access_token": page_token
                }).json()

                # Possible statuses: 'uploading', 'processing', 'ready', 'error'
                status = status_res.get("video_status")

                if status == "ready":
                    is_ready = True
                    logger.info(f"✅ [FB] Video is ready for publication.")
                    break
                elif status == "error":
                    logger.error(f"[FB] Meta reported a processing error: {status_res}")
                    return False

                # Wait before next check (increase wait time as attempts progress)
                time.sleep(15)
                attempt += 1

            if not is_ready:
                logger.error("[FB] Timeout: Video processing took too long.")
                return False

            # Phase 3: Finalize and publish
            final_res = requests.post(init_url, data={
                "upload_phase": "finish",
                "video_id": video_id,
                "video_state": "PUBLISHED",
                "description": description,
                "access_token": page_token
            }).json()

            if final_res.get("success"):
                logger.info(f"✅ [FB] Reel published successfully to Page {target_id}")
                return True
            else:
                logger.error(f"[FB] Finalization failed: {final_res}")
                return False

        except Exception as e:
            logger.error(f"[FB] Critical publishing error: {e}")
            return False