"""
Configuration Schema and Validation

Implements Pydantic models for configuration validation
"""

from pydantic import BaseModel, Field, validator
from typing import Dict, Any, Optional, List
from enum import Enum
import logging

# Configure logging
logger = logging.getLogger(__name__)

class VideoFormat(str, Enum):
    TALKING_OBJECT = "talking_object"
    ABSURD_MOTIVATION = "absurd_motivation"
    NOTHING_HAPPENS = "nothing_happens"

class MotionStyle(str, Enum):
    CUTS_ZOOM_SHAKE = "cuts_zoom_shake"
    KEN_BURNS = "ken_burns"
    STATIC = "static"

class CaptionStyle(str, Enum):
    DYNAMIC = "dynamic"
    STATIC = "static"

class SchedulingWindow(BaseModel):
    start_hour: int = Field(12, ge=0, le=23)
    end_hour: int = Field(20, ge=0, le=23)

    @validator('end_hour')
    def end_after_start(cls, v, values):
        if 'start_hour' in values and v <= values['start_hour']:
            raise ValueError('end_hour must be after start_hour')
        return v

class SystemConfig(BaseModel):
    daily_budget: float = Field(3.0, gt=0, le=100)
    max_videos_per_day: int = Field(3, ge=1, le=10)
    default_language: str = Field("fr-FR", min_length=2, max_length=10)
    timezone: str = Field("Europe/Paris", min_length=3, max_length=50)
    scheduling_window: SchedulingWindow = SchedulingWindow()
    kill_switch_enabled: bool = False
    automation_enabled: bool = True
    openai_model: str = Field("gpt-4o", min_length=3, max_length=50)
    tts_model: str = Field("tts-1", min_length=3, max_length=50)
    image_model: str = Field("dall-e-3", min_length=3, max_length=50)
    default_duration_seconds: int = Field(7, ge=5, le=60)
    default_resolution: Dict[str, int] = Field({"width": 1080, "height": 1920})
    default_fps: int = Field(30, ge=24, le=60)
    music_lufs_target: float = Field(-28.0, ge=-40, le=-10)
    caption_style: CaptionStyle = CaptionStyle.DYNAMIC
    motion_style: MotionStyle = MotionStyle.CUTS_ZOOM_SHAKE

class FormatWeightConfig(BaseModel):
    talking_object: float = Field(1.0, ge=0.1, le=10.0)
    absurd_motivation: float = Field(1.0, ge=0.1, le=10.0)
    nothing_happens: float = Field(1.0, ge=0.1, le=10.0)

class EpisodeConfig(BaseModel):
    format: VideoFormat
    language: str = "fr-FR"
    min_duration: int = 6
    max_duration: int = 8
    caption_density: float = Field(0.8, ge=0.1, le=1.0)
    motion_intensity: float = Field(0.7, ge=0.1, le=1.0)

class ConfigManager:
    def __init__(self):
        self.config = SystemConfig()
        self.format_weights = FormatWeightConfig()
        self.logger = logging.getLogger(f"{__name__}.ConfigManager")

    def validate_config(self, config_data: Dict[str, Any]) -> SystemConfig:
        """Validate and return typed configuration"""
        try:
            return SystemConfig(**config_data)
        except Exception as e:
            self.logger.error(f"Configuration validation failed: {e}")
            raise

    def update_config(self, updates: Dict[str, Any]):
        """Update configuration with validated values"""
        try:
            validated = self.validate_config(updates)
            for key, value in validated.dict().items():
                setattr(self.config, key, value)
            self.logger.info("Configuration updated successfully")
        except Exception as e:
            self.logger.error(f"Failed to update configuration: {e}")
            raise

    def get_format_weights(self) -> FormatWeightConfig:
        """Get current format weights"""
        return self.format_weights

    def update_format_weights(self, weights: Dict[str, float]):
        """Update format weights with validation"""
        try:
            validated = FormatWeightConfig(**weights)
            self.format_weights = validated
            self.logger.info("Format weights updated successfully")
        except Exception as e:
            self.logger.error(f"Failed to update format weights: {e}")
            raise

    def get_episode_config(self, format: VideoFormat) -> EpisodeConfig:
        """Get episode configuration for specific format"""
        return EpisodeConfig(format=format)

# Global config instance
config = ConfigManager()
