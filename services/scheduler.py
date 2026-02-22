# services/scheduler.py
import logging
import os
from apscheduler.schedulers.background import BackgroundScheduler
from datetime import datetime

from database.session import SessionLocal
from database.models import ScheduledPost, SocialCredential
from storage.oracle_s3 import download_video
from storage.local_temp import cleanup_temp_file
from publishers import youtube, instagram, tiktok

logger = logging.getLogger("Scheduler")

# Get the absolute path of the project root
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
# New path inside your project: F:\Development\Pycharm\Projects\evo_omni_publisher_engine\temp_videos
TEMP_DIR = os.path.join(BASE_DIR, "temp_videos")


def process_pending_posts():
    """Job that runs every minute to check for and publish pending videos."""
    db = SessionLocal()
    try:
        # 1. Find pending posts whose time has come
        pending_posts = db.query(ScheduledPost).filter(
            ScheduledPost.status == "pending",
            ScheduledPost.scheduled_time <= datetime.utcnow()
        ).all()

        if not pending_posts:
            return

        # Ensure the local folder exists inside the project
        if not os.path.exists(TEMP_DIR):
            os.makedirs(TEMP_DIR, exist_ok=True)
            logger.info(f"Created local storage directory at: {TEMP_DIR}")

        for post in pending_posts:
            logger.info(f"Processing Post ID: {post.id} | Title: '{post.title}'")

            post.status = "processing"
            db.commit()

            # 2. Download video from Oracle Storage to the NEW local folder
            local_path = os.path.join(TEMP_DIR, f"video_{post.id}.mp4")
            if not download_video(post.video_file_id, local_path):
                post.status = "error"
                db.commit()
                continue

            # 3. Publish to requested platforms
            has_errors = False
            for platform in post.platforms:
                cred = db.query(SocialCredential).filter_by(
                    client_id=post.client_id, platform=platform
                ).first()

                tokens = cred.token_data if cred else {}

                if platform == "youtube":
                    if not youtube.upload_video(local_path, post.title, post.description, tokens):
                        has_errors = True
                elif platform == "tiktok":
                    if not tiktok.upload_tiktok(local_path, post.title, post.description, tokens):
                        has_errors = True
                # Add other platforms here...

            # 4. Cleanup and final status
            # NOTE: Comment out the line below if you want to see the file in PyCharm!
            # cleanup_temp_file(local_path)

            post.status = "error" if has_errors else "completed"
            db.commit()
            logger.info(f"Finished Post ID: {post.id} with status: {post.status}")

    except Exception as e:
        logger.error(f"Error in process_pending_posts: {e}")
    finally:
        db.close()


scheduler = BackgroundScheduler()
scheduler.add_job(process_pending_posts, 'interval', minutes=1)


def start_scheduler():
    scheduler.start()
    logger.info("Background engine started successfully.")


def stop_scheduler():
    scheduler.shutdown()
    logger.info("Background engine stopped.")