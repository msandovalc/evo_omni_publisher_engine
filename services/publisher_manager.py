# services/publisher_manager.py
import os
import logging
from database.session import SessionLocal
from database.models import ScheduledPost, SocialCredential
from storage.oracle_s3 import download_video

# Imports for each platform
from publishers.youtube import upload_video
from publishers.tiktok import upload_video_to_tiktok

logger = logging.getLogger("Publisher-Manager")


def process_single_post(post_id: int):
    """
    Orchestrates the full flow: DB Fetch -> Oracle Download -> Multi-Platform Upload -> Clean-Up.
    """
    db = SessionLocal()
    local_video_path = None

    try:
        # 1. Retrieve the post from the database
        post = db.query(ScheduledPost).filter(ScheduledPost.id == post_id).first()
        if not post or post.status != 'pending':
            return

        # 2. Directory management
        temp_dir = "temp_videos"
        os.makedirs(temp_dir, exist_ok=True)
        local_video_path = os.path.join(temp_dir, f"video_{post.id}.mp4")

        # 3. Download from Oracle Bucket
        logger.info(f"Downloading {post.video_file_id} from Oracle Bucket...")
        download_success = download_video(post.video_file_id, local_video_path)

        if not download_success:
            logger.error(f"Download failed from bucket for Post {post_id}")
            post.status = 'failed'
            db.commit()
            return

        # 4. MULTI-PLATFORM UPLOAD (Handling JSONB 'platforms')
        # We iterate through the list of platforms defined in the JSONB column
        overall_success = True

        for platform in post.platforms:  # 'platforms' is the JSONB list like ["tiktok", "youtube"]
            logger.info(f"Processing upload for platform: {platform.upper()}")

            # Retrieve credentials dynamically for THIS specific platform
            creds = db.query(SocialCredential).filter(
                SocialCredential.client_id == post.client_id,
                SocialCredential.platform == platform
            ).first()

            if not creds:
                logger.error(f"No credentials found for Client {post.client_id} on {platform}")
                overall_success = False
                continue

            # Route to the correct publisher
            platform_success = False
            if platform == 'youtube':
                platform_success = upload_video(
                    video_path=local_video_path,
                    title=post.title,
                    description=post.description,
                    token_data=creds.token_data
                )
            elif platform == 'tiktok':
                platform_success = upload_video_to_tiktok(
                    video_path=local_video_path,
                    title=post.title,
                    token_data=creds.token_data
                )

            if not platform_success:
                overall_success = False
                logger.error(f"Upload failed for {platform.upper()}")
            else:
                logger.info(f"✅ Success: {platform.upper()} upload completed for Post {post_id}.")

        # 5. Final Status Update
        post.status = 'completed' if overall_success else 'failed'
        db.commit()

        # 6. CLEAN-UP
        if local_video_path and os.path.exists(local_video_path):
            os.remove(local_video_path)
            logger.info(f"🧹 Clean-up: Temporary file removed from VPS.")

    except Exception as e:
        db.rollback()
        logger.error(f"Critical error in Publisher-Manager: {str(e)}")
    finally:
        db.close()