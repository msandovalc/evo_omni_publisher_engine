import requests
import time
import logging

logger = logging.getLogger("EVO-Instagram")


class InstagramPublisher:
    def __init__(self, access_token: str, instagram_account_id: str):
        self.access_token = access_token
        self.ig_id = instagram_account_id
        self.version = "v22.0"  # Updated version as per your script
        self.base_url = f"https://graph.facebook.com/{self.version}"

    def publish_reel(self, video_url: str, caption: str) -> bool:
        """
        Orchestrates the Meta Reel publication flow.
        """
        try:
            logger.info(f"[Instagram] Starting Reel upload for ID: {self.ig_id}")

            # 1. Create Media Container
            container_id = self._create_container(video_url, caption)
            if not container_id:
                return False

            # 2. Poll Status (Wait for Meta to download the video from our VPS)
            if self._wait_for_processing(container_id):
                # 3. Final Publish
                return self._publish_container(container_id)

            return False
        except Exception as e:
            logger.error(f"[Instagram] Critical failure in publish_reel: {e}")
            return False

    def _create_container(self, video_url: str, caption: str):
        url = f"{self.base_url}/{self.ig_id}/media"
        payload = {
            "media_type": "REELS",
            "video_url": video_url,
            "caption": caption,
            "access_token": self.access_token
        }
        try:
            response = requests.post(url, data=payload, timeout=30)
            data = response.json()
            if response.status_code == 200:
                logger.info(f"[Instagram] Container created: {data['id']}")
                return data['id']
            logger.error(f"[Instagram] Container creation failed: {data}")
            return None
        except Exception as e:
            logger.error(f"[Instagram] API Connection error (Container): {e}")
            return None

    def _wait_for_processing(self, container_id: str, retries=20):
        url = f"{self.base_url}/{container_id}"
        params = {"fields": "status_code", "access_token": self.access_token}

        for i in range(retries):
            try:
                res = requests.get(url, params=params).json()
                status = res.get("status_code")
                logger.info(f"[Instagram] Processing status: {status} (Attempt {i + 1})")

                if status == "FINISHED":
                    return True
                if status == "ERROR":
                    logger.error(f"[Instagram] Meta processing error: {res}")
                    return False
                time.sleep(20)  # Wait for Meta to pull the file
            except Exception as e:
                logger.error(f"[Instagram] Polling error: {e}")
        return False

    def _publish_container(self, container_id: str):
        url = f"{self.base_url}/{self.ig_id}/media_publish"
        payload = {"creation_id": container_id, "access_token": self.access_token}
        try:
            res = requests.post(url, data=payload).json()
            if "id" in res:
                logger.info(f"✅ [Instagram] Reel published successfully! ID: {res['id']}")
                return True
            logger.error(f"[Instagram] Final publish failed: {res}")
            return False
        except Exception as e:
            logger.error(f"[Instagram] API Connection error (Publish): {e}")
            return False