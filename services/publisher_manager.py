# services/publisher_manager.py
import os
import logging
from database.session import SessionLocal
from database.models import ScheduledPost, SocialCredential
from storage.oracle_s3 import download_video

# 1. Imports for each platform
from publishers.youtube import upload_video
from publishers.tiktok import upload_video_to_tiktok  # Added TikTok!

logger = logging.getLogger("Publisher-Manager")


def process_single_post(post_id: int):
    """
    Orchestrates the full flow for a single post:
    DB Fetch -> Oracle Download -> Dynamic Platform Upload -> DB Update -> Clean-Up.
    """
    db = SessionLocal()
    local_video_path = None

    try:
        # 1. Retrieve the post from the database
        post = db.query(ScheduledPost).filter(ScheduledPost.id == post_id).first()
        if not post or post.status != 'pending':
            return

        # 2. Retrieve credentials DYNAMICALLY based on the post's platform
        creds = db.query(SocialCredential).filter(
            SocialCredential.client_id == post.client_id,
            SocialCredential.platform == post.platform  # Now supports any platform!
        ).first()

        if not creds:
            logger.error(f"No credentials found for Client {post.client_id} on {post.platform}")
            post.status = 'failed'  # Mark as failed if no credentials
            db.commit()
            return

        # 3. Directory management
        temp_dir = "temp_videos"
        os.makedirs(temp_dir, exist_ok=True)
        local_video_path = os.path.join(temp_dir, f"video_{post.id}.mp4")

        # 4. Download from Oracle Bucket (Same logic as YouTube)
        logger.info(f"Downloading {post.video_file_id} from Oracle Bucket...")
        download_success = download_video(post.video_file_id, local_video_path)

        if not download_success:
            logger.error(f"Download failed from bucket for Post {post_id}")
            return

        # 5. DYNAMIC UPLOAD (The bridge)
        logger.info(f"Triggering {post.platform.upper()} upload for Post {post_id}")
        upload_success = False

        if post.platform == 'youtube':
            upload_success = upload_video(
                video_path=local_video_path,
                title=post.title,
                description=post.description,
                token_data=creds.token_data
            )
        elif post.platform == 'tiktok':
            upload_success = upload_video_to_tiktok(
                video_path=local_video_path,
                title=post.title,
                token_data=creds.token_data
            )
        # Add Meta (FB/IG) logic here later

        # 6. Update Status
        if upload_success:
            post.status = 'completed'
            db.commit()
            logger.info(f"✅ Success: {post.platform.upper()} Post {post_id} completed.")

            # 7. CLEAN-UP
            if local_video_path and os.path.exists(local_video_path):
                os.remove(local_video_path)
                logger.info(f"🧹 Clean-up: Temporary file removed.")
        else:
            post.status = 'failed'
            db.commit()

    except Exception as e:
        db.rollback()
        logger.error(f"Critical error in Publisher-Manager: {str(e)}")
    finally:
        db.close()