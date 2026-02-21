# database/models.py
from sqlalchemy import Column, Integer, String, DateTime, ForeignKey, Text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import relationship
from datetime import datetime

from database.session import Base

class Client(Base):
    __tablename__ = "clients"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(150), nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)

    # Relationships to navigate in Python (e.g., client.credentials)
    credentials = relationship("SocialCredential", back_populates="client", cascade="all, delete")
    scheduled_posts = relationship("ScheduledPost", back_populates="client", cascade="all, delete")


class SocialCredential(Base):
    __tablename__ = "social_credentials"

    id = Column(Integer, primary_key=True, index=True)
    client_id = Column(Integer, ForeignKey("clients.id", ondelete="CASCADE"))
    platform = Column(String(50), nullable=False) # e.g., 'youtube', 'instagram', 'tiktok'
    token_data = Column(JSONB, nullable=False)    # Stores access_token, refresh_token, etc.
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    client = relationship("Client", back_populates="credentials")


class ScheduledPost(Base):
    __tablename__ = "scheduled_posts"

    id = Column(Integer, primary_key=True, index=True)
    client_id = Column(Integer, ForeignKey("clients.id", ondelete="CASCADE"))
    video_file_id = Column(String(255), nullable=False) # Path or Object Storage ID
    title = Column(String(150), nullable=False)
    description = Column(Text, nullable=True)
    platforms = Column(JSONB, nullable=False)           # e.g., '["youtube", "tiktok"]'
    scheduled_time = Column(DateTime, nullable=False)
    status = Column(String(20), default="pending", index=True) # pending, processing, completed, error
    created_at = Column(DateTime, default=datetime.utcnow)

    client = relationship("Client", back_populates="scheduled_posts")