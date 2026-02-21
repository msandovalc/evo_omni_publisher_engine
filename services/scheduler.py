# services/scheduler.py
from apscheduler.schedulers.background import BackgroundScheduler
from datetime import datetime
import os

from database.session import SessionLocal
from database.models import ScheduledPost, SocialCredential
from storage.oracle_s3 import download_video
from storage.local_temp import cleanup_temp_file
from publishers import youtube, instagram, tiktok

TEMP_DIR = "/tmp/evo_videos"


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

        os.makedirs(TEMP_DIR, exist_ok=True)

        for post in pending_posts:
            print(f"\n>>> [Engine] Processing Post ID: {post.id} | Title: '{post.title}'")

            # Mark as processing to avoid duplicate runs
            post.status = "processing"
            db.commit()

            # 2. Download video from Oracle Storage
            local_path = os.path.join(TEMP_DIR, f"video_{post.id}.mp4")
            if not download_video(post.video_file_id, local_path):
                post.status = "error"
                db.commit()
                continue

            # 3. Publish to requested platforms
            has_errors = False
            for platform in post.platforms:
                # Get tokens for this specific client and platform
                cred = db.query(SocialCredential).filter_by(
                    client_id=post.client_id, platform=platform
                ).first()

                tokens = cred.token_data if cred else {}

                if platform == "youtube":
                    if not youtube.upload_video(local_path, post.title, post.description, tokens):
                        has_errors = True
                elif platform == "instagram":
                    if not instagram.upload_reels(local_path, post.title, post.description, tokens):
                        has_errors = True
                elif platform == "tiktok":
                    if not tiktok.upload_tiktok(local_path, post.title, post.description, tokens):
                        has_errors = True

            # 4. Cleanup and final status
            cleanup_temp_file(local_path)
            post.status = "error" if has_errors else "completed"
            db.commit()
            print(f"<<< [Engine] Finished Post ID: {post.id} with status: {post.status}")

    finally:
        db.close()


# Scheduler instance
scheduler = BackgroundScheduler()
scheduler.add_job(process_pending_posts, 'interval', minutes=1)


def start_scheduler():
    scheduler.start()
    print("[Scheduler] Background engine started successfully.")


def stop_scheduler():
    scheduler.shutdown()
    print("[Scheduler] Background engine stopped.")