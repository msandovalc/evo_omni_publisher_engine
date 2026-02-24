import requests
import logging

logger = logging.getLogger(__name__)


class FacebookPublisher:
    """
    Service to handle Video Reels publishing on Facebook Pages using Page Access Tokens.
    """

    def __init__(self, access_token):  # Parameter name must match the Manager call
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
                "access_token": self.access_token  # Uses the token provided in __init__
            }
            res = requests.get(url, params=params).json()
            page_token = res.get("access_token")

            if not page_token:
                logger.error(f"[FB] Could not retrieve Page Token for {page_id}: {res}")
                return None

            return page_token
        except Exception as e:
            logger.error(f"[FB] Error fetching Page Token: {e}")
            return None

    def publish_reel(self, video_url, description, target_id):
        """
        Publishes a Reel using the Page Access Token.
        """
        # Step 1: Get the specific token for this Page
        page_token = self.get_page_access_token(target_id)
        if not page_token:
            return False

        try:
            # Phase 1: Initialize the upload session on the Page
            init_url = f"{self.base_url}/{target_id}/video_reels"
            init_payload = {
                "upload_phase": "start",
                "access_token": page_token
            }
            init_res = requests.post(init_url, data=init_payload).json()
            video_id = init_res.get("video_id")

            if not video_id:
                logger.error(f"[FB] Init failed for Page {target_id}: {init_res}")
                return False

            # Phase 2: Request Meta to pull the video from public VPS URL
            upload_url = f"{self.base_url}/{video_id}"
            upload_payload = {
                "video_file_url": video_url,
                "access_token": page_token
            }
            requests.post(upload_url, data=upload_payload)

            # Phase 3: Finalize publication
            publish_payload = {
                "upload_phase": "finish",
                "video_state": "PUBLISHED",
                "description": description,
                "access_token": page_token
            }
            final_res = requests.post(init_url, data=publish_payload).json()

            if final_res.get("success"):
                logger.info(f"✅ [FB] Reel published successfully to Page {target_id}")
                return True
            else:
                logger.error(f"[FB] Publish failed: {final_res}")
                return False

        except Exception as e:
            logger.error(f"[FB] Critical publishing error: {e}")
            return False