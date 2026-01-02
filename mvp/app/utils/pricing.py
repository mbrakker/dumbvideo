"""
Cost Estimation and Tracking Utility

Implements OpenAI pricing calculations and budget enforcement
"""

from typing import Dict, Optional, Tuple
from datetime import datetime, timedelta
from app.utils.logging import get_logger
from app.config.schema import VideoFormat

logger = get_logger(__name__)

class PricingError(Exception):
    """Custom exception for pricing operations"""
    pass

class CostCalculator:
    def __init__(self):
        self.logger = get_logger(f"{__name__}.CostCalculator")

        # OpenAI pricing as of 2024 (in USD per 1M tokens)
        self.openai_pricing = {
            "gpt-4o": {
                "input": 5.00,    # $5 per 1M input tokens
                "output": 15.00   # $15 per 1M output tokens
            },
            "gpt-4-turbo": {
                "input": 10.00,
                "output": 30.00
            },
            "dall-e-3": {
                "standard": 0.04,  # $0.04 per image (1024x1024)
                "hd": 0.08,        # $0.08 per image (1024x1024 HD)
                "quality_hd": 0.12 # $0.12 per image (1024x1024 HD with quality)
            },
            "tts-1": {
                "per_character": 0.015 / 1000  # $0.015 per 1000 characters
            }
        }

        # Conversion rate (USD to EUR)
        self.usd_to_eur = 0.93

    def estimate_episode_generation_cost(
        self,
        model: str = "gpt-4o",
        estimated_input_tokens: int = 500,
        estimated_output_tokens: int = 1500
    ) -> float:
        """
        Estimate cost for generating episode JSON

        Args:
            model: OpenAI model to use
            estimated_input_tokens: Estimated input tokens
            estimated_output_tokens: Estimated output tokens

        Returns:
            Cost in EUR
        """
        try:
            if model not in self.openai_pricing:
                raise PricingError(f"Unknown model: {model}")

            pricing = self.openai_pricing[model]

            # Calculate cost in USD
            input_cost = (estimated_input_tokens / 1_000_000) * pricing["input"]
            output_cost = (estimated_output_tokens / 1_000_000) * pricing["output"]
            total_usd = input_cost + output_cost

            # Convert to EUR
            total_eur = total_usd * self.usd_to_eur

            self.logger.debug("Episode generation cost estimated",
                           model=model,
                           input_tokens=estimated_input_tokens,
                           output_tokens=estimated_output_tokens,
                           cost_eur=total_eur)

            return total_eur

        except Exception as e:
            self.logger.error("Failed to estimate episode generation cost", error=str(e))
            raise PricingError(f"Cost estimation failed: {str(e)}")

    def estimate_image_generation_cost(
        self,
        model: str = "dall-e-3",
        quality: str = "standard",
        size: str = "1024x1024"
    ) -> float:
        """
        Estimate cost for generating image

        Args:
            model: Image model to use
            quality: Quality level (standard, hd, quality_hd)
            size: Image size

        Returns:
            Cost in EUR
        """
        try:
            if model not in self.openai_pricing:
                raise PricingError(f"Unknown model: {model}")

            pricing = self.openai_pricing[model]

            # Get pricing based on quality
            if quality == "hd":
                cost_usd = pricing["hd"]
            elif quality == "quality_hd":
                cost_usd = pricing["quality_hd"]
            else:  # standard
                cost_usd = pricing["standard"]

            # Convert to EUR
            cost_eur = cost_usd * self.usd_to_eur

            self.logger.debug("Image generation cost estimated",
                           model=model,
                           quality=quality,
                           size=size,
                           cost_eur=cost_eur)

            return cost_eur

        except Exception as e:
            self.logger.error("Failed to estimate image generation cost", error=str(e))
            raise PricingError(f"Cost estimation failed: {str(e)}")

    def estimate_tts_cost(
        self,
        model: str = "tts-1",
        tts_length: int = 100
    ) -> float:
        """
        Estimate cost for TTS generation

        Args:
            model: TTS model to use
            tts_length: Length of text in characters

        Returns:
            Cost in EUR
        """
        try:
            if model not in self.openai_pricing:
                raise PricingError(f"Unknown model: {model}")

            pricing = self.openai_pricing[model]
            cost_per_1000 = pricing["per_character"] * 1000  # Convert to per 1000 chars

            # Calculate cost
            cost_usd = (tts_length / 1000) * cost_per_1000
            cost_eur = cost_usd * self.usd_to_eur

            self.logger.debug("TTS cost estimated",
                           model=model,
                           text_length=tts_length,
                           cost_eur=cost_eur)

            return cost_eur

        except Exception as e:
            self.logger.error("Failed to estimate TTS cost", error=str(e))
            raise PricingError(f"Cost estimation failed: {str(e)}")

    def estimate_total_video_cost(
        self,
        format: VideoFormat,
        script_length: int = 150,
        tts_length: int = 100
    ) -> float:
        """
        Estimate total cost for generating one video

        Args:
            format: Video format
            script_length: Length of script in words
            tts_length: Length of TTS text in characters

        Returns:
            Total cost in EUR
        """
        try:
            # Estimate episode generation cost
            episode_cost = self.estimate_episode_generation_cost()

            # Estimate image generation cost
            image_cost = self.estimate_image_generation_cost()

            # Estimate TTS cost
            tts_cost = self.estimate_tts_cost(tts_length=tts_length)

            # Total cost
            total_cost = episode_cost + image_cost + tts_cost

            self.logger.info("Total video cost estimated",
                           format=format,
                           episode_cost=episode_cost,
                           image_cost=image_cost,
                           tts_cost=tts_cost,
                           total_cost=total_cost)

            return total_cost

        except Exception as e:
            self.logger.error("Failed to estimate total video cost", error=str(e))
            raise PricingError(f"Total cost estimation failed: {str(e)}")

    def check_budget_compliance(
        self,
        daily_cost: float,
        budget: float,
        video_count: int,
        max_videos: int
    ) -> Tuple[bool, Optional[str]]:
        """
        Check if proposed video generation complies with budget

        Args:
            daily_cost: Current daily cost so far
            budget: Daily budget limit
            video_count: Current video count
            max_videos: Maximum videos per day

        Returns:
            Tuple of (compliant: bool, message: str)
        """
        try:
            # Check video count limit
            if video_count >= max_videos:
                return False, f"Maximum daily videos reached ({max_videos})"

            # Check budget limit
            if daily_cost >= budget:
                return False, f"Daily budget exceeded (€{budget:.2f})"

            return True, "Budget compliant"

        except Exception as e:
            self.logger.error("Budget compliance check failed", error=str(e))
            return False, f"Budget check error: {str(e)}"

# Global pricing instance
pricing = CostCalculator()
