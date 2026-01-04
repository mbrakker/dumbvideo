"""
TTS (Text-to-Speech) Service

Handles external text-to-speech generation via OpenAI TTS API
"""

import os
import time
import uuid
import random
from typing import Optional, Dict, Any, List
from datetime import datetime
from app.utils.logging import get_logger
from app.contracts.audio import (
    TTSGenerationRequest,
    TTSGenerationResponse
)

logger = get_logger(__name__)

class TTSGenerationError(Exception):
    """Custom exception for TTS generation failures"""
    pass

class TTSService:
    """
    OpenAI Text-to-Speech Service

    Responsible for:
    - Calling OpenAI TTS API
    - Applying seeded randomness for pitch/speed/EQ
    - Cost tracking
    - Voice selection and configuration
    """

    def __init__(self, api_key: Optional[str] = None):
        self.logger = get_logger(f"{__name__}.TTSService")

        self.api_key = api_key or os.getenv("OPENAI_API_KEY")
        if not self.api_key:
            self.logger.warning("OpenAI API key not configured - TTS service will be limited")
            self.api_key = None

        # Service configuration
        self.available_models = ["tts-1", "tts-1-hd"]
        self.available_voices = ["alloy", "echo", "fable", "onyx", "nova", "shimmer"]
        self.max_retries = 3
        self.retry_delay = 2
        self.request_timeout = 60  # seconds

        # Cost tracking (per 1K characters)
        self.cost_per_1k_chars = {
            "tts-1": 15,      # credits
            "tts-1-hd": 30    # credits
        }

        # Seeded random variations for variability
        self.speed_variation_range = (0.25, 4.0)
        self.seed_based_variations = {
            "speed_factor": 0.1,  # ±10% speed variation
            "pitch_offset": 0.05,  # ±5% pitch variation
            "eq_boost": 2.0       # ±2dB EQ boost/cut
        }

        self.logger.info("TTS service initialized",
                       models=self.available_models,
                       voices=self.available_voices,
                       max_retries=self.max_retries)

    def generate_speech(self, request: TTSGenerationRequest) -> TTSGenerationResponse:
        """
        Generate speech using OpenAI TTS API

        Args:
            request: TTS generation request contract

        Returns:
            TTS generation response contract
        """
        start_time = time.time()
        request_id = request.request_id or str(uuid.uuid4())

        try:
            self.logger.info("Starting TTS generation",
                           request_id=request_id,
                           model=request.model,
                           voice=request.voice)

            # Validate request
            if not self._validate_request(request):
                raise TTSGenerationError("Invalid TTS request")

            # Apply seeded randomness if seed provided
            effective_speed = request.speed
            if request.seed is not None:
                random.seed(request.seed)
                # Apply speed variation within reasonable bounds
                speed_variation = random.uniform(-self.seed_based_variations["speed_factor"],
                                               self.seed_based_variations["speed_factor"])
                effective_speed = max(0.25, min(4.0, request.speed * (1 + speed_variation)))
                self.logger.debug("Applied seeded speed variation",
                                original_speed=request.speed,
                                effective_speed=effective_speed,
                                seed=request.seed)

            # Call OpenAI TTS API with retry logic
            audio_data = None
            api_model = None
            for attempt in range(self.max_retries):
                try:
                    audio_data, api_model = self._call_tts_api(request, effective_speed, request_id)
                    break
                except Exception as e:
                    if attempt < self.max_retries - 1:
                        self.logger.warning("TTS API attempt failed, retrying",
                                         attempt=attempt + 1,
                                         error=str(e))
                        time.sleep(self.retry_delay)
                    else:
                        raise

            # Analyze the generated audio
            duration = self._analyze_audio_duration(audio_data)

            # Calculate cost
            cost_chars = len(request.text)

            response = TTSGenerationResponse(
                request=request,
                audio_data=audio_data,
                duration_seconds=duration,
                cost_characters=cost_chars,
                model_used=api_model or request.model,
                voice_used=request.voice,
                speed_actual=effective_speed,
                seed_used=request.seed,
                request_id=request_id
            )

            generation_time = time.time() - start_time
            self.logger.info("TTS generation completed",
                           request_id=request_id,
                           duration=generation_time,
                           audio_duration=duration,
                           cost_characters=cost_chars,
                           effective_speed=effective_speed)

            return response

        except Exception as e:
            self.logger.error("TTS generation failed",
                            request_id=request_id,
                            error=str(e))

            return TTSGenerationResponse(
                request=request,
                audio_data=b"",
                duration_seconds=0.0,
                error=str(e),
                request_id=request_id
            )

    def select_voice_for_episode(self, episode_format: str, seed: Optional[int] = None) -> str:
        """
        Select appropriate voice for episode format

        Args:
            episode_format: Episode format (talking_object, absurd_motivation, nothing_happens)
            seed: Random seed for reproducible selection

        Returns:
            Selected voice name
        """
        # Format-specific voice preferences
        voice_preferences = {
            "talking_object": ["alloy", "echo", "fable"],  # Friendly, approachable voices
            "absurd_motivation": ["alloy", "nova", "shimmer"],  # Energetic, motivational voices
            "nothing_happens": ["onyx", "echo", "fable"]  # Dry, deadpan voices
        }

        available_voices = voice_preferences.get(episode_format, self.available_voices)

        if seed is not None:
            random.seed(seed)

        selected_voice = random.choice(available_voices)

        self.logger.debug("Selected voice for episode format",
                        episode_format=episode_format,
                        selected_voice=selected_voice,
                        available_voices=available_voices)

        return selected_voice

    def get_estimated_duration(self, text: str, speed: float = 1.0) -> float:
        """
        Estimate speech duration based on text length
        Rough approximation: ~150 words per minute at normal speed

        Args:
            text: Input text
            speed: Speech speed multiplier

        Returns:
            Estimated duration in seconds
        """
        # Rough estimation: ~5 characters per second at normal speed
        base_chars_per_second = 5.0
        chars_per_second = base_chars_per_second * speed

        duration = len(text) / chars_per_second

        # Add some padding for natural speech rhythm
        duration *= 1.1

        return max(1.0, duration)  # Minimum 1 second

    def _call_tts_api(self, request: TTSGenerationRequest, effective_speed: float, request_id: str) -> tuple:
        """Make the actual OpenAI TTS API call"""
        import openai
        import io

        client = openai.OpenAI(api_key=self.api_key)

        try:
            # Compress text if needed before sending to API
            sanitized_text = self._sanitize_text(request.text)
            compressed_text = self._compress_text_for_tts(sanitized_text)

            response = client.audio.speech.create(
                model=request.model,
                voice=request.voice,
                input=compressed_text,
                speed=effective_speed,
                response_format="mp3"
            )

            # Get audio data
            audio_data = b""
            for chunk in response.iter_bytes():
                audio_data += chunk

            return audio_data, request.model

        except Exception as e:
            self.logger.error("OpenAI TTS API call failed",
                            request_id=request_id,
                            error=str(e))
            raise TTSGenerationError(f"TTS API error: {str(e)}")

    def _validate_request(self, request: TTSGenerationRequest) -> bool:
        """Validate TTS request parameters"""
        if not request.text or len(request.text.strip()) == 0:
            return False

        if request.model not in self.available_models:
            return False

        if request.voice not in self.available_voices:
            return False

        if not 0.25 <= request.speed <= 4.0:
            return False

        if len(request.text) > 4096:  # OpenAI limit
            return False

        return True

    def _sanitize_text(self, text: str) -> str:
        """Sanitize text for TTS generation"""
        # Remove excessive whitespace
        text = " ".join(text.split())

        # Limit length if needed (OpenAI allows up to 4096 chars)
        if len(text) > 4096:
            text = text[:4093] + "..."

        return text.strip()

    def _compress_text_for_tts(self, text: str, max_length: int = 4096) -> str:
        """
        Compress text for TTS generation while preserving meaning
        Uses semantic compression to reduce token count
        """
        if len(text) <= max_length:
            return text

        try:
            # Use OpenAI to summarize/compress the text
            from openai import OpenAI
            import os
            from dotenv import load_dotenv

            load_dotenv()
            api_key = os.getenv("OPENAI_API_KEY")
            if not api_key:
                self.logger.warning("OpenAI API key not available for text compression")
                return text[:max_length - 3] + "..."

            client = OpenAI(api_key=api_key)

            # Create compression prompt
            prompt = f"""Compress this text to {max_length//2} characters while preserving the main meaning and tone.
Original text: {text}
Compressed version:"""

            response = client.chat.completions.create(
                model="gpt-4o",
                messages=[
                    {
                        "role": "system",
                        "content": "You are a text compression assistant. Compress text while preserving meaning and tone."
                    },
                    {
                        "role": "user",
                        "content": prompt
                    }
                ],
                max_tokens=max_length//2,
                temperature=0.3
            )

            compressed_text = response.choices[0].message.content.strip()
            return compressed_text if len(compressed_text) <= max_length else compressed_text[:max_length - 3] + "..."

        except Exception as e:
            self.logger.error("Text compression failed, falling back to truncation", error=str(e))
            return text[:max_length - 3] + "..."

    def _analyze_audio_duration(self, audio_data: bytes) -> float:
        """Analyze audio data to get duration"""
        try:
            from pydub import AudioSegment
            import io

            # Load audio from bytes
            audio_segment = AudioSegment.from_file(io.BytesIO(audio_data), format="mp3")
            duration_seconds = len(audio_segment) / 1000.0  # Convert ms to seconds

            self.logger.debug("Analyzed audio duration",
                            duration_seconds=duration_seconds,
                            raw_bytes=len(audio_data))

            return duration_seconds

        except Exception as e:
            self.logger.warning("Failed to analyze audio duration",
                              error=str(e))
            return 0.0

    def get_voice_characteristics(self, voice: str) -> Dict[str, Any]:
        """Get voice characteristics for UI/display"""
        voice_info = {
            "alloy": {
                "gender": "neutral",
                "style": "versatile",
                "description": "Well-rounded, adaptable voice",
                "use_case": "general purpose, educational content"
            },
            "echo": {
                "gender": "male",
                "style": "warm",
                "description": "Warm, friendly male voice",
                "use_case": "narratives, instructional content"
            },
            "fable": {
                "gender": "female",
                "style": "storytelling",
                "description": "Youthful, narrative-focused female voice",
                "use_case": "storytelling, children's content"
            },
            "onyx": {
                "gender": "male",
                "style": "deep",
                "description": "Deep, authoritative male voice",
                "use_case": "formal announcements, serious content"
            },
            "nova": {
                "gender": "female",
                "style": "young",
                "description": "Youthful, energetic female voice",
                "use_case": "casual, friendly content"
            },
            "shimmer": {
                "gender": "female",
                "style": "expressive",
                "description": "Expressive female voice with character",
                "use_case": "advertising, creative content"
            }
        }

        return voice_info.get(voice, {})

    def get_service_stats(self) -> Dict[str, Any]:
        """Get service statistics"""
        return {
            "provider": "openai",
            "available_models": self.available_models,
            "available_voices": self.available_voices,
            "max_text_length": 4096,
            "speed_range": "0.25-4.0",
            "cost_per_1k_chars_tts1": self.cost_per_1k_chars["tts-1"],
            "cost_per_1k_chars_hd": self.cost_per_1k_chars["tts-1-hd"],
            "status": "ready" if self.api_key else "no_api_key"
        }

    def test_voice_sample(self, voice: str, text: str = "Bonjour! Ceci est un test de synthèse vocale.") -> bytes:
        """
        Generate a voice sample for testing

        Args:
            voice: Voice to test
            text: Test text (default French sample)

        Returns:
            Audio data bytes
        """
        test_request = TTSGenerationRequest(
            text=text,
            voice=voice,
            model="tts-1",  # Use basic model for testing
            speed=1.0
        )

        response = self.generate_speech(test_request)
        return response.audio_data if response.audio_data else b""

# Global TTS service instance
tts_service = TTSService()
