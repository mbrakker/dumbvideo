"""
Video Renderer Service

Handles complete video rendering pipeline using FFmpeg
"""

import os
import json
import tempfile
import subprocess
from typing import Dict, List, Optional, Tuple
from datetime import datetime
from app.utils.logging import get_logger
from app.utils.ffmpeg import FFmpegWrapper, FFmpegError
from app.config.schema import VideoFormat
from app.db.models import Job, VideoStatus
import uuid
import hashlib

logger = get_logger(__name__)

class RenderingError(Exception):
    """Custom exception for rendering failures"""
    pass

class VideoRenderer:
    def __init__(self):
        self.logger = get_logger(f"{__name__}.VideoRenderer")
        self.ffmpeg = FFmpegWrapper()

        # Configure pydub to use our FFmpeg path
        from pydub import AudioSegment
        AudioSegment.converter = self.ffmpeg.ffmpeg_path
        AudioSegment.ffmpeg = self.ffmpeg.ffmpeg_path
        AudioSegment.ffprobe = self.ffmpeg.ffmpeg_path.replace("ffmpeg.exe", "ffprobe.exe")

        # Rendering parameters
        self.default_resolution = (1080, 1920)  # 9:16 aspect ratio
        self.default_fps = 30
        self.default_duration = 7  # seconds

        # Asset paths
        self.font_path = os.path.join("data", "assets", "fonts", "arial.ttf")
        self.music_dir = os.path.join("data", "assets", "music")
        self.temp_dir = os.path.join("data", "temp")
        self.output_dir = os.path.join("data", "outputs")

        # Ensure directories exist
        os.makedirs(self.temp_dir, exist_ok=True)
        os.makedirs(self.output_dir, exist_ok=True)

        self.logger.info("Video renderer initialized",
                       resolution=self.default_resolution,
                       fps=self.default_fps,
                       duration=self.default_duration,
                       ffmpeg_path=self.ffmpeg.ffmpeg_path)

    def render_video(self, episode_data: Dict, episode: Dict = None, output_path: Optional[str] = None) -> str:
        """
        Complete video rendering pipeline

        Args:
            episode_data: Episode JSON data
            episode: Deprecated alias for episode_data (for backward compatibility)
            output_path: Optional custom output path

        Returns:
            Path to rendered video file
        """
        # Handle backward compatibility for incorrect parameter name
        if episode is not None:
            episode_data = episode

        start_time = datetime.now()
        job_id = str(uuid.uuid4())

        try:
            # Create temp directory for this job
            job_temp_dir = os.path.join(self.temp_dir, job_id)
            os.makedirs(job_temp_dir, exist_ok=True)

            self.logger.info("Starting video rendering",
                           job_id=job_id,
                           format=episode_data['format'])

            # Step 1: Generate image (simulated - would use DALL-E-3)
            image_path = self._generate_image(episode_data, job_temp_dir)

            # Step 2: Generate TTS audio (simulated - would use OpenAI TTS)
            audio_path = self._generate_tts_audio(episode_data, job_temp_dir)

            # Step 3: Generate captions file
            captions_path = self._generate_captions_file(episode_data, job_temp_dir)

            # Step 4: Mix audio with music
            mixed_audio_path = self._mix_audio(audio_path, job_temp_dir)

            # Step 5: Render final video
            final_output = output_path or os.path.join(
                self.output_dir,
                f"{job_id}.mp4"
            )

            self._render_final_video(
                image_path=image_path,
                audio_path=mixed_audio_path,
                captions_path=captions_path,
                output_path=final_output,
                episode_data=episode_data
            )

            # Clean up temp files
            self._cleanup_temp_files(job_temp_dir, [final_output])

            rendering_time = (datetime.now() - start_time).total_seconds()
            self.logger.info("Video rendering completed",
                           job_id=job_id,
                           duration=rendering_time,
                           output_path=final_output)

            return final_output

        except FileNotFoundError as e:
            self.logger.error("Video rendering failed - file not found", job_id=job_id, error=str(e))
            self._cleanup_temp_files(job_temp_dir)
            raise RenderingError(f"Rendering failed - file not found: {str(e)}")
        except Exception as e:
            self.logger.error("Video rendering failed", job_id=job_id, error=str(e))
            self._cleanup_temp_files(job_temp_dir)
            raise RenderingError(f"Rendering failed: {str(e)}")

    def _generate_image(self, episode_data: Dict, temp_dir: str) -> str:
        """Generate image for video (simulated)"""
        try:
            # In production, this would call DALL-E-3 API
            # For now, we'll create a placeholder image

            image_prompt = episode_data['image_prompt']
            prompt_hash = hashlib.md5(image_prompt.encode()).hexdigest()[:8]
            image_path = os.path.join(temp_dir, f"image_{prompt_hash}.png")

            # Create a simple placeholder image using PIL
            from PIL import Image, ImageDraw

            width, height = self.default_resolution
            img = Image.new('RGB', (width, height), color=(30, 30, 30))
            draw = ImageDraw.Draw(img)

            # Add some text to represent the image
            text = f"Image: {image_prompt[:50]}..."
            draw.text((50, height//2), text, fill=(255, 255, 255))

            img.save(image_path)

            self.logger.debug("Generated placeholder image",
                            path=image_path,
                            prompt_preview=image_prompt[:100])

            return image_path

        except Exception as e:
            self.logger.error("Failed to generate image", error=str(e))
            raise RenderingError(f"Image generation failed: {str(e)}")

    def _generate_tts_audio(self, episode_data: Dict, temp_dir: str) -> str:
        """Generate TTS audio for video (simulated)"""
        try:
            # In production, this would call OpenAI TTS API
            # For now, we'll create a placeholder audio file

            script = episode_data['script']
            script_hash = hashlib.md5(script.encode()).hexdigest()[:8]
            audio_path = os.path.join(temp_dir, f"voice_{script_hash}.mp3")

            # Create a simple silent audio file using pydub
            from pydub import AudioSegment
            from pydub.generators import Sine

            # Generate a simple tone to represent speech
            duration = self.default_duration * 1000  # milliseconds
            sine_wave = Sine(440).to_audio_segment(duration=duration)
            sine_wave.export(audio_path, format="mp3")

            self.logger.debug("Generated placeholder TTS audio",
                            path=audio_path,
                            script_preview=script[:100])

            return audio_path

        except Exception as e:
            self.logger.error("Failed to generate TTS audio", error=str(e))
            raise RenderingError(f"TTS generation failed: {str(e)}")

    def _generate_captions_file(self, episode_data: Dict, temp_dir: str) -> str:
        """Generate captions JSON file"""
        try:
            captions = episode_data['on_screen_captions']
            captions_path = os.path.join(temp_dir, "captions.json")

            # Convert to proper format for FFmpeg
            formatted_captions = []
            for caption in captions:
                formatted_captions.append({
                    "start_ms": caption['start_ms'],
                    "end_ms": caption['end_ms'],
                    "text": caption['text']
                })

            with open(captions_path, 'w', encoding='utf-8') as f:
                json.dump(formatted_captions, f, ensure_ascii=False, indent=2)

            self.logger.debug("Generated captions file",
                            path=captions_path,
                            caption_count=len(captions))

            return captions_path

        except Exception as e:
            self.logger.error("Failed to generate captions file", error=str(e))
            raise RenderingError(f"Captions generation failed: {str(e)}")

    def _mix_audio(self, voice_path: str, temp_dir: str) -> str:
        """Mix voice with background music"""
        try:
            mixed_audio_path = os.path.join(temp_dir, "mixed_audio.mp3")

            # Check if we have music files
            music_files = []
            if os.path.exists(self.music_dir):
                music_files = [f for f in os.listdir(self.music_dir) if f.endswith('.mp3')]

            if music_files:
                # Use the first music file found
                music_path = os.path.join(self.music_dir, music_files[0])

                # Mix using FFmpeg wrapper
                self.ffmpeg.mix_audio(
                    voice_path=voice_path,
                    music_path=music_path,
                    output_path=mixed_audio_path,
                    voice_volume=-12.0,
                    music_volume=-20.0,
                    ducking=True
                )
            else:
                # No music available, just copy voice
                import shutil
                shutil.copy(voice_path, mixed_audio_path)

            self.logger.debug("Mixed audio",
                            voice=voice_path,
                            music=music_files[0] if music_files else "none",
                            output=mixed_audio_path)

            return mixed_audio_path

        except Exception as e:
            self.logger.error("Failed to mix audio", error=str(e))
            raise RenderingError(f"Audio mixing failed: {str(e)}")

    def _render_final_video(self, image_path: str, audio_path: str, captions_path: str, output_path: str, episode_data: Dict):
        """Render final video with all elements"""
        try:
            # Get rendering parameters from episode data
            visual_recipe = episode_data['visual_recipe']
            motion_style = visual_recipe.get('motion', 'cuts_zoom_shake')
            duration = self.default_duration

            # Render using FFmpeg wrapper
            self.ffmpeg.render_video(
                image_path=image_path,
                audio_path=audio_path,
                output_path=output_path,
                duration=duration,
                resolution=self.default_resolution,
                fps=self.default_fps,
                motion_style=motion_style,
                caption_file=captions_path
            )

            self.logger.info("Rendered final video",
                           image=image_path,
                           audio=audio_path,
                           output=output_path,
                           motion_style=motion_style)

        except FFmpegError as e:
            self.logger.error("FFmpeg rendering failed", error=str(e))
            raise RenderingError(f"FFmpeg error: {str(e)}")
        except Exception as e:
            self.logger.error("Final video rendering failed", error=str(e))
            raise RenderingError(f"Final rendering failed: {str(e)}")

    def _cleanup_temp_files(self, temp_dir: str, keep_files: Optional[List[str]] = None):
        """Clean up temporary files"""
        try:
            keep_files = keep_files or []
            if os.path.exists(temp_dir):
                for filename in os.listdir(temp_dir):
                    file_path = os.path.join(temp_dir, filename)
                    if file_path not in keep_files:
                        try:
                            os.remove(file_path)
                        except:
                            pass
                try:
                    os.rmdir(temp_dir)
                except:
                    pass

            self.logger.debug("Cleaned up temp files", temp_dir=temp_dir)

        except Exception as e:
            self.logger.error("Failed to cleanup temp files", error=str(e))

    def generate_thumbnail(self, video_path: str, output_path: Optional[str] = None) -> str:
        """Generate thumbnail from video"""
        try:
            output_path = output_path or video_path.replace('.mp4', '_thumb.jpg')

            # Use FFmpeg to extract thumbnail
            cmd = [
                self.ffmpeg.ffmpeg_path,
                '-i', video_path,
                '-ss', '00:00:01',  # 1 second in
                '-vframes', '1',
                '-q:v', '2',  # Quality
                output_path
            ]

            subprocess.run(cmd, check=True, capture_output=True)

            self.logger.info("Generated thumbnail",
                           video=video_path,
                           thumbnail=output_path)

            return output_path

        except Exception as e:
            self.logger.error("Failed to generate thumbnail", error=str(e))
            raise RenderingError(f"Thumbnail generation failed: {str(e)}")

    def get_rendering_stats(self) -> Dict:
        """Get FFmpeg and system capabilities"""
        try:
            ffmpeg_info = self.ffmpeg.get_ffmpeg_info()

            return {
                "ffmpeg": ffmpeg_info,
                "supported_formats": ["talking_object", "absurd_motivation", "nothing_happens"],
                "default_resolution": self.default_resolution,
                "default_fps": self.default_fps,
                "default_duration": self.default_duration,
                "status": "ready"
            }

        except Exception as e:
            self.logger.error("Failed to get rendering stats", error=str(e))
            return {
                "status": "error",
                "error": str(e)
            }

# Global renderer instance
video_renderer = VideoRenderer()
