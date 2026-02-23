# services/publisher_manager.py
import os
import logging
from database.session import SessionLocal
from database.models import ScheduledPost, SocialCredential
from storage.oracle_s3 import download_video

# Existing Publishers
from publishers.youtube import upload_video
from publishers.tiktok import upload_video_to_tiktok
from publishers.instagram import InstagramPublisher

logger = logging.getLogger("Publisher-Manager")

# Update this with your actual duckdns domain
BASE_PUBLIC_URL = "https://evo-omni-engine.duckdns.org/temp"


def process_single_post(post_id: int):
    """
    Orchestrates the full flow: DB Fetch -> Oracle Download -> Multi-Platform Upload -> Clean-Up.
    Now passes DB session and Client ID to enable token refreshing.
    """
    db = SessionLocal()
    local_video_path = None

    try:
        # 1. Retrieve the post from the database
        post = db.query(ScheduledPost).filter(ScheduledPost.id == post_id).first()
        if not post or post.status != 'pending':
            return

        logger.info(f"[Manager] Starting orchestration for Post {post_id} (Client {post.client_id})")

        # 2. Directory management (Using the mounted /temp_media for Meta compatibility)
        temp_dir = "temp_media"
        os.makedirs(temp_dir, exist_ok=True)
        filename = f"video_job_{post.id}.mp4"
        local_video_path = os.path.join(temp_dir, filename)

        # 3. Download from Oracle Bucket
        logger.info(f"[Manager] Downloading {post.video_file_id} from Oracle...")
        if not download_video(post.video_file_id, local_video_path):
            logger.error(f"[Manager] Failed to fetch video from storage. Marking post as failed.")
            post.status = 'failed'
            db.commit()
            return

        overall_success = True

        # 4. Iterate through requested platforms
        for platform in post.platforms:
            logger.info(f"[Manager] Routing to platform: {platform.upper()}")

            # Fetch credentials for this specific client and platform
            creds = db.query(SocialCredential).filter_by(
                client_id=post.client_id,
                platform=platform
            ).first()

            if not creds:
                logger.error(f"[Manager] No credentials found for {platform} (Client {post.client_id})")
                overall_success = False
                continue

            platform_success = False
            try:
                if platform == 'youtube':
                    # YouTube handles its own refresh inside its publisher
                    platform_success = upload_video(
                        video_path=local_video_path,
                        title=post.title,
                        description=post.description,
                        token_data=creds.token_data
                    )

                elif platform == 'tiktok':
                    # We pass 'db' and 'post.client_id' to enable TikTok auto-refresh
                    platform_success = upload_video_to_tiktok(
                        video_path=local_video_path,
                        title=post.title,
                        token_data=creds.token_data,
                        client_id=post.client_id,
                        db=db
                    )

                elif platform == 'instagram' or platform == 'facebook':
                    # Meta (IG/FB) requires a public URL to PULL the video
                    public_video_url = f"{BASE_PUBLIC_URL}/{filename}"

                    ig_publisher = InstagramPublisher(
                        access_token=creds.token_data.get("access_token"),
                        instagram_account_id=creds.token_data.get("instagram_account_id")
                    )
                    platform_success = ig_publisher.publish_reel(public_video_url, post.description)

            except Exception as platform_err:
                logger.error(f"[Manager] Error during {platform.upper()} execution: {platform_err}")
                platform_success = False

            if not platform_success:
                overall_success = False

        # 5. Final Status Update
        post.status = 'completed' if overall_success else 'failed'
        db.commit()
        logger.info(f"[Manager] Orchestration finished. Status: {post.status}")

    except Exception as e:
        db.rollback()
        logger.error(f"[Manager] Critical error in orchestration: {str(e)}")
    finally:
        # 6. CLEAN-UP
        # Delete the local file after all platforms are done
        if local_video_path and os.path.exists(local_video_path):
            os.remove(local_video_path)
            logger.info(f"🧹 Clean-up: Local video file removed from VPS.")
        db.close()