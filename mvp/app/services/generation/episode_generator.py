"""
Episode Generator Service

Handles AI-powered video script generation using OpenAI API
"""

import os
import json
import time
import random
from typing import Dict, List, Optional, Tuple
from datetime import datetime
import openai
from textwrap import dedent
from app.utils.logging import get_logger
from app.config.schema import VideoFormat, EpisodeConfig
from app.services.safety.content_safety import ContentSafetyChecker
from app.utils.pricing import CostCalculator
from app.db.models import Job, VideoStatus

logger = get_logger(__name__)

class GenerationError(Exception):
    """Custom exception for generation failures"""
    pass

class EpisodeGenerator:
    def __init__(self):
        self.logger = get_logger(f"{__name__}.EpisodeGenerator")
        self.safety_checker = ContentSafetyChecker()
        self.cost_calculator = CostCalculator()

        # Initialize OpenAI client
        openai.api_key = os.getenv("OPENAI_API_KEY")
        if not openai.api_key:
            raise GenerationError("OpenAI API key not configured")

        self.model = "gpt-4o"
        self.max_retries = 3
        self.retry_delay = 2

        self.logger.info("Episode generator initialized",
                       model=self.model,
                       max_retries=self.max_retries)

    def generate_episode(self, config: EpisodeConfig) -> Dict:
        """
        Generate a complete episode JSON for a video

        Args:
            config: Episode configuration

        Returns:
            Complete episode data as dict
        """
        start_time = time.time()

        try:
            # Generate initial prompt
            prompt = self._generate_prompt(config)

            # Estimate cost before generation
            estimated_cost = self.cost_calculator.estimate_episode_generation_cost(
                model=self.model,
                estimated_input_tokens=500,
                estimated_output_tokens=1500
            )

            self.logger.info("Starting episode generation",
                           format=config.format,
                           estimated_cost=estimated_cost)

            # Generate with retry logic
            episode_data = None
            for attempt in range(self.max_retries):
                try:
                    episode_data = self._call_openai_api(prompt, config)
                    break
                except Exception as e:
                    if attempt < self.max_retries - 1:
                        self.logger.warning("Generation attempt failed, retrying",
                                         attempt=attempt + 1,
                                         error=str(e))
                        time.sleep(self.retry_delay)
                    else:
                        raise

            # Validate the generated data
            if not self._validate_episode_data(episode_data):
                raise GenerationError("Generated episode data is invalid")

            # Safety check
            safety_check = self.safety_checker.check_content_safety(episode_data)
            if not safety_check[0]:
                self.logger.warning("Generated content failed safety check",
                                 reason=safety_check[1])

                # Regenerate with safer prompt
                safe_prompt = self.safety_checker.generate_safe_prompt(prompt, config.format)
                episode_data = self._call_openai_api(safe_prompt, config)

                # Validate again
                if not self._validate_episode_data(episode_data):
                    raise GenerationError("Safe regenerated episode data is invalid")

            # Calculate actual cost
            actual_cost = self._calculate_actual_cost(prompt, episode_data)

            generation_time = time.time() - start_time
            self.logger.info("Episode generation completed",
                           format=config.format,
                           duration=generation_time,
                           cost=actual_cost,
                           safety_status="passed")

            return episode_data

        except Exception as e:
            self.logger.error("Episode generation failed", error=str(e))
            raise GenerationError(f"Generation failed: {str(e)}")

    def _generate_prompt(self, config: EpisodeConfig) -> str:
        """Generate format-specific prompt"""
        if config.format == VideoFormat.TALKING_OBJECT:
            return self._generate_talking_object_prompt(config)
        elif config.format == VideoFormat.ABSURD_MOTIVATION:
            return self._generate_absurd_motivation_prompt(config)
        else:  # NOTHING_HAPPENS
            return self._generate_nothing_happens_prompt(config)

    def _generate_talking_object_prompt(self, config: EpisodeConfig) -> str:
        """Generate talking object format prompt"""
        template = dedent(
            """
            Generate a funny French short video script in the "Talking Object" format.

            REQUIREMENTS:
            - Language: French (France)
            - Duration: {min_duration}-{max_duration} seconds when spoken
            - Format: A single inanimate object that talks directly to the viewer
            - Tone: Absurd, humorous, lighthearted
            - Content: Completely original, no real people/brands/politics
            - Structure: Hook -> Main content -> Punchline

            OUTPUT STRUCTURE (JSON only, no explanation):
            {{
              "format": "{format_value}",
              "language": "fr-FR",
              "hook_text": "[1-2 second attention-grabbing opening line in French]",
              "script": "[Full script in French, 6-8 seconds when spoken]",
              "on_screen_captions": [
                {{"start_ms": 0, "end_ms": 2000, "text": "[French caption text]"}},
                {{"start_ms": 2000, "end_ms": 4000, "text": "[French caption text]"}}
              ],
              "title_options": [
                "[Funny French title option 1]",
                "[Funny French title option 2]",
                "[Funny French title option 3]"
              ],
              "description": "[Short French description for YouTube, 1-2 sentences]",
              "hashtags": ["#shorts", "#humour", "#absurde"],
              "image_prompt": "[Detailed DALL-E-3 prompt for a simple, original image featuring the talking object]",
              "visual_recipe": {{
                "motion": "cuts_zoom_shake",
                "color_preset": "vibrant",
                "caption_style": "dynamic",
                "font": "Arial"
              }},
              "audio_recipe": {{
                "voice_preset": "friendly_french_male",
                "music_track_id": "yt_audio_library_upbeat_1",
                "music_lufs_target": -28
              }}
            }}

            EXAMPLE IDEAS (choose one or create your own):
            - A sentient toaster complaining about breakfast
            - A philosophical banana questioning its existence
            - A sarcastic rubber duck giving life advice
            - A dramatic houseplant begging for water
            - A confused lamp that thinks it's a disco ball

            IMPORTANT: Respond with ONLY the JSON object, no additional text or explanation.
            """
        ).strip()

        return template.format(
            min_duration=config.min_duration,
            max_duration=config.max_duration,
            format_value=VideoFormat.TALKING_OBJECT.value,
        )

    def _generate_absurd_motivation_prompt(self, config: EpisodeConfig) -> str:
        """Generate absurd motivation format prompt"""
        template = dedent(
            """
            Generate a funny French short video script in the "Absurd Motivation" format.

            REQUIREMENTS:
            - Language: French (France)
            - Duration: {min_duration}-{max_duration} seconds when spoken
            - Format: Motivational speech about a completely ridiculous goal
            - Tone: Over-the-top motivational, inspirational, humorous
            - Content: Completely original, no real people/brands/politics
            - Structure: Problem -> Absurd solution -> Call to inaction

            OUTPUT STRUCTURE (JSON only, no explanation):
            {{
              "format": "{format_value}",
              "language": "fr-FR",
              "hook_text": "[1-2 second attention-grabbing motivational opening in French]",
              "script": "[Full motivational script in French, 6-8 seconds when spoken]",
              "on_screen_captions": [
                {{"start_ms": 0, "end_ms": 2000, "text": "[French caption text]"}},
                {{"start_ms": 2000, "end_ms": 4000, "text": "[French caption text]"}}
              ],
              "title_options": [
                "[Motivational-sounding but absurd French title 1]",
                "[Motivational-sounding but absurd French title 2]",
                "[Motivational-sounding but absurd French title 3]"
              ],
              "description": "[Short French description for YouTube, 1-2 sentences]",
              "hashtags": ["#shorts", "#motivation", "#absurde"],
              "image_prompt": "[DALL-E-3 prompt for a colorful, motivational-style image]",
              "visual_recipe": {{
                "motion": "cuts_zoom_shake",
                "color_preset": "vibrant",
                "caption_style": "dynamic",
                "font": "Impact"
              }},
              "audio_recipe": {{
                "voice_preset": "motivational_french_male",
                "music_track_id": "yt_audio_library_inspirational_1",
                "music_lufs_target": -28
              }}
            }}

            EXAMPLE IDEAS (choose one or create your own):
            - "How to become a professional couch potato"
            - "Mastering the art of strategic procrastination"
            - "The secret to perfecting your staring-into-space technique"
            - "10 steps to winning at doing absolutely nothing"
            - "Becoming the world's most average person"

            IMPORTANT: Respond with ONLY the JSON object, no additional text or explanation.
            """
        ).strip()

        return template.format(
            min_duration=config.min_duration,
            max_duration=config.max_duration,
            format_value=VideoFormat.ABSURD_MOTIVATION.value,
        )

    def _generate_nothing_happens_prompt(self, config: EpisodeConfig) -> str:
        """Generate nothing happens format prompt"""
        template = dedent(
            """
            Generate a funny French short video script in the "Nothing Happens" format.

            REQUIREMENTS:
            - Language: French (France)
            - Duration: {min_duration}-{max_duration} seconds when spoken
            - Format: Build-up to an anti-climax where nothing happens
            - Tone: Dramatic build-up, deadpan delivery, humorous disappointment
            - Content: Completely original, no real people/brands/politics
            - Structure: Dramatic setup -> Expectation building -> Nothing happens

            OUTPUT STRUCTURE (JSON only, no explanation):
            {{
              "format": "{format_value}",
              "language": "fr-FR",
              "hook_text": "[1-2 second intriguing opening line in French]",
              "script": "[Full script in French building to anti-climax, 6-8 seconds when spoken]",
              "on_screen_captions": [
                {{"start_ms": 0, "end_ms": 2000, "text": "[French caption text]"}},
                {{"start_ms": 2000, "end_ms": 4000, "text": "[French caption text]"}}
              ],
              "title_options": [
                "[Dramatic but ultimately boring French title 1]",
                "[Dramatic but ultimately boring French title 2]",
                "[Dramatic but ultimately boring French title 3]"
              ],
              "description": "[Short French description for YouTube, 1-2 sentences]",
              "hashtags": ["#shorts", "#ennuyeux", "#anticipation"],
              "image_prompt": "[DALL-E-3 prompt for a completely ordinary, mundane scene]",
              "visual_recipe": {{
                "motion": "static",
                "color_preset": "monochrome",
                "caption_style": "static",
                "font": "Arial"
              }},
              "audio_recipe": {{
                "voice_preset": "dramatic_french_male",
                "music_track_id": "yt_audio_library_dramatic_1",
                "music_lufs_target": -28
              }}
            }}

            EXAMPLE IDEAS (choose one or create your own):
            - "The most exciting thing that happened today... nothing"
            - "Watch as this man attempts to do something interesting... and fails"
            - "The dramatic conclusion you've been waiting for... still waiting"
            - "An ordinary street where absolutely nothing happens"
            - "The thrilling adventure of a completely still object"

            IMPORTANT: Respond with ONLY the JSON object, no additional text or explanation.
            """
        ).strip()

        return template.format(
            min_duration=config.min_duration,
            max_duration=config.max_duration,
            format_value=VideoFormat.NOTHING_HAPPENS.value,
        )

    def _call_openai_api(self, prompt: str, config: EpisodeConfig) -> Dict:
        """Call OpenAI API with structured output"""
        try:
            response = openai.ChatCompletion.create(
                model=self.model,
                messages=[
                    {
                        "role": "system",
                        "content": "You are a creative French content generator for YouTube Shorts. Always respond in perfect French with the requested JSON structure."
                    },
                    {
                        "role": "user",
                        "content": prompt
                    }
                ],
                response_format={"type": "json_object"},
                temperature=0.9,
                max_tokens=1500,
                top_p=1,
                frequency_penalty=0,
                presence_penalty=0
            )

            # Parse the response
            response_text = response.choices[0].message.content.strip()

            # Clean up any potential JSON formatting issues
            response_text = self._clean_json_response(response_text)

            # Parse JSON
            episode_data = json.loads(response_text)

            return episode_data

        except openai.error.OpenAIError as e:
            self.logger.error("OpenAI API error", error=str(e))
            raise GenerationError(f"OpenAI API error: {str(e)}")
        except json.JSONDecodeError as e:
            self.logger.error("JSON decode error", error=str(e), response=response_text)
            raise GenerationError(f"JSON decode error: {str(e)}")
        except Exception as e:
            self.logger.error("Unexpected API error", error=str(e))
            raise GenerationError(f"Unexpected error: {str(e)}")

    def _clean_json_response(self, response_text: str) -> str:
        """Clean up JSON response text"""
        # Remove any leading/trailing non-JSON characters
        response_text = response_text.strip()

        # Remove markdown code blocks if present
        if response_text.startswith("```json"):
            response_text = response_text[7:].strip()
        if response_text.endswith("```"):
            response_text = response_text[:-3].strip()

        return response_text

    def _validate_episode_data(self, episode_data: Dict) -> bool:
        """Validate episode data structure"""
        required_fields = [
            'format', 'language', 'hook_text', 'script',
            'on_screen_captions', 'title_options', 'description',
            'hashtags', 'image_prompt', 'visual_recipe', 'audio_recipe'
        ]

        for field in required_fields:
            if field not in episode_data:
                self.logger.error("Missing required field in episode data", field=field)
                return False

        # Validate format
        if episode_data['format'] not in [fmt.value for fmt in VideoFormat]:
            self.logger.error("Invalid format in episode data", format=episode_data['format'])
            return False

        # Validate language
        if episode_data['language'] != 'fr-FR':
            self.logger.error("Invalid language in episode data", language=episode_data['language'])
            return False

        # Validate captions
        if not isinstance(episode_data['on_screen_captions'], list) or len(episode_data['on_screen_captions']) == 0:
            self.logger.error("Invalid captions in episode data")
            return False

        # Validate title options
        if not isinstance(episode_data['title_options'], list) or len(episode_data['title_options']) < 3:
            self.logger.error("Invalid title options in episode data")
            return False

        return True

    def _calculate_actual_cost(self, prompt: str, episode_data: Dict) -> float:
        """Calculate actual generation cost"""
        # Count tokens (simplified estimation)
        prompt_tokens = len(prompt.split()) * 1.3  # Approximate tokens
        response_tokens = len(json.dumps(episode_data).split()) * 1.3

        return self.cost_calculator.estimate_episode_generation_cost(
            model=self.model,
            estimated_input_tokens=int(prompt_tokens),
            estimated_output_tokens=int(response_tokens)
        )

    def generate_image_prompt(self, episode_data: Dict) -> str:
        """Generate or refine image prompt from episode data"""
        try:
            # Use the existing image prompt if it's good
            if 'image_prompt' in episode_data and len(episode_data['image_prompt']) > 20:
                return episode_data['image_prompt']

            # Generate a new one based on the script
            script_preview = episode_data['script'][:100]
            format = episode_data['format']

            prompt = f"""Generate a detailed DALL-E-3 image prompt based on this video script preview: "{script_preview}"

The image should:
- Be completely original (no copyrighted characters/brands)
- Match the video format: {format}
- Be simple and clear for a short video
- Use vibrant colors if appropriate
- Be suitable for a 9:16 aspect ratio

Provide only the image prompt text, no additional explanation."""

            response = openai.ChatCompletion.create(
                model=self.model,
                messages=[
                    {
                        "role": "system",
                        "content": "You are an AI image prompt generator. Respond only with the image prompt text."
                    },
                    {
                        "role": "user",
                        "content": prompt
                    }
                ],
                max_tokens=100,
                temperature=0.7
            )

            return response.choices[0].message.content.strip()

        except Exception as e:
            self.logger.error("Failed to generate image prompt", error=str(e))
            # Fallback to generic prompt
            return "A simple, colorful, original scene suitable for a funny short video, no text, no brands, no real people"

# Global generator instance
episode_generator = EpisodeGenerator()
