# services/publisher_manager.py
import os
import logging
from database.session import SessionLocal
from database.models import ScheduledPost, SocialCredential
from storage.oracle_s3 import download_video
from publishers.youtube import upload_video

logger = logging.getLogger("Publisher-Manager")


def process_single_post(post_id: int):
    """
    Orchestrates the full flow for a single post:
    DB Fetch -> Oracle Download -> YouTube Upload -> DB Update -> Clean-Up.
    """
    db = SessionLocal()
    local_video_path = None  # Initialize to track for cleanup

    try:
        # 1. Retrieve the post from the database
        post = db.query(ScheduledPost).filter(ScheduledPost.id == post_id).first()
        if not post or post.status != 'pending':
            return

        # 2. Retrieve credentials
        creds = db.query(SocialCredential).filter(
            SocialCredential.client_id == post.client_id,
            SocialCredential.platform == 'youtube'
        ).first()

        if not creds:
            logger.error(f"No credentials found for Client {post.client_id}")
            return

        # 3. Directory management
        temp_dir = "temp_videos"
        os.makedirs(temp_dir, exist_ok=True)
        local_video_path = os.path.join(temp_dir, f"video_{post.id}.mp4")

        # 4. Download from Oracle
        logger.info(f"Downloading {post.video_file_id} from Oracle...")
        download_success = download_video(post.video_file_id, local_video_path)

        if not download_success:
            logger.error(f"Download failed for Post {post_id}")
            return

        # 5. Upload (Simulated/Real)
        logger.info(f"Triggering upload for Post {post_id}")
        upload_success = upload_video(
            video_path=local_video_path,
            title=post.title,
            description=post.description,
            token_data=creds.token_data
        )

        # 6. Update Status
        if upload_success:
            post.status = 'completed'
            db.commit()
            logger.info(f"✅ Success: Post {post_id} completed.")

            # 7. CLEAN-UP: Remove the temporary file
            # if local_video_path and os.path.exists(local_video_path):
            #     try:
            #         os.remove(local_video_path)
            #         logger.info(f"🧹 Clean-up: Temporary file removed: {local_video_path}")
            #     except Exception as clean_e:
            #         logger.warning(f"⚠️ Clean-up failed for {local_video_path}: {clean_e}")
        else:
            post.status = 'failed'
            db.commit()

    except Exception as e:
        db.rollback()
        logger.error(f"Critical error in Publisher-Manager: {str(e)}")
    finally:
        db.close()