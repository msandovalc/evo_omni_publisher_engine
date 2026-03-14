# database/listener.py
import json
import select
import logging
import psycopg2
from psycopg2.extensions import ISOLATION_LEVEL_AUTOCOMMIT
from datetime import datetime, timezone

# 1. Import DB session and models for time validation
from database.session import SessionLocal
from database.models import ScheduledPost

# 2. Import the Manager (The Brain)
from services.publisher_manager import process_single_post

logger = logging.getLogger("DB-Listener")


class DBListener:
    def __init__(self, db_url: str):
        self.db_url = db_url
        self.conn = None
        self.channel = "post_updates"

    def connect(self):
        try:
            self.conn = psycopg2.connect(self.db_url)
            self.conn.set_isolation_level(ISOLATION_LEVEL_AUTOCOMMIT)
            cursor = self.conn.cursor()
            cursor.execute(f"LISTEN {self.channel};")
            logger.info(f"Connected to DB. Listening on channel: '{self.channel}'")
        except Exception as e:
            logger.error(f"Error connecting to database for LISTEN: {e}")
            raise

    def start_listening(self):
        """
        Wait for notifications and trigger the Manager logic conditionally.
        It evaluates if the post is for NOW or the FUTURE.
        """
        if not self.conn:
            self.connect()

        logger.info("Event-Driven Listener active.")

        try:
            while True:
                # Wait for up to 60 seconds for a notification
                if select.select([self.conn], [], [], 60) == ([], [], []):
                    logger.debug("Heartbeat: Listener waiting...")
                else:
                    self.conn.poll()
                    while self.conn.notifies:
                        notify = self.conn.notifies.pop(0)
                        try:
                            payload = json.loads(notify.payload)
                            post_id = payload.get("post_id")

                            # Check if the post is pending and has a valid ID
                            if payload.get("status") == "pending" and post_id:

                                # --- HYBRID ARCHITECTURE LOGIC: Time Validation ---
                                # Open a brief DB session to check the scheduled time
                                db = SessionLocal()
                                try:
                                    post = db.query(ScheduledPost).filter(ScheduledPost.id == post_id).first()

                                    if post:
                                        # Get current UTC time (naive, to match your DB schema)
                                        current_utc = datetime.now(timezone.utc).replace(tzinfo=None)

                                        # Compare if the scheduled time is in the past or exactly now
                                        if post.scheduled_time <= current_utc:
                                            # It's an immediate post. Publish right away!
                                            logger.info(f"⚡ [Real-Time] Post {post_id} is ready NOW. Executing...")
                                            process_single_post(post_id)
                                        else:
                                            # It's a future post. The Listener ignores it.
                                            # The APScheduler will pick it up when the time comes.
                                            logger.info(
                                                f"⏳ [Real-Time] Post {post_id} is scheduled for the FUTURE ({post.scheduled_time}). Ignoring event.")

                                except Exception as db_err:
                                    logger.error(f"Error validating post time: {db_err}")
                                finally:
                                    # Always close the session to prevent connection leaks
                                    db.close()
                                    # --------------------------------------------------

                        except Exception as e:
                            logger.error(f"Error processing notification: {e}")
        except Exception as e:
            logger.error(f"Listener loop crashed: {e}")
        finally:
            if self.conn:
                self.conn.close()