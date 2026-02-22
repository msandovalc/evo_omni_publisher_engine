# database/listener.py
import json
import select
import logging
import psycopg2
from psycopg2.extensions import ISOLATION_LEVEL_AUTOCOMMIT

# 1. Import the Manager (The Brain)
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
        Wait for notifications and trigger the Manager logic.
        """
        if not self.conn:
            self.connect()

        logger.info("Event-Driven Listener active.")

        try:
            while True:
                if select.select([self.conn], [], [], 60) == ([], [], []):
                    logger.debug("Heartbeat: Listener waiting...")
                else:
                    self.conn.poll()
                    while self.conn.notifies:
                        notify = self.conn.notifies.pop(0)
                        try:
                            payload = json.loads(notify.payload)

                            # 2. Call the Manager to do the heavy lifting
                            if payload.get("status") == "pending":
                                process_single_post(payload.get("post_id"))

                        except Exception as e:
                            logger.error(f"Error processing notification: {e}")
        except Exception as e:
            logger.error(f"Listener loop crashed: {e}")
        finally:
            if self.conn:
                self.conn.close()