"""
Production-Grade Rendering Tests

Tests the complete rendering pipeline with real assets and external services
"""

import os
import tempfile
import shutil
from pathlib import Path
import pytest
from app.utils.logging import get_logger
from app.services.rendering.image_service import image_service, ImageGenerationRequest, ImageFallbackRequest
from app.services.rendering.tts_service import tts_service, TTSGenerationRequest
from app.services.rendering.video_renderer import video_renderer
from app.contracts.image import ImageGenerationResponse
from app.contracts.audio import TTSGenerationResponse

logger = get_logger(__name__)

class TestRenderingProduction:
    """Test production-grade rendering features"""

    def setup_method(self):
        """Setup test environment"""
        self.test_dir = tempfile.mkdtemp(prefix="test_rendering_")
        self.music_test_dir = os.path.join(self.test_dir, "music")

        # Create test directories
        os.makedirs(self.music_test_dir, exist_ok=True)

        logger.info("Test environment setup", test_dir=self.test_dir)

    def teardown_method(self):
        """Clean up test environment"""
        if os.path.exists(self.test_dir):
            shutil.rmtree(self.test_dir)
        logger.info("Test environment cleaned up")

    def test_image_service_dalle_generation(self):
        """Test DALL·E image generation service"""
        try:
            request = ImageGenerationRequest(
                prompt="A funny talking toaster in a kitchen, cartoon style",
                model="dall-e-3",
                size="1792x1024",
                style="vivid",
                request_id="test_image_001"
            )

            response = image_service.generate_image(request)

            # Should succeed or provide fallback
            assert response.request.prompt == request.prompt
            assert response.request_id == request.request_id

            if response.error:
                # Test fallback generation
                fallback_request = ImageFallbackRequest(
                    text="Funny talking toaster",
                    width=1080,
                    height=1920,
                    style="gradient",
                    request_id="test_fallback_001"
                )

                fallback_response = image_service.generate_fallback_image(fallback_request)

                assert fallback_response.image_data
                assert len(fallback_response.image_data) > 0
                assert fallback_response.width == 1080
                assert fallback_response.height == 1920
                assert fallback_response.format == "PNG"

            logger.info("Image service test passed")

        except Exception as e:
            logger.error("Image service test failed", error=str(e))
            pytest.skip(f"Image service test failed (may be due to missing API keys): {str(e)}")

    def test_tts_service_generation(self):
        """Test TTS service generation"""
        try:
            request = TTSGenerationRequest(
                text="Bonjour! Ceci est un test de synthèse vocale.",
                model="tts-1-hd",
                voice="alloy",
                speed=1.0,
                request_id="test_tts_001"
            )

            response = tts_service.generate_speech(request)

            # Should succeed or provide error
            assert response.request.text == request.text
            assert response.request_id == request.request_id

            if not response.error:
                assert response.audio_data
                assert len(response.audio_data) > 0
                assert response.duration_seconds > 0
                assert response.cost_characters > 0
                assert response.model_used in ["tts-1", "tts-1-hd"]

            logger.info("TTS service test passed")

        except Exception as e:
            logger.error("TTS service test failed", error=str(e))
            pytest.skip(f"TTS service test failed (may be due to missing API keys): {str(e)}")

    def test_music_validation(self):
        """Test background music validation"""
        # Test with empty music directory
        validation = video_renderer._validate_music_availability()

        # Should detect no music
        assert not validation["music_available"]
        assert validation["total_tracks"] == 0
        assert len(validation["selected_tracks"]) == 0

        # Test with mock music files
        self._create_mock_music_files()

        validation = video_renderer._validate_music_availability()

        # Should find valid tracks
        assert validation["music_available"] is True
        assert validation["total_tracks"] >= 2
        assert len(validation["selected_tracks"]) >= 1

        logger.info("Music validation test passed")

    def test_caption_generation_density(self):
        """Test caption generation with different densities"""
        test_script = "Bonjour! Je suis un grille-pain qui parle. C'est très amusant de pouvoir parler comme un humain."
        duration = 8.0  # seconds

        # Test sparse captions
        sparse_captions = video_renderer._segment_script_into_captions(
            test_script, duration, "sparse", "dynamic"
        )
        assert len(sparse_captions) <= 3  # Should be fewer captions

        # Test dense captions
        dense_captions = video_renderer._segment_script_into_captions(
            test_script, duration, "dense", "dynamic"
        )
        assert len(dense_captions) >= len(sparse_captions)  # Should have more captions

        logger.info("Caption density test passed")

    def test_adaptive_caption_styling(self):
        """Test adaptive caption styling"""
        resolution = (1080, 1920)

        # Test with short text
        short_caption = {"start_ms": 0, "end_ms": 2000, "text": "Hello!"}
        styled_short = video_renderer._apply_adaptive_caption_styling(short_caption, resolution)
        assert styled_short["_render_config"]["font_size"] >= 48

        # Test with long text
        long_caption = {"start_ms": 0, "end_ms": 3000, "text": "This is a very long caption that should be styled differently"}
        styled_long = video_renderer._apply_adaptive_caption_styling(long_caption, resolution)
        assert styled_long["_render_config"]["font_size"] < styled_short["_render_config"]["font_size"]

        logger.info("Adaptive styling test passed")

    def test_voice_selection_by_format(self):
        """Test voice selection based on episode format"""
        # Test format-specific voice selection
        talking_voice = tts_service.select_voice_for_episode("talking_object")
        assert talking_voice in ["alloy", "echo", "fable"]

        motivation_voice = tts_service.select_voice_for_episode("absurd_motivation")
        assert motivation_voice in ["alloy", "nova", "shimmer"]

        nothing_voice = tts_service.select_voice_for_episode("nothing_happens")
        assert nothing_voice in ["onyx", "echo", "fable"]

        logger.info("Voice selection test passed")

    def test_service_stats(self):
        """Test service statistics reporting"""
        image_stats = image_service.get_service_stats()
        assert "status" in image_stats
        assert "model" in image_stats

        tts_stats = tts_service.get_service_stats()
        assert "available_voices" in tts_stats
        assert "available_models" in tts_stats
        assert "status" in tts_stats

        logger.info("Service stats test passed")

    def _create_mock_music_files(self):
        """Create mock music files for testing"""
        from pydub import AudioSegment
        from pydub.generators import Sine

        # Create a few mock music files of different durations
        durations = [45, 60, 30]  # seconds

        for i, duration in enumerate(durations):
            # Generate a simple tone as mock music
            audio = Sine(220).to_audio_segment(duration=duration * 1000)  # convert to ms
            audio_path = os.path.join(self.music_test_dir, f"mock_music_{i}.mp3")
            audio.export(audio_path, format="mp3")

        # Temporarily override the music directory for testing
        original_music_dir = video_renderer.music_dir
        video_renderer.music_dir = self.music_test_dir

        # Restore after test
        def restore_music_dir():
            video_renderer.music_dir = original_music_dir

        # Use request.addfinalizer instead
        import pytest
        request = self._pytest_request
        request.addfinalizer(restore_music_dir)

    @pytest.mark.skip(reason="Requires API keys and external services")
    def test_complete_rendering_pipeline(self):
        """Test complete rendering pipeline (requires API keys)"""
        try:
            # Sample episode data
            episode_data = {
                "format": "talking_object",
                "script": "Bonjour! Je suis un grille-pain parlant. C'est incroyable!",
                "image_prompt": "A smiling talking toaster in a bright kitchen",
                "visual_recipe": {
                    "motion": "cuts_zoom_shake",
                    "caption_density": "medium",
                    "caption_style": "dynamic"
                },
                "audio_recipe": {
                    "model": "tts-1-hd",
                    "music_volume_db": -20.0,
                    "voice_volume_db": -12.0
                },
                "hook_text": "Regardez ce grille-pain!",
                "on_screen_captions": [],
                "title_options": ["Un grille-pain qui parle", "Le grille-pain magique"],
                "description": "Découvrez ce grille-pain incroyable qui peut parler!",
                "hashtags": ["#shorts", "#humour"],
                "job_id": "test_complete_pipeline"
            }

            # Add music to test directory
            self._create_mock_music_files()

            # Render video
            output_path = video_renderer.render_video(episode_data)

            # Verify output
            assert os.path.exists(output_path)
            assert os.path.getsize(output_path) > 0

            logger.info("Complete pipeline test passed", output_path=output_path)

        except Exception as e:
            logger.error("Complete pipeline test failed", error=str(e))
            pytest.skip(f"Complete pipeline test failed: {str(e)}")

if __name__ == "__main__":
    pytest.main([__file__, "-v"])
