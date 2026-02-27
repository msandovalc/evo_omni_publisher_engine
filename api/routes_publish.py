# api/routes_publish.py
import logging
import shutil
import os
from fastapi import APIRouter, Depends, HTTPException, status, File, UploadFile, Form
from sqlalchemy import text
from sqlalchemy.orm import Session
from pydantic import BaseModel, Field
from typing import List, Optional
from datetime import datetime

from database.session import get_db
from database.models import ScheduledPost, Client
# --- CRUCIAL: Importing your fixed storage service ---
from storage.oracle_s3 import upload_video

logger = logging.getLogger("Publish-API")


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
        db: Session = Depends(get_db)
):
    """
    Direct Dashboard Publication Logic:
    1. Buffered save to VPS local disk.
    2. Real-time sync to Oracle Cloud Storage.
    3. Database record creation to trigger Publisher-Manager.
    """
    try:
        logger.info(f"📥 [Web-Direct] Processing upload for: {file.filename}")

        # Step 1: VPS Local Buffer
        temp_dir = "temp_media"
        os.makedirs(temp_dir, exist_ok=True)
        file_path = os.path.join(temp_dir, file.filename)

        with open(file_path, "wb") as buffer:
            shutil.copyfileobj(file.file, buffer)
        logger.info(f"💾 [Web-Direct] Video temporarily stored on VPS: {file_path}")

        # Step 2: ORACLE CLOUD SYNC
        # This is what was missing in the previous execution!
        logger.info(f"☁️ [Web-Direct] Syncing '{file.filename}' to Oracle Bucket...")
        upload_success = upload_video(file_path, file.filename)

        if not upload_success:
            logger.error(f"❌ [Web-Direct] Oracle upload failed for '{file.filename}'")
            raise HTTPException(
                status_code=status.HTTP_502_BAD_GATEWAY,
                detail="Cloud Sync Error: Video could not be sent to Oracle."
            )

        # Step 3: Database Trigger
        logger.info(f"🗄️ [Web-Direct] Recording entry in scheduled_posts for Manager detection.")
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
            "title": "Audit Web Publication",
            "description": caption
        })
        db.commit()

        logger.info(f"🚀 [Web-Direct] All systems go. Post {file.filename} is now live in Oracle and queued in DB.")
        return {"status": "success", "message": "Video uploaded to Oracle and scheduled successfully."}

    except HTTPException as http_err:
        raise http_err
    except Exception as e:
        if 'db' in locals(): db.rollback()
        logger.error(f"🔥 [Web-Direct] Critical Failure: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Internal Server Error: {str(e)}")