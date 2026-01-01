"""
Database Models for YouTube Shorts Factory

Implements SQLite schema with SQLAlchemy ORM
"""

from datetime import datetime
from enum import Enum
from typing import Optional, List
from sqlalchemy import Column, Integer, String, Float, Boolean, DateTime, Text, JSON, ForeignKey, Enum as SQLEnum
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import relationship

Base = declarative_base()

class VideoFormat(str, Enum):
    TALKING_OBJECT = "talking_object"
    ABSURD_MOTIVATION = "absurd_motivation"
    NOTHING_HAPPENS = "nothing_happens"

class VideoStatus(str, Enum):
    PENDING = "pending"
    GENERATING = "generating"
    RENDERING = "rendering"
    UPLOADING = "uploading"
    COMPLETED = "completed"
    FAILED = "failed"
    REJECTED = "rejected"

class Job(Base):
    """Video generation and upload jobs"""
    __tablename__ = "jobs"

    id = Column(String(36), primary_key=True, index=True)
    format = Column(SQLEnum(VideoFormat), nullable=False)
    status = Column(SQLEnum(VideoStatus), default=VideoStatus.PENDING)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Generation metadata
    episode_data = Column(JSON, nullable=True)
    generation_cost = Column(Float, default=0.0)
    render_cost = Column(Float, default=0.0)

    # YouTube metadata
    youtube_id = Column(String(50), nullable=True)
    scheduled_publish_time = Column(DateTime, nullable=True)
    actual_publish_time = Column(DateTime, nullable=True)
    privacy_status = Column(String(20), default="private")

    # Error handling
    error_message = Column(Text, nullable=True)
    retry_count = Column(Integer, default=0)

    # Relationships
    metrics = relationship("VideoMetric", back_populates="job", cascade="all, delete-orphan")

class VideoMetric(Base):
    """Performance metrics for uploaded videos"""
    __tablename__ = "video_metrics"

    id = Column(Integer, primary_key=True)
    job_id = Column(String(36), ForeignKey("jobs.id"), nullable=False)
    window = Column(String(20), nullable=False)  # "24h", "72h", etc.
    timestamp = Column(DateTime, default=datetime.utcnow)

    views = Column(Integer, default=0)
    likes = Column(Integer, default=0)
    comments = Column(Integer, default=0)
    avg_view_duration = Column(Float, default=0.0)  # in seconds
    avg_view_percentage = Column(Float, default=0.0)  # 0-100
    subscribers_gained = Column(Integer, default=0)

    job = relationship("Job", back_populates="metrics")

class Config(Base):
    """System configuration"""
    __tablename__ = "config"

    key = Column(String(50), primary_key=True)
    value = Column(JSON, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

class FormatWeight(Base):
    """Format performance weights for optimization"""
    __tablename__ = "format_weights"

    format = Column(SQLEnum(VideoFormat), primary_key=True)
    weight = Column(Float, default=1.0)
    last_updated = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    reason = Column(Text, nullable=True)

class CostTracking(Base):
    """Daily cost tracking"""
    __tablename__ = "cost_tracking"

    date = Column(DateTime, primary_key=True)
    openai_cost = Column(Float, default=0.0)
    total_cost = Column(Float, default=0.0)
    video_count = Column(Integer, default=0)
