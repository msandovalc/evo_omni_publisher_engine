import requests
import logging
import time

# Set up specialized logger for Facebook
logger = logging.getLogger("EVO-Facebook")


class FacebookPublisher:
    """
    Service to handle Video Reels publishing on Facebook Pages with deep status polling.
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
        Publishes a Reel using a 3-phase process with enhanced diagnostic logging.
        """
        page_token = self.get_page_access_token(target_id)
        if not page_token:
            return False

        try:
            # PHASE 1: Initialize session
            init_url = f"{self.base_url}/{target_id}/video_reels"
            init_res = requests.post(init_url, data={
                "upload_phase": "start",
                "access_token": page_token
            }).json()

            video_id = init_res.get("video_id")
            if not video_id:
                logger.error(f"[FB] Initialization failed. Response: {init_res}")
                return False

            logger.info(f"[FB] Session initialized. Video ID: {video_id}")

            # PHASE 2: Start the PULL process from VPS
            upload_res = requests.post(f"{self.base_url}/{video_id}", data={
                "video_file_url": video_url,
                "access_token": page_token
            }).json()

            if not upload_res.get("success"):
                logger.error(f"[FB] Pull request failed. Response: {upload_res}")
                return False

            # PHASE 2.5: Deep Polling with Diagnostic Logging
            max_attempts = 15  # Increased for safety
            attempt = 1
            is_ready = False

            while attempt <= max_attempts:
                # Polling for status
                status_res = requests.get(f"{self.base_url}/{video_id}", params={
                    "fields": "video_status",
                    "access_token": page_token
                }).json()

                # --- DIAGNOSTIC LOGGING ---
                # This will let you see exactly what Meta is thinking
                logger.info(f"[FB] Polling Attempt {attempt}/{max_attempts} - Full Response: {status_res}")

                video_status_obj = status_res.get("video_status", {})
                current_state = video_status_obj.get("status")

                if current_state == "ready":
                    is_ready = True
                    logger.info(f"✅ [FB] Meta confirms video is READY.")
                    break
                elif current_state == "error":
                    logger.error(f"❌ [FB] Meta reported processing error: {video_status_obj}")
                    return False

                # If still 'processing' or 'uploading', we wait
                logger.info(f"[FB] Current state is '{current_state}'. Waiting 15s...")
                time.sleep(15)
                attempt += 1

            if not is_ready:
                logger.error(f"[FB] Timeout reached after {max_attempts} attempts.")
                return False

            # PHASE 3: Finalize Publication
            logger.info(f"[FB] Finalizing publication for video_id: {video_id}...")
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
                logger.error(f"❌ [FB] Publication finalization failed: {final_res}")
                return False

        except Exception as e:
            logger.error(f"❌ [FB] Critical exception: {str(e)}")
            return False