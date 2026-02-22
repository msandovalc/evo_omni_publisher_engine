# api/routes_publish.py
import logging
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from pydantic import BaseModel, Field
from typing import List, Optional
from datetime import datetime

from database.session import get_db
from database.models import ScheduledPost, Client

logger = logging.getLogger("Publish-API")

# --- 1. PYDANTIC SCHEMAS (Data Validation) ---
class PostCreate(BaseModel):
    """Payload expected from the client to schedule a new video."""
    client_id: int = Field(..., description="ID of the client scheduling the post")
    video_file_id: str = Field(..., description="Path or Object Storage ID of the video")
    title: str = Field(..., max_length=150, description="Title of the social media post")
    description: Optional[str] = Field(default="", description="Caption or description")
    platforms: List[str] = Field(..., description="List of target platforms, e.g., ['youtube', 'tiktok']")
    scheduled_time: datetime = Field(..., description="UTC time to publish the video")

class PostResponse(BaseModel):
    """Response returned after successfully scheduling a post."""
    id: int
    client_id: int
    title: str
    platforms: List[str]
    scheduled_time: datetime
    status: str
    created_at: datetime

    class Config:
        from_attributes = True

# --- 2. FASTAPI ROUTER & ENDPOINTS ---
router = APIRouter(
    prefix="/api/v1/publish",
    tags=["Publishing Operations"]
)

@router.post("/", response_model=PostResponse, status_code=status.HTTP_201_CREATED)
def schedule_new_post(post_data: PostCreate, db: Session = Depends(get_db)):
    """Endpoint to schedule a new video publication."""
    logger.info(f"Received request to schedule post: '{post_data.title}' for client {post_data.client_id}")

    # Verify if the client exists in the database
    client = db.query(Client).filter(Client.id == post_data.client_id).first()
    if not client:
        logger.warning(f"Client ID {post_data.client_id} not found.")
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Client with ID {post_data.client_id} not found in the database."
        )

    # Create the new database record
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

    logger.info(f"Post {new_post.id} scheduled successfully for {new_post.scheduled_time}")
    return new_post

@router.get("/pending", response_model=List[PostResponse])
def get_pending_posts(db: Session = Depends(get_db)):
    """Retrieves all currently pending posts in the queue."""
    logger.info("Fetching all pending posts from the database.")
    pending_posts = db.query(ScheduledPost).filter(ScheduledPost.status == "pending").all()
    return pending_posts