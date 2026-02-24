import requests
import logging
import time

# Set up specialized logger for Facebook
logger = logging.getLogger("EVO-Facebook")


class FacebookPublisher:
    """
    Service to handle Video Reels publishing on Facebook Pages using Graph API v25.0.
    Implements the strict 3-phase upload process via rupload.facebook.com.
    """

    def __init__(self, access_token):
        self.access_token = access_token
        # Updated to v25.0 as per latest official documentation
        self.api_version = "v25.0"
        self.base_graph_url = f"https://graph.facebook.com/{self.api_version}"
        self.base_rupload_url = f"https://rupload.facebook.com/video-upload/{self.api_version}"

    def get_page_access_token(self, page_id):
        """
        Exchanges the User Access Token for a specific Page Access Token.
        """
        try:
            url = f"{self.base_graph_url}/{page_id}"
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
        Executes the official 3-phase Reel publishing flow for Facebook Pages.
        Waits for 'upload_complete' before triggering the 'finish' phase.
        """
        page_token = self.get_page_access_token(target_id)
        if not page_token:
            logger.error(f"[FB] Failed to obtain Page Access Token for Page ID: {target_id}")
            return False

        try:
            # ==========================================
            # PHASE 1: Initialize Upload Session
            # ==========================================
            logger.info(f"[FB] PHASE 1: Initializing session for Page {target_id}...")
            init_url = f"{self.base_graph_url}/{target_id}/video_reels"
            init_payload = {
                "upload_phase": "start",
                "access_token": page_token
            }
            init_res = requests.post(init_url, data=init_payload).json()

            video_id = init_res.get("video_id")
            if not video_id:
                logger.error(f"[FB] Initialization failed. Response: {init_res}")
                return False

            logger.info(f"[FB] Session initialized successfully. Video ID: {video_id}")

            # ==========================================
            # PHASE 2: Upload the Video (PULL Method via rupload)
            # ==========================================
            logger.info(f"[FB] PHASE 2: Requesting Meta to pull video from {video_url}...")
            upload_url = f"{self.base_rupload_url}/{video_id}"

            # Credentials and file_url MUST be passed in the headers
            upload_headers = {
                "Authorization": f"OAuth {page_token}",
                "file_url": video_url
            }

            upload_res = requests.post(upload_url, headers=upload_headers).json()

            if not upload_res.get("success"):
                logger.error(f"[FB] Pull request failed. Response: {upload_res}")
                return False

            logger.info(f"[FB] Video pull request accepted. Waiting for download to complete...")

            # ==========================================
            # PHASE 2.5: Polling for Upload Completion
            # ==========================================
            max_attempts = 15
            attempt = 1
            is_ready = False

            while attempt <= max_attempts:
                status_url = f"{self.base_graph_url}/{video_id}"
                status_params = {
                    "fields": "status",
                    "access_token": page_token
                }
                status_res = requests.get(status_url, params=status_params).json()

                logger.info(f"[FB] Polling Attempt {attempt}/{max_attempts} - Full Response: {status_res}")

                status_obj = status_res.get("status", {})
                current_state = status_obj.get("video_status")

                # The crucial fix: Trigger on 'upload_complete'
                if current_state == "upload_complete" or current_state == "ready":
                    is_ready = True
                    logger.info(f"✅ [FB] Meta confirms upload is complete. Proceeding to finish phase.")
                    break
                elif current_state == "error":
                    logger.error(f"❌ [FB] Meta reported processing error: {status_obj}")
                    return False

                logger.info(f"[FB] Current state is '{current_state}'. Waiting 15s...")
                time.sleep(15)
                attempt += 1

            if not is_ready:
                logger.error(f"[FB] Timeout reached. Video did not reach 'upload_complete' state.")
                return False

            # ==========================================
            # PHASE 3: Finalize Publication
            # ==========================================
            logger.info(f"[FB] PHASE 3: Finalizing publication to trigger processing for video_id: {video_id}...")
            finish_payload = {
                "upload_phase": "finish",
                "video_id": video_id,
                "video_state": "PUBLISHED",
                "description": description,
                "access_token": page_token
            }
            final_res = requests.post(init_url, data=finish_payload).json()

            if final_res.get("success"):
                logger.info(f"✅ [FB] Reel published successfully to Page {target_id}")
                return True
            else:
                logger.error(f"❌ [FB] Publication finalization failed: {final_res}")
                return False

        except Exception as e:
            logger.error(f"❌ [FB] Critical exception during publishing flow: {str(e)}")
            return False