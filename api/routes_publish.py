# api/routes_publish.py
import logging
import shutil
import os
import oci
from fastapi import APIRouter, Depends, HTTPException, status, File, UploadFile, Form
from sqlalchemy import text
from sqlalchemy.orm import Session
from pydantic import BaseModel, Field
from typing import List, Optional
from datetime import datetime
from dotenv import load_dotenv

from database.session import get_db
from database.models import ScheduledPost, Client

from storage.oracle_s3 import upload_video

# Load environment variables
load_dotenv()

logger = logging.getLogger("Publish-API")

# Oracle Cloud Configuration from .env
OCI_NAMESPACE = os.getenv("ORACLE_NAMESPACE")
OCI_BUCKET_NAME = os.getenv("ORACLE_BUCKET_NAME")


# --- 1. PYDANTIC SCHEMAS ---

class PostCreate(BaseModel):
    client_id: int = Field(..., description="ID of the client scheduling the post")
    video_file_id: str = Field(..., description="Path or Object Storage ID of the video")
    title: str = Field(..., max_length=150, description="Title of the social media post")
    description: Optional[str] = Field(default="", description="Caption or description")
    platforms: List[str] = Field(..., description="List of target platforms")
    scheduled_time: datetime = Field(..., description="UTC time to publish the video")


class PostResponse(BaseModel):
    id: int
    client_id: int
    title: str
    platforms: List[str]
    scheduled_time: datetime
    status: str
    created_at: datetime

    class Config:
        from_attributes = True


# --- 2. HELPER METHODS (Robust OCI Integration) ---

def upload_video_to_oracle(file_path: str, filename: str) -> bool:
    """
    Core method to upload files to Oracle Object Storage.
    Includes comprehensive logging and exception handling for OCI operations.
    """
    if not OCI_NAMESPACE or not OCI_BUCKET_NAME:
        logger.error("[OCI Storage] ❌ Oracle Namespace or Bucket Name missing in environment variables.")
        return False

    try:
        logger.info(f"[OCI Storage] ⬆️ Uploading '{filename}' to bucket '{OCI_BUCKET_NAME}'...")

        # Load OCI config from default location (~/.oci/config)
        config = oci.config.from_file()
        object_storage = oci.object_storage.ObjectStorageClient(config)

        # Upload process
        with open(file_path, "rb") as file_data:
            object_storage.put_object(
                namespace_name=OCI_NAMESPACE,
                bucket_name=OCI_BUCKET_NAME,
                object_name=filename,
                put_object_body=file_data
            )

        logger.info(f"[OCI Storage] ✅ Successfully uploaded '{filename}' to Oracle.")
        return True

    except oci.exceptions.ServiceError as se:
        logger.error(f"[OCI Storage] ❌ OCI Service Error: {se.message}")
        return False
    except Exception as e:
        logger.error(f"[OCI Storage] ❌ Unexpected Error during OCI upload: {str(e)}")
        return False


# --- 3. ROUTER DEFINITION ---

router = APIRouter(
    prefix="/api/v1/publish",
    tags=["Publishing Operations"]
)


# --- 4. ENDPOINTS ---

@router.post("/", response_model=PostResponse, status_code=status.HTTP_201_CREATED)
def schedule_new_post(post_data: PostCreate, db: Session = Depends(get_db)):
    """Schedules a new post (Original API Logic)."""
    client = db.query(Client).filter(Client.id == post_data.client_id).first()
    if not client:
        raise HTTPException(status_code=404, detail="Client not found")

    new_post = ScheduledPost(
        client_id=post_data.client_id,
        video_file_id=post_data.video_file_id,
        title=post_data.title,
        description=post_data.description,
        platforms=post_data.platforms,
        scheduled_time=post_data.scheduled_time,
        status="pending"
    )
    db.add(new_post)
    db.commit()
    db.refresh(new_post)
    return new_post


@router.get("/pending", response_model=List[PostResponse])
def get_pending_posts(db: Session = Depends(get_db)):
    """Retrieves all pending scheduled posts."""
    return db.query(ScheduledPost).filter(ScheduledPost.status == "pending").all()


# --- 4. WEB-DIRECT METHOD ---
@router.post("/web-direct")
async def publish_web_direct(
        file: UploadFile = File(...),
        privacy: str = Form(...),
        caption: str = Form(""),
        db: Session = Depends(get_db)
):
    """
    Direct Dashboard Publication:
    1. Saves video to VPS (temp_media).
    2. Uploads video to Oracle Bucket via storage/oracle_s3.py.
    3. Records entry in database to trigger the Listener.
    """
    try:
        # Step 1: Save to VPS local buffer
        temp_dir = "temp_media"
        os.makedirs(temp_dir, exist_ok=True)
        file_path = os.path.join(temp_dir, file.filename)

        with open(file_path, "wb") as buffer:
            shutil.copyfileobj(file.file, buffer)

        logger.info(f"[Web-Direct] 💾 Video buffered on VPS: {file_path}")

        # Step 2: SYNC WITH ORACLE (This was the missing piece!)
        # Uses your existing upload_video function from oracle_s3.py
        logger.info(f"[Web-Direct] ☁️ Uploading {file.filename} to Oracle Cloud Storage...")
        success = upload_video(file_path, file.filename)

        if not success:
            logger.error(f"[Web-Direct] ❌ Failed to upload {file.filename} to Oracle.")
            raise HTTPException(
                status_code=status.HTTP_502_BAD_GATEWAY,
                detail="Oracle Cloud storage synchronization failed."
            )

        # Step 3: Insert into Database
        insert_query = text("""
            INSERT INTO scheduled_posts (
                client_id, video_file_id, title, description, platforms, scheduled_time, status
            )
            VALUES (
                1, :video_file_id, :title, :description, '["Tiktok"]'::jsonb, NOW(), 'pending'
            )
        """)

        db.execute(insert_query, {
            "video_file_id": file.filename,
            "title": "Web Dashboard Upload",
            "description": caption
        })
        db.commit()

        logger.info(f"[Web-Direct] ✅ Process complete. Post queued for {file.filename}")
        return {"status": "success", "message": "Video synced to Oracle and scheduled."}

    except HTTPException as http_err:
        raise http_err
    except Exception as e:
        db.rollback()
        logger.error(f"[Web-Direct] 🔥 Fatal Error: {str(e)}")
        raise HTTPException(status_code=500, detail="Internal server error during processing.")