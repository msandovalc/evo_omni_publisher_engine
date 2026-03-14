# api/routes_publish.py
import logging
import shutil
import os
from fastapi import APIRouter, Depends, HTTPException, status, File, UploadFile, Form
from sqlalchemy import text
from sqlalchemy.orm import Session
from pydantic import BaseModel, Field
from typing import List, Optional
from datetime import datetime, timezone
from services.utils import get_smart_title

from database.session import get_db
from database.models import ScheduledPost, Client

# --- CRUCIAL: Importing your fixed storage service ---
from storage.oracle_s3 import upload_video

logger = logging.getLogger("Publish-API")

# Version Marker
ROUTE_VERSION = "2.5.2-DEBUG"

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


# --- 2. ROUTER DEFINITION ---
router = APIRouter(prefix="/api/v1/publish", tags=["Publishing Operations"])


# --- 3. ORIGINAL ENDPOINTS (Kept intact) ---
@router.post("/", response_model=PostResponse, status_code=status.HTTP_201_CREATED)
def schedule_new_post(post_data: PostCreate, db: Session = Depends(get_db)):
    client = db.query(Client).filter(Client.id == post_data.client_id).first()
    if not client: raise HTTPException(status_code=404, detail="Client not found")
    new_post = ScheduledPost(**post_data.dict(), status="pending")
    db.add(new_post);
    db.commit();
    db.refresh(new_post)
    return new_post


@router.get("/pending", response_model=List[PostResponse])
def get_pending_posts(db: Session = Depends(get_db)):
    return db.query(ScheduledPost).filter(ScheduledPost.status == "pending").all()


# --- 4. THE WEB-DIRECT METHOD (The Fix) ---
@router.post("/web-direct")
async def publish_web_direct(
        file: UploadFile = File(...),
        privacy: str = Form(...),
        caption: str = Form(""),
        scheduled_time: str = Form(...),
        db: Session = Depends(get_db)
):
    # HIGH VISIBILITY LOGS
    logger.info("XXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXX")
    logger.info(f"XXX INCOMING REQUEST: {file.filename} [VER: {ROUTE_VERSION}]")
    logger.info("XXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXX")

    try:

        try:
            # 1. Parse the ISO string sent by the frontend (e.g., '2026-03-14T03:43:00.000Z')
            # We replace 'Z' with '+00:00' to ensure compatibility with Python's fromisoformat
            parsed_aware_time = datetime.fromisoformat(scheduled_time.replace('Z', '+00:00'))

            # 2. Ensure it's in UTC and strip the timezone info (make it naive) for Postgres
            parsed_scheduled_time = parsed_aware_time.astimezone(timezone.utc).replace(tzinfo=None)
            logger.info(f"🕒 Scheduled time normalized to UTC: {parsed_scheduled_time}")

        except ValueError:
            # Fallback to current UTC time if parsing fails
            parsed_scheduled_time = datetime.now(timezone.utc).replace(tzinfo=None)
            logger.warning("⚠️ Date parsing failed, falling back to current UTC time")

        # Step 1: VPS Local Buffer
        temp_dir = "temp_media"
        os.makedirs(temp_dir, exist_ok=True)
        file_path = os.path.join(temp_dir, file.filename)

        with open(file_path, "wb") as buffer:
            shutil.copyfileobj(file.file, buffer)
        logger.info(f"💾 [1/3] VPS BUFFER SAVED: {file_path}")

        # Step 2: ORACLE SYNC (The Critical Part)
        logger.info(f"☁️ [2/3] STARTING OCI SYNC FOR {file.filename}...")
        success = upload_video(file_path, file.filename)

        if not success:
            logger.error("❌ [2/3] OCI SYNC FAILED. DB INSERT CANCELLED.")
            raise HTTPException(status_code=502, detail="Oracle Sync Failed")

        # Step 3: Database Registration
        logger.info("🗄️ [3/3] RECORDING TO POSTGRES...")

        # Extract smart title using the helper
        post_title = get_smart_title(caption)
        logger.info(f"✨ Smart Title generated: '{post_title}'")

        insert_query = text("""
            INSERT INTO scheduled_posts (
                client_id, video_file_id, title, description, platforms, scheduled_time, status
            )
            VALUES (
                1, :video_file_id, :title, :description, '["tiktok"]'::jsonb, :scheduled_time, 'pending'
            )
        """)

        db.execute(insert_query, {
            "video_file_id": file.filename,
            "title": post_title,  # Short & Clean for the Dashboard
            "description": caption,  # Full raw text for TikTok/Instagram
            "scheduled_time": parsed_scheduled_time
        })
        db.commit()

        logger.info(f"🚀 [FINISH] ALL STEPS DONE FOR {file.filename}")
        return {"status": "success", "message": "Video uploaded and scheduled."}

    except Exception as e:
        if 'db' in locals(): db.rollback()
        logger.error(f"🔥 FATAL ERROR: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))