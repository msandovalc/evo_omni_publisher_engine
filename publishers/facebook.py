import requests
import logging

logger = logging.getLogger(__name__)


class FacebookPublisher:
    """
    Service to handle Video Reels publishing on Facebook Pages.
    """

    def __init__(self, access_token):
        self.access_token = access_token
        self.base_url = "https://graph.facebook.com/v19.0"

    def publish_reel(self, video_url, description, target_id):
        try:
            # Phase 1: Initialize the video upload session on the Facebook Page
            init_url = f"{self.base_url}/{target_id}/video_reels"
            init_payload = {
                "upload_phase": "start",
                "access_token": self.access_token
            }
            init_res = requests.post(init_url, data=init_payload).json()
            video_id = init_res.get("video_id")

            if not video_id:
                logger.error(f"[FB] Failed to initialize Reel: {init_res}")
                return False

            # Phase 2: Provide the public VPS URL so Meta can pull the video file
            upload_url = f"{self.base_url}/{video_id}"
            upload_payload = {
                "video_file_url": video_url,
                "access_token": self.access_token
            }
            upload_res = requests.post(upload_url, data=upload_payload).json()

            # Phase 3: Finalize and publish the Reel
            # Meta processes the video asynchronously after this call
            publish_payload = {
                "upload_phase": "finish",
                "video_state": "PUBLISHED",
                "description": description,
                "access_token": self.access_token
            }
            final_res = requests.post(init_url, data=publish_payload).json()

            if final_res.get("success"):
                logger.info(f"✅ [FB] Reel published successfully to Page {target_id}")
                return True
            else:
                logger.error(f"[FB] Final publish failed: {final_res}")
                return False

        except Exception as e:
            logger.error(f"[FB] Critical error during publishing: {e}")
            return False