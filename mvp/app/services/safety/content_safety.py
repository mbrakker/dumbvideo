"""
Content Safety Service

Implements multi-layer content filtering and compliance checking
"""

import re
import json
from typing import Dict, List, Tuple, Optional
from app.utils.logging import get_logger
from app.config.schema import VideoFormat, EpisodeConfig
from app.db.models import Job, VideoStatus
from datetime import datetime

logger = get_logger(__name__)

class SafetyError(Exception):
    """Custom exception for safety violations"""
    pass

class ContentSafetyChecker:
    def __init__(self):
        self.logger = get_logger(f"{__name__}.ContentSafetyChecker")

        # Load safety configuration
        self.blacklisted_keywords = self._load_blacklisted_keywords()
        self.safety_threshold = 0.9  # Minimum safety score to pass

        self.logger.info("Content safety service initialized",
                       keywords_count=len(self.blacklisted_keywords),
                       threshold=self.safety_threshold)

    def _load_blacklisted_keywords(self) -> List[str]:
        """Load blacklisted keywords from configuration"""
        # These would come from config in production
        return [
            # Copyright/brand protection
            "disney", "marvel", "star wars", "microsoft", "apple", "google",
            "netflix", "amazon", "facebook", "twitter", "instagram", "tiktok",
            "copyright", "trademark", "brand", "logo", "sponsor",

            # Real people/celebrities
            "elon musk", "jeff bezos", "mark zuckerberg", "donald trump",
            "joe biden", "kim kardashian", "taylor swift", "beyonce",
            "celebrity", "famous", "influencer", "president", "prime minister",

            # Political/news topics
            "politics", "election", "war", "conflict", "protest", "government",
            "law", "court", "trial", "scandal", "corruption", "brexit",
            "covid", "pandemic", "vaccine", "climate change",

            # Sexual/suggestive content
            "sexy", "nude", "porn", "sex", "erotic", "adult", "nsfw",
            "kinky", "fetish", "bdsm", "orgasm", "aroused", "horny",

            # Profanity/slurs (French)
            "putain", "merde", "connard", "salope", "enculé", "bite",
            "couille", "nique", "fils de pute", "garce", "enfoiré",

            # Medical/financial advice
            "cancer", "tumor", "chemotherapy", "suicide", "depression",
            "anxiety", "therapy", "medication", "prescription", "doctor",
            "hospital", "investment", "stock", "crypto", "bitcoin",
            "financial advice", "get rich", "money making",

            # Violence/gore
            "kill", "murder", "blood", "gore", "violence", "abuse",
            "rape", "torture", "death", "suicide", "bomb", "terrorism"
        ]

    def check_content_safety(self, episode_data: Dict) -> Tuple[bool, Optional[str]]:
        """
        Check if episode content passes safety requirements

        Args:
            episode_data: Episode JSON data to validate

        Returns:
            Tuple of (safe: bool, reason: str)
        """
        try:
            # Convert to lowercase for case-insensitive matching
            content = self._extract_content_text(episode_data).lower()

            # Check each safety layer
            checks = [
                ("blacklisted_keywords", self._check_blacklisted_keywords(content)),
                ("copyright_brands", self._check_copyright_brands(content)),
                ("real_people", self._check_real_people(content)),
                ("political_content", self._check_political_content(content)),
                ("sexual_content", self._check_sexual_content(content)),
                ("profanity", self._check_profanity(content)),
                ("medical_advice", self._check_medical_advice(content)),
                ("violence", self._check_violence(content))
            ]

            # Run all checks
            for check_name, result in checks:
                if not result[0]:  # Check failed
                    self.logger.warning("Content safety check failed",
                                     check=check_name,
                                     reason=result[1],
                                     content_preview=content[:100])
                    return False, f"Safety check failed: {check_name} - {result[1]}"

            self.logger.info("Content safety check passed",
                           content_preview=content[:100])
            return True, "Content passed all safety checks"

        except Exception as e:
            self.logger.error("Content safety check failed", error=str(e))
            return False, f"Safety check error: {str(e)}"

    def _extract_content_text(self, episode_data: Dict) -> str:
        """Extract all text content from episode data"""
        text_parts = []

        # Add hook text
        if 'hook_text' in episode_data:
            text_parts.append(episode_data['hook_text'])

        # Add script
        if 'script' in episode_data:
            text_parts.append(episode_data['script'])

        # Add captions
        if 'on_screen_captions' in episode_data:
            for caption in episode_data['on_screen_captions']:
                text_parts.append(caption['text'])

        # Add title options
        if 'title_options' in episode_data:
            text_parts.extend(episode_data['title_options'])

        # Add description
        if 'description' in episode_data:
            text_parts.append(episode_data['description'])

        # Add image prompt
        if 'image_prompt' in episode_data:
            text_parts.append(episode_data['image_prompt'])

        return " ".join(text_parts)

    def _check_blacklisted_keywords(self, content: str) -> Tuple[bool, str]:
        """Check for blacklisted keywords"""
        for keyword in self.blacklisted_keywords:
            if keyword in content:
                return False, f"Contains blacklisted keyword: {keyword}"
        return True, "No blacklisted keywords found"

    def _check_copyright_brands(self, content: str) -> Tuple[bool, str]:
        """Check for copyrighted brands and IP"""
        copyright_terms = [
            "disney", "marvel", "star wars", "harry potter",
            "microsoft", "apple", "google", "netflix", "amazon",
            "facebook", "twitter", "instagram", "tiktok", "youtube",
            "copyright", "trademark", "brand", "logo"
        ]

        for term in copyright_terms:
            if term in content:
                return False, f"Contains copyrighted brand/IP: {term}"
        return True, "No copyrighted brands found"

    def _check_real_people(self, content: str) -> Tuple[bool, str]:
        """Check for real people and celebrities"""
        person_terms = [
            "elon musk", "jeff bezos", "mark zuckerberg",
            "donald trump", "joe biden", "kim kardashian",
            "taylor swift", "beyonce", "celebrity", "famous",
            "president", "prime minister", "king", "queen"
        ]

        for term in person_terms:
            if term in content:
                return False, f"Contains real person/celebrity reference: {term}"
        return True, "No real people found"

    def _check_political_content(self, content: str) -> Tuple[bool, str]:
        """Check for political and news content"""
        political_terms = [
            "politics", "election", "war", "conflict", "protest",
            "government", "law", "court", "trial", "scandal",
            "corruption", "brexit", "covid", "pandemic"
        ]

        for term in political_terms:
            if term in content:
                return False, f"Contains political/news content: {term}"
        return True, "No political content found"

    def _check_sexual_content(self, content: str) -> Tuple[bool, str]:
        """Check for sexual and suggestive content"""
        sexual_terms = [
            "sexy", "nude", "porn", "sex", "erotic", "adult",
            "nsfw", "kinky", "fetish", "bdsm", "orgasm",
            "aroused", "horny", "intimate", "sensual"
        ]

        for term in sexual_terms:
            if term in content:
                return False, f"Contains sexual/suggestive content: {term}"
        return True, "No sexual content found"

    def _check_profanity(self, content: str) -> Tuple[bool, str]:
        """Check for profanity and slurs"""
        profanity_terms = [
            "putain", "merde", "connard", "salope", "enculé",
            "bite", "couille", "nique", "fils de pute", "garce",
            "enfoiré", "chier", "emmerder", "baiser", "branler"
        ]

        for term in profanity_terms:
            if term in content:
                return False, f"Contains profanity/slurs: {term}"
        return True, "No profanity found"

    def _check_medical_advice(self, content: str) -> Tuple[bool, str]:
        """Check for medical and financial advice"""
        medical_terms = [
            "cancer", "tumor", "chemotherapy", "suicide",
            "depression", "anxiety", "therapy", "medication",
            "prescription", "doctor", "hospital", "diagnosis",
            "treatment", "cure", "disease", "illness"
        ]

        financial_terms = [
            "investment", "stock", "crypto", "bitcoin",
            "financial advice", "get rich", "money making",
            "trading", "forex", "wall street", "profit"
        ]

        all_terms = medical_terms + financial_terms

        for term in all_terms:
            if term in content:
                return False, f"Contains medical/financial advice: {term}"
        return True, "No medical/financial advice found"

    def _check_violence(self, content: str) -> Tuple[bool, str]:
        """Check for violent content"""
        violence_terms = [
            "kill", "murder", "blood", "gore", "violence",
            "abuse", "rape", "torture", "death", "suicide",
            "bomb", "terrorism", "shoot", "stab", "beat"
        ]

        for term in violence_terms:
            if term in content:
                return False, f"Contains violent content: {term}"
        return True, "No violent content found"

    def generate_safe_prompt(self, original_prompt: str, format: VideoFormat) -> str:
        """
        Generate a safer version of a prompt that failed safety checks

        Args:
            original_prompt: The original unsafe prompt
            format: Video format for context

        Returns:
            Safer prompt version
        """
        try:
            # Analyze what made the original prompt unsafe
            safety_check = self.check_content_safety({"script": original_prompt})

            if safety_check[0]:
                return original_prompt  # Already safe

            # Generate format-specific safe prompt
            if format == VideoFormat.TALKING_OBJECT:
                return self._generate_safe_talking_object_prompt()
            elif format == VideoFormat.ABSURD_MOTIVATION:
                return self._generate_safe_absurd_motivation_prompt()
            else:  # NOTHING_HAPPENS
                return self._generate_safe_nothing_happens_prompt()

        except Exception as e:
            self.logger.error("Failed to generate safe prompt", error=str(e))
            # Fallback to generic safe prompt
            return "Generate a funny, absurd, and completely original short video concept in French. Avoid any real people, brands, politics, or controversial topics. Make it lighthearted and entertaining."

    def _generate_safe_talking_object_prompt(self) -> str:
        """Generate safe talking object prompt"""
        safe_objects = [
            "a sentient toaster", "a philosophical banana",
            "a sarcastic rubber duck", "a dramatic houseplant",
            "a confused lamp", "an existentialist coffee mug",
            "a rebellious sock", "a pretentious wine bottle",
            "a paranoid alarm clock", "a melodramatic pillow"
        ]

        safe_topics = [
            "the meaning of breakfast", "why Mondays are weird",
            "the secret life of office supplies", "if inanimate objects dream",
            "the philosophy of laziness", "why we procrastinate",
            "the art of doing nothing", "how to be dramatically average",
            "the joys of mediocrity", "why we love comfort food"
        ]

        import random
        object = random.choice(safe_objects)
        topic = random.choice(safe_topics)

        return f"""Generate a funny French short video script featuring {object} talking about {topic}.
The script should be:
- 6-8 seconds when spoken aloud
- Completely original and absurd
- Lighthearted and humorous
- Avoid any real people, brands, politics, or controversial topics
- Use simple, everyday French
- End with a silly punchline or twist
- Include 2-3 on-screen captions for emphasis
- Provide 3 title options that are funny and intriguing
- Suggest a simple, original image prompt for DALL-E-3"""

    def _generate_safe_absurd_motivation_prompt(self) -> str:
        """Generate safe absurd motivation prompt"""
        absurd_goals = [
            "becoming the world's most average person",
            "mastering the art of sitting still",
            "collecting invisible achievements",
            "winning at doing nothing",
            "becoming a professional nap champion",
            "perfecting the art of staring into space",
            "collecting boring moments",
            "mastering the skill of forgetting things",
            "becoming a connoisseur of mediocrity",
            "perfecting the art of procrastination"
        ]

        absurd_methods = [
            "by practicing extreme laziness",
            "through the power of daydreaming",
            "by embracing your inner couch potato",
            "with the magic of doing nothing",
            "through strategic napping",
            "by perfecting the art of staring",
            "with creative procrastination",
            "by mastering the skill of forgetting",
            "through the power of boredom",
            "with the magic of mediocrity"
        ]

        import random
        goal = random.choice(absurd_goals)
        method = random.choice(absurd_methods)

        return f"""Generate an absurd motivational French short video script about {goal} {method}.
The script should be:
- 6-8 seconds when spoken aloud
- Completely original and ridiculous
- Lighthearted and funny
- Avoid any real people, brands, politics, or controversial topics
- Use simple, everyday French with motivational tone
- Include exaggerated, silly advice
- Add 2-3 on-screen captions for comedic effect
- Provide 3 title options that sound motivational but are absurd
- Suggest a colorful, original image prompt for DALL-E-3"""

    def _generate_safe_nothing_happens_prompt(self) -> str:
        """Generate safe nothing happens prompt"""
        mundane_scenes = [
            "a completely empty street",
            "a blank white wall",
            "an unmoving cloud",
            "a still life of ordinary objects",
            "a quiet corner of a room",
            "an empty park bench",
            "a motionless ceiling fan",
            "a perfectly still bowl of fruit",
            "an unmoving curtain",
            "a quiet suburban sidewalk"
        ]

        anti_climaxes = [
            "and then nothing happens",
            "but nothing changes",
            "and it stays exactly the same",
            "but everything remains still",
            "and nothing moves",
            "but it's completely uneventful",
            "and everything stays boring",
            "but nothing exciting occurs",
            "and it remains perfectly ordinary",
            "but absolutely nothing happens"
        ]

        import random
        scene = random.choice(mundane_scenes)
        anti_climax = random.choice(anti_climaxes)

        return f"""Generate a 'nothing happens' French short video script featuring {scene} where {anti_climax}.
The script should be:
- 6-8 seconds when spoken aloud
- Completely original and anti-climactic
- Lighthearted and funny in its boredom
- Avoid any real people, brands, politics, or controversial topics
- Use simple, everyday French
- Build up to a non-event
- Include 2-3 on-screen captions that emphasize the nothingness
- Provide 3 title options that promise excitement but deliver boredom
- Suggest a minimalist, ordinary image prompt for DALL-E-3"""

# Global safety instance
content_safety = ContentSafetyChecker()
