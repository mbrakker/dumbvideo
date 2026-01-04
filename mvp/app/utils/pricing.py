"""
Cost Estimation and Tracking Utility

Implements OpenAI pricing calculations and budget enforcement
"""

from typing import Dict, Optional, Tuple
from datetime import datetime
from app.utils.logging import get_logger
from app.config.schema import VideoFormat
import tiktoken
from functools import lru_cache

logger = get_logger(__name__)

class PricingError(Exception):
    """Custom exception for pricing operations"""
    pass

class CostCalculator:
    def __init__(self):
        self.logger = get_logger(f"{__name__}.CostCalculator")
        self._spend_tracker: Dict[str, Dict[str, float]] = {}

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
        estimated_output_tokens: int = 1500,
        max_tokens: Optional[int] = None
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
            if max_tokens:
                estimated_input_tokens = min(estimated_input_tokens, max_tokens)
                estimated_output_tokens = min(estimated_output_tokens, max_tokens)

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

    def count_tokens(self, text: str, model: str = "gpt-4o", max_tokens: Optional[int] = None) -> int:
        """
        Count tokens in text using tiktoken for accurate tokenization

        Args:
            text: Input text to tokenize
            model: Model to use for tokenization

        Returns:
            Number of tokens (capped if max_tokens provided)
        """
        try:
            encoding = self._get_encoding(model)
            tokens = encoding.encode(text)
            token_count = len(tokens)
        except Exception as e:
            self.logger.error("Failed to count tokens", error=str(e))
            token_count = int(len(text.split()) * 1.3)

        if max_tokens is not None and token_count > max_tokens:
            self.logger.warning(
                "Token count exceeds configured maximum; applying cap",
                model=model,
                calculated_tokens=token_count,
                max_tokens=max_tokens,
            )
            return max_tokens

        return token_count

    @lru_cache(maxsize=8)
    def _get_encoding(self, model: str) -> tiktoken.Encoding:
        return tiktoken.encoding_for_model(model)

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
        max_videos: int,
        date_key: Optional[str] = None
    ) -> Tuple[bool, Optional[str]]:
        """
        Check if proposed video generation complies with budget

        Args:
            daily_cost: Current daily cost so far
            budget: Daily budget limit
            video_count: Current video count
            max_videos: Maximum videos per day
            date_key: Optional date label (YYYY-MM-DD). If omitted, uses today's date.

        Returns:
            Tuple of (compliant: bool, message: str)
        """
        try:
            effective_date = date_key or datetime.utcnow().date().isoformat()
            tracked = self.get_daily_spend(effective_date)
            effective_cost = max(daily_cost, tracked.get("cost_eur", 0.0))

            # Check video count limit
            if video_count >= max_videos:
                return False, f"Maximum daily videos reached ({max_videos})"

            # Check budget limit
            if effective_cost >= budget:
                return False, f"Daily budget exceeded (€{budget:.2f})"

            return True, "Budget compliant"

        except Exception as e:
            self.logger.error("Budget compliance check failed", error=str(e))
            return False, f"Budget check error: {str(e)}"

    def track_spend(self, date_key: str, cost_eur: float, model: str, input_tokens: int = 0, output_tokens: int = 0):
        """
        Track spend in-memory to avoid relying solely on caller-provided totals.
        """
        day_entry = self._spend_tracker.setdefault(date_key, {"cost_eur": 0.0, "input_tokens": 0, "output_tokens": 0, "events": 0})
        day_entry["cost_eur"] += cost_eur
        day_entry["input_tokens"] += input_tokens
        day_entry["output_tokens"] += output_tokens
        day_entry["events"] += 1
        self.logger.info(
            "Tracked spend event",
            date=date_key,
            model=model,
            cost_increment=cost_eur,
            cost_total=day_entry["cost_eur"],
            input_tokens=input_tokens,
            output_tokens=output_tokens,
        )

    def get_daily_spend(self, date_key: str) -> Dict[str, float]:
        """Get tracked spend for a given date."""
        return self._spend_tracker.get(date_key, {"cost_eur": 0.0, "input_tokens": 0, "output_tokens": 0, "events": 0})

    def estimate_request_cost(self, model: str, input_tokens: int, output_tokens: int) -> float:
        """Estimate cost for a single request using cached pricing."""
        if model not in self.openai_pricing:
            raise PricingError(f"Unknown model: {model}")

        pricing = self.openai_pricing[model]
        input_cost = (input_tokens / 1_000_000) * pricing.get("input", 0)
        output_cost = (output_tokens / 1_000_000) * pricing.get("output", 0)
        return (input_cost + output_cost) * self.usd_to_eur

# Global pricing instance
pricing = CostCalculator()
