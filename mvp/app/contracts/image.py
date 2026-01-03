"""
Image Generation Contract Models

Defines data contracts for image generation services
"""

from dataclasses import dataclass
from typing import Optional, Dict, Any
from datetime import datetime


@dataclass
class ImageGenerationRequest:
    """Request contract for image generation"""
    prompt: str
    model: str = "dall-e-3"
    size: str = "1792x1024"  # 16:9 aspect ratio suitable for cropping to 9:16
    quality: str = "standard"
    style: str = "vivid"
    user_id: Optional[str] = None
    request_id: str = ""
    schema_version: str = "1.0"


@dataclass
class ImageGenerationResponse:
    """Response contract from image generation service"""
    request: ImageGenerationRequest
    image_url: str
    image_data: Optional[bytes] = None  # For local storage
    revised_prompt: Optional[str] = None
    seed: Optional[int] = None
    cost_credits: int = 0
    model_used: str = ""
    size_actual: str = ""
    generated_at: datetime = None
    error: Optional[str] = None
    request_id: str = ""
    schema_version: str = "1.0"

    def __post_init__(self):
        if self.generated_at is None:
            self.generated_at = datetime.now()


@dataclass
class ImageFallbackRequest:
    """Request for fallback image generation"""
    text: str
    width: int = 1080
    height: int = 1920
    background_color: str = "linear-gradient(135deg, #667eea 0%, #764ba2 100%)"
    text_color: str = "white"
    font_size: int = 72
    style: str = "gradient"  # gradient, solid, pattern
    request_id: str = ""
    schema_version: str = "1.0"


@dataclass
class ImageFallbackResponse:
    """Response from fallback image generation"""
    request: ImageFallbackRequest
    image_data: bytes
    format: str = "PNG"
    width: int = 0
    height: int = 0
    generated_at: datetime = None
    error: Optional[str] = None
    request_id: str = ""
    schema_version: str = "1.0"

    def __post_init__(self):
        if self.generated_at is None:
            self.generated_at = datetime.now()
