#!/usr/bin/env python3
"""
Database Initialization Script

Sets up SQLite database with required tables and initial data
"""

import os
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from app.db.models import Base, FormatWeight, Config, VideoFormat
from datetime import datetime
import logging

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def init_database():
    """Initialize database with schema and default data"""
    db_path = os.path.join("data", "youtube_shorts.db")
    os.makedirs(os.path.dirname(db_path), exist_ok=True)

    logger.info(f"Initializing database at {db_path}")

    # Create engine and tables
    engine = create_engine(f"sqlite:///{db_path}")
    Base.metadata.create_all(engine)

    # Create session
    Session = sessionmaker(bind=engine)
    session = Session()

    # Initialize format weights
    init_format_weights(session)

    # Initialize system config
    init_system_config(session)

    session.commit()
    logger.info("Database initialization complete")

def init_format_weights(session):
    """Initialize format weights with equal distribution"""
    formats = [
        FormatWeight(format=VideoFormat.TALKING_OBJECT, weight=1.0, reason="Initial setup"),
        FormatWeight(format=VideoFormat.ABSURD_MOTIVATION, weight=1.0, reason="Initial setup"),
        FormatWeight(format=VideoFormat.NOTHING_HAPPENS, weight=1.0, reason="Initial setup"),
    ]

    for fmt in formats:
        existing = session.query(FormatWeight).filter_by(format=fmt.format).first()
        if not existing:
            session.add(fmt)
            logger.info(f"Added format weight for {fmt.format}")

def init_system_config(session):
    """Initialize system configuration with defaults"""
    default_config = {
        "daily_budget": {"value": 3.0, "currency": "EUR"},
        "max_videos_per_day": 3,
        "default_language": "fr-FR",
        "timezone": "Europe/Paris",
        "scheduling_window": {"start_hour": 12, "end_hour": 20},
        "kill_switch_enabled": False,
        "automation_enabled": True,
        "openai_model": "gpt-4o",
        "tts_model": "tts-1",
        "image_model": "dall-e-3",
        "default_duration_seconds": 7,
        "default_resolution": {"width": 1080, "height": 1920},
        "default_fps": 30,
        "music_lufs_target": -28,
        "caption_style": "dynamic",
        "motion_style": "cuts_zoom_shake"
    }

    for key, value in default_config.items():
        existing = session.query(Config).filter_by(key=key).first()
        if not existing:
            config_item = Config(key=key, value=value)
            session.add(config_item)
            logger.info(f"Added config: {key}")
        else:
            existing.value = value
            existing.updated_at = datetime.utcnow()
            logger.info(f"Updated config: {key}")

if __name__ == "__main__":
    init_database()
