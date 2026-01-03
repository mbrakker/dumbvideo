"""
DALL·E Image Generation Service

Handles external image generation via OpenAI DALL·E API
"""

import os
import time
import uuid
import requests
from typing import Optional, Dict, Any
from datetime import datetime
from app.utils.logging import get_logger
from app.contracts.image import (
    ImageGenerationRequest,
    ImageGenerationResponse,
    ImageFallbackRequest,
    ImageFallbackResponse
)
import tempfile
import hashlib

logger = get_logger(__name__)

class ImageGenerationError(Exception):
    """Custom exception for image generation failures"""
    pass

class ImageService:
    """
    DALL·E Image Generation Service

    Responsible for:
    - Calling OpenAI DALL·E API
    - Downloading generated images
    - Fallback image generation
    - Cost tracking
    """

    def __init__(self, api_key: Optional[str] = None):
        self.logger = get_logger(f"{__name__}.ImageService")

        self.api_key = api_key or os.getenv("OPENAI_API_KEY")
        if not self.api_key:
            self.logger.warning("OpenAI API key not configured - running in fallback mode")
            self.api_key = None

        # Service configuration
        self.model = "dall-e-3"
        self.max_retries = 3
        self.retry_delay = 2
        self.request_timeout = 120  # seconds

        # Cost tracking (credits per image)
        self.cost_credits = {
            "dall-e-2": 16,
            "dall-e-3": 85
        }

        self.logger.info("Image service initialized",
                       model=self.model,
                       max_retries=self.max_retries)

    def generate_image(self, request: ImageGenerationRequest) -> ImageGenerationResponse:
        """
        Generate image using DALL·E API

        Args:
            request: Image generation request contract

        Returns:
            Image generation response contract
        """
        start_time = time.time()
        request_id = request.request_id or str(uuid.uuid4())

        try:
            self.logger.info("Starting image generation",
                           request_id=request_id,
                           model=request.model)

            # Validate prompt
            if not self._validate_prompt(request.prompt):
                raise ImageGenerationError("Invalid prompt content")

            # Call DALL·E API with retry logic
            api_response = None
            for attempt in range(self.max_retries):
                try:
                    api_response = self._call_dalle_api(request, request_id)
                    break
                except Exception as e:
                    if attempt < self.max_retries - 1:
                        self.logger.warning("DALL·E API attempt failed, retrying",
                                         attempt=attempt + 1,
                                         error=str(e))
                        time.sleep(self.retry_delay)
                    else:
                        raise

            # Download image data
            image_data = self._download_image(api_response['data'][0]['url'])

            # Calculate cost
            cost = self.cost_credits.get(request.model, 85)

            response = ImageGenerationResponse(
                request=request,
                image_url=api_response['data'][0]['url'],
                image_data=image_data,
                revised_prompt=api_response.get('data', [{}])[0].get('revised_prompt'),
                seed=None,  # DALL·E doesn't provide seeds
                cost_credits=cost,
                model_used=request.model,
                size_actual=request.size,
                request_id=request_id
            )

            generation_time = time.time() - start_time
            self.logger.info("Image generation completed",
                           request_id=request_id,
                           duration=generation_time,
                           cost_credits=cost,
                           image_url=response.image_url)

            return response

        except Exception as e:
            self.logger.error("Image generation failed",
                            request_id=request_id,
                            error=str(e))

            return ImageGenerationResponse(
                request=request,
                image_url="",
                error=str(e),
                request_id=request_id
            )

    def generate_fallback_image(self, request: ImageFallbackRequest) -> ImageFallbackResponse:
        """
        Generate fallback image when DALL·E fails

        Args:
            request: Fallback request contract

        Returns:
            Fallback response contract
        """
        start_time = time.time()
        request_id = request.request_id or str(uuid.uuid4())

        try:
            self.logger.info("Generating fallback image",
                           request_id=request_id,
                           style=request.style)

            # Generate fallback image using PIL
            image_data = self._generate_text_image(
                text=request.text,
                width=request.width,
                height=request.height,
                bg_color=request.background_color,
                text_color=request.text_color,
                font_size=request.font_size,
                style=request.style
            )

            response = ImageFallbackResponse(
                request=request,
                image_data=image_data,
                format="PNG",
                width=request.width,
                height=request.height,
                request_id=request_id
            )

            generation_time = time.time() - start_time
            self.logger.info("Fallback image generated",
                           request_id=request_id,
                           duration=generation_time)

            return response

        except Exception as e:
            self.logger.error("Fallback image generation failed",
                            request_id=request_id,
                            error=str(e))

            return ImageFallbackResponse(
                request=request,
                image_data=b"",
                error=str(e),
                request_id=request_id
            )

    def _call_dalle_api(self, request: ImageGenerationRequest, request_id: str) -> Dict:
        """Make the actual DALL·E API call"""
        import openai
        client = openai.OpenAI(api_key=self.api_key)

        try:
            response = client.images.generate(
                model=request.model,
                prompt=self._sanitize_prompt(request.prompt),
                size=request.size,
                quality=request.quality,
                style=request.style,
                n=1,
                user=request_id  # For tracking
            )

            # Convert to dict for our processing
            return {
                'data': [{
                    'url': response.data[0].url,
                    'revised_prompt': getattr(response.data[0], 'revised_prompt', None)
                }]
            }

        except Exception as e:
            self.logger.error("DALL·E API call failed",
                            request_id=request_id,
                            error=str(e))
            raise ImageGenerationError(f"DALL·E API error: {str(e)}")

    def _download_image(self, image_url: str) -> bytes:
        """Download image from URL"""
        try:
            response = requests.get(image_url, timeout=30)
            response.raise_for_status()

            self.logger.debug("Downloaded image",
                            size=len(response.content),
                            url=image_url[:100] + "...")

            return response.content

        except Exception as e:
            self.logger.error("Image download failed", error=str(e))
            raise ImageGenerationError(f"Download failed: {str(e)}")

    def _validate_prompt(self, prompt: str) -> bool:
        """Basic prompt validation"""
        if not prompt or len(prompt.strip()) == 0:
            return False
        if len(prompt) > 4000:  # DALL·E limit
            return False
        # Add more validation as needed
        return True

    def _sanitize_prompt(self, prompt: str) -> str:
        """Sanitize prompt for DALL·E"""
        # Remove or replace potentially problematic content
        return prompt.strip()

    def _generate_text_image(self, text: str, width: int, height: int,
                           bg_color: str, text_color: str, font_size: int,
                           style: str) -> bytes:
        """Generate a simple text-based fallback image"""
        try:
            from PIL import Image, ImageDraw, ImageFont
            import io

            # Create image
            img = Image.new('RGBA', (width, height), (30, 30, 30, 255))
            draw = ImageDraw.Draw(img)

            # Handle different background styles
            if style == "gradient":
                self._apply_gradient_background(img, width, height)
            elif style == "solid":
                img.paste(self._parse_color(bg_color), (0, 0, width, height))
            elif style == "pattern":
                self._apply_pattern_background(img, width, height)

            # Try to load font, fallback to default
            try:
                # Try different possible font paths
                font_paths = [
                    "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
                    "/System/Library/Fonts/Arial.ttf",
                    "/Library/Fonts/Arial.ttf",
                    "arial.ttf"
                ]
                font = None
                for path in font_paths:
                    try:
                        if os.path.exists(path):
                            font = ImageFont.truetype(path, font_size)
                            break
                    except:
                        continue

                if font is None:
                    font = ImageFont.load_default()

            except Exception:
                font = ImageFont.load_default()

            # Text wrapping and positioning
            lines = self._wrap_text(text.upper(), font, width - 100)
            y_pos = (height - len(lines) * font_size) // 2

            for line in lines:
                bbox = draw.textbbox((0, 0), line, font=font)
                line_width = bbox[2] - bbox[0]
                x_pos = (width - line_width) // 2

                # Add text stroke/shadow
                shadow_offset = 3
                draw.text((x_pos + shadow_offset, y_pos + shadow_offset),
                         line, fill="black", font=font)
                draw.text((x_pos, y_pos), line, fill=self._parse_color(text_color), font=font)
                y_pos += font_size + 10

            # Save to bytes
            buffer = io.BytesIO()
            img.save(buffer, format='PNG')
            return buffer.getvalue()

        except Exception as e:
            self.logger.error("Text image generation failed", error=str(e))
            raise ImageGenerationError(f"Text image generation failed: {str(e)}")

    def _apply_gradient_background(self, img, width: int, height: int):
        """Apply a gradient background"""
        from PIL import ImageDraw

        draw = ImageDraw.Draw(img)
        for y in range(height):
            # Simple purple to blue gradient
            r = int(102 + (26 * y / height))
            g = int(102 + (6 * y / height))
            b = int(234 - (48 * y / height))
            draw.line([(0, y), (width, y)], fill=(r, g, b))

    def _apply_pattern_background(self, img, width: int, height: int):
        """Apply a pattern background"""
        from PIL import ImageDraw

        draw = ImageDraw.Draw(img)
        # Simple geometric pattern
        for x in range(0, width, 50):
            for y in range(0, height, 50):
                draw.rectangle([x, y, x+25, y+25], fill="gray20", outline="gray10")

    def _parse_color(self, color_str: str):
        """Parse color string (simple implementation)"""
        color_map = {
            "white": (255, 255, 255),
            "black": (0, 0, 0),
            "gray": (128, 128, 128),
            "red": (255, 0, 0),
            "blue": (0, 0, 255),
            "green": (0, 255, 0),
        }
        return color_map.get(color_str.lower(), (255, 255, 255))

    def _wrap_text(self, text: str, font, max_width: int) -> list:
        """Wrap text to fit within width"""
        words = text.split()
        lines = []
        current_line = ""

        for word in words:
            test_line = current_line + " " + word if current_line else word
            bbox = font.getbbox(test_line)
            if bbox[2] <= max_width:
                current_line = test_line
            else:
                if current_line:
                    lines.append(current_line)
                current_line = word

        if current_line:
            lines.append(current_line)

        return lines

    def get_service_stats(self) -> Dict[str, Any]:
        """Get service statistics"""
        return {
            "provider": "openai",
            "model": self.model,
            "max_retries": self.max_retries,
            "cost_per_image_credits": self.cost_credits.get(self.model, 0),
            "status": "ready" if self.api_key else "no_api_key"
        }

# Global image service instance
image_service = ImageService()
