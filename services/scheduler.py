# services/scheduler.py
import logging
from apscheduler.schedulers.background import BackgroundScheduler
from datetime import datetime, timezone

from database.session import SessionLocal
from database.models import ScheduledPost
from services.publisher_manager import process_single_post

logger = logging.getLogger("Scheduler")


def process_pending_posts():
    """Job that runs every minute to check for and publish pending videos."""
    db = SessionLocal()
    try:
        # ✨ 1. Fetch posts where the scheduled_time has passed and are still pending
        # FIX: Replaced deprecated utcnow() with timezone-aware UTC datetime
        current_utc_time = datetime.now(timezone.utc)

        pending_posts = db.query(ScheduledPost).filter(
            ScheduledPost.status == "pending",
            ScheduledPost.scheduled_time <= current_utc_time
        ).all()

        if not pending_posts:
            return

        for post in pending_posts:
            logger.info(f"⏰ Time reached for Post ID: {post.id}. Delegating to Manager...")
            # Switch status to 'processing' to avoid duplicate executions in the next cycle
            post.status = "processing"
            db.commit()

            # ✨ 2. Delegate ALL the heavy lifting to the Manager (DRY Principle applied)
            process_single_post(post.id)

    except Exception as e:
        logger.error(f"Error in process_pending_posts: {e}")
    finally:
        db.close()


scheduler = BackgroundScheduler()
scheduler.add_job(process_pending_posts, 'interval', minutes=1)


def start_scheduler():
    scheduler.start()
    logger.info("⏰ Background engine started successfully.")


def stop_scheduler():
    scheduler.shutdown()
    logger.info("⏰ Background engine stopped.")