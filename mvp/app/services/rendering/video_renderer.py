"""
Video Renderer Generator

Handles complete video rendering pipeline using FFmpeg
Coordinates asset generation and rendering
"""

import os
import json
import tempfile
import subprocess
from typing import Dict, List, Optional, Tuple
from datetime import datetime
from app.utils.logging import get_logger
from app.utils.ffmpeg_wrapper import FFmpegWrapper, FFmpegError
from app.config.schema import VideoFormat
from app.db.models import Job, VideoStatus

# Import services
from app.services.rendering.image_service import ImageService, ImageGenerationError
from app.services.rendering.tts_service import TTSService, TTSGenerationError
from app.contracts.image import ImageGenerationRequest, ImageFallbackRequest
from app.contracts.audio import TTSGenerationRequest, MusicValidationRequest

# Import contracts
import uuid
import hashlib
import random

logger = get_logger(__name__)

class RenderingError(Exception):
    """Custom exception for rendering failures"""
    pass

class VideoRenderer:
    def __init__(self):
        self.logger = get_logger(f"{__name__}.VideoRenderer")
        self.ffmpeg = FFmpegWrapper()

        # Initialize services
        self.image_service = ImageService()
        self.tts_service = TTSService()

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
        os.makedirs(self.music_dir, exist_ok=True)

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
        """Generate image for video using DALL·E service"""
        try:
            image_prompt = episode_data['image_prompt']
            job_id = episode_data.get('job_id', 'unknown')

            # Create image generation request
            request = ImageGenerationRequest(
                prompt=image_prompt,
                model="dall-e-3",
                size="1792x1024",  # Optimal for 9:16 cropping
                quality="standard",
                style="vivid",
                request_id=job_id
            )

            # Try DALL·E generation first
            response = self.image_service.generate_image(request)

            if response.error:
                # Fallback to gradient image
                self.logger.warning("DALL·E failed, using fallback image",
                                  error=response.error,
                                  request_id=job_id)

                fallback_request = ImageFallbackRequest(
                    text=image_prompt[:100],  # Use prompt as text
                    width=self.default_resolution[0],
                    height=self.default_resolution[1],
                    style="gradient",
                    request_id=job_id
                )

                fallback_response = self.image_service.generate_fallback_image(fallback_request)
                image_data = fallback_response.image_data

                self.logger.info("Generated fallback image",
                               request_id=job_id,
                               style=fallback_request.style)
            else:
                image_data = response.image_data
                self.logger.info("Generated DALL·E image",
                               request_id=job_id,
                               cost_credits=response.cost_credits,
                               image_url=response.image_url)

            # Save image to temp file
            prompt_hash = hashlib.md5(image_prompt.encode()).hexdigest()[:8]
            image_path = os.path.join(temp_dir, f"image_{prompt_hash}.png")

            with open(image_path, 'wb') as f:
                f.write(image_data)

            self.logger.debug("Saved image asset",
                            path=image_path,
                            size=len(image_data),
                            request_id=job_id)

            return image_path

        except ImageGenerationError as e:
            self.logger.error("Image generation service failed", error=str(e))
            raise RenderingError(f"Image generation failed: {str(e)}")
        except Exception as e:
            self.logger.error("Failed to generate image", error=str(e))
            raise RenderingError(f"Image generation failed: {str(e)}")

    def _generate_tts_audio(self, episode_data: Dict, temp_dir: str) -> str:
        """Generate TTS audio for video using OpenAI TTS service"""
        try:
            script = episode_data['script']
            job_id = episode_data.get('job_id', 'unknown')
            episode_format = episode_data.get('format', '')

            # Select appropriate voice based on episode format
            voice = self.tts_service.select_voice_for_episode(episode_format)

            # Use seeded randomness for reproducible but varied voice characteristics
            seed = hashlib.md5(f"{job_id}_{episode_format}".encode()).hexdigest()
            seed_int = int(seed[:8], 16) % 1000000

            # Create TTS request with speech parameters from audio_recipe
            audio_recipe = episode_data.get('audio_recipe', {})
            model = audio_recipe.get('model', 'tts-1-hd')
            speed = audio_recipe.get('speed', 1.0)

            request = TTSGenerationRequest(
                text=script,
                model=model,
                voice=voice,
                speed=speed,
                seed=seed_int,
                request_id=job_id
            )

            # Generate TTS audio
            response = self.tts_service.generate_speech(request)

            if response.error:
                self.logger.error("TTS generation failed",
                                error=response.error,
                                request_id=job_id)
                raise RenderingError(f"TTS generation failed: {response.error}")

            # Save audio to temp file
            script_hash = hashlib.md5(script.encode()).hexdigest()[:8]
            audio_path = os.path.join(temp_dir, f"voice_{script_hash}.mp3")

            with open(audio_path, 'wb') as f:
                f.write(response.audio_data)

            self.logger.info("Generated TTS audio",
                           path=audio_path,
                           voice=response.voice_used,
                           model=response.model_used,
                           duration_seconds=response.duration_seconds,
                           cost_characters=response.cost_characters,
                           speed_actual=response.speed_actual,
                           request_id=job_id)

            return audio_path

        except TTSGenerationError as e:
            self.logger.error("TTS service failed", error=str(e))
            raise RenderingError(f"TTS generation failed: {str(e)}")
        except Exception as e:
            self.logger.error("Failed to generate TTS audio", error=str(e))
            raise RenderingError(f"TTS generation failed: {str(e)}")

    def _generate_captions_file(self, episode_data: Dict, temp_dir: str) -> str:
        """Generate captions JSON file with full script coverage and adaptive styling"""
        try:
            captions_path = os.path.join(temp_dir, "captions.json")

            # Get visual recipe for styling
            visual_recipe = episode_data.get('visual_recipe', {})
            caption_density = visual_recipe.get('caption_density', 'medium')  # 'sparse', 'medium', 'dense'
            caption_style = visual_recipe.get('caption_style', 'dynamic')  # 'dynamic', 'static'

            # Use provided captions or generate comprehensive ones from script
            provided_captions = episode_data.get('on_screen_captions', [])

            if provided_captions:
                # Use provided captions but enhance with styling
                captions = self._enhance_captions_with_styling(provided_captions, caption_density, caption_style)
            else:
                # Generate captions from script
                script = episode_data.get('script', '')
                estimated_duration = self.tts_service.get_estimated_duration(script)

                # Segment script into caption chunks based on density
                captions = self._segment_script_into_captions(
                    script,
                    estimated_duration,
                    caption_density,
                    caption_style
                )

            self.logger.debug("Generated comprehensive captions",
                            caption_count=len(captions),
                            density=caption_density,
                            style=caption_style)

            # Convert to proper format for FFmpeg with enhanced styling
            formatted_captions = []
            for caption in captions:
                # Add adaptive styling based on text length and position
                styled_caption = self._apply_adaptive_caption_styling(caption, self.default_resolution)
                formatted_captions.append(styled_caption)

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
        """Mix voice with background music with validation and warnings"""
        try:
            mixed_audio_path = os.path.join(temp_dir, "mixed_audio.mp3")

            # Validate music availability
            music_validation = self._validate_music_availability()

            if music_validation["music_available"]:
                # Select music track based on validation results
                selected_track = music_validation["selected_tracks"][0]
                music_path = os.path.join(self.music_dir, selected_track["filename"])

                self.logger.info("Using background music",
                               music_file=selected_track["filename"],
                               duration=selected_track.get("duration", "unknown"))

                # Get audio recipe parameters
                audio_recipe = {}  # This would come from episode_data in the future
                voice_volume = audio_recipe.get('voice_volume_db', -12.0)
                music_volume = audio_recipe.get('music_volume_db', -20.0)

                # Mix using FFmpeg wrapper with ducking
                self.ffmpeg.mix_audio(
                    voice_path=voice_path,
                    music_path=music_path,
                    output_path=mixed_audio_path,
                    voice_volume=voice_volume,
                    music_volume=music_volume,
                    ducking=True
                )

                self.logger.debug("Mixed audio with music",
                                voice=voice_path,
                                music=selected_track["filename"],
                                voice_volume=voice_volume,
                                music_volume=music_volume,
                                output=mixed_audio_path)

            else:
                # No music available - fail fast with warning
                warning_msg = "No background music available. Video will render without music. Please add MP3 files to data/assets/music/"
                self.logger.warning("Missing background music",
                                 music_dir=self.music_dir,
                                 status=music_validation["status"],
                                 total_tracks=music_validation["total_tracks"],
                                 valid_tracks=music_validation["valid_tracks"])

                # For now, copy voice only but log the warning
                # In production, this might raise an error instead
                import shutil
                shutil.copy(voice_path, mixed_audio_path)

                # Log for UI warnings (in a production system, this would be shown to user)
                self.logger.warning("Rendering without music - UI should display warning",
                                 warning=warning_msg)

            return mixed_audio_path

        except Exception as e:
            self.logger.error("Failed to mix audio", error=str(e))
            raise RenderingError(f"Audio mixing failed: {str(e)}")

    def _validate_music_availability(self) -> Dict:
        """Validate background music availability and quality"""
        try:
            validation_result = {
                "music_available": False,
                "total_tracks": 0,
                "valid_tracks": 0,
                "format_breakdown": {},
                "average_duration": 0.0,
                "average_lufs": -20.0,  # default
                "selected_tracks": [],
                "issues": [],
                "status": "no_music_directory"
            }

            if not os.path.exists(self.music_dir):
                validation_result["issues"].append(f"Music directory does not exist: {self.music_dir}")
                return validation_result

            # Scan for music files
            supported_formats = {".mp3", ".wav", ".m4a"}
            music_files = []

            for filename in os.listdir(self.music_dir):
                filepath = os.path.join(self.music_dir, filename)
                if os.path.isfile(filepath):
                    ext = os.path.splitext(filename)[1].lower()
                    if ext in supported_formats:
                        music_files.append(filepath)

            validation_result["total_tracks"] = len(music_files)
            validation_result["status"] = "no_music_files" if len(music_files) == 0 else "checking_files"

            if not music_files:
                validation_result["issues"].append("No supported music files found (.mp3, .wav, .m4a)")
                return validation_result

            # Validate and analyze tracks
            valid_tracks = []
            total_duration = 0.0

            for filepath in music_files:
                try:
                    filename = os.path.basename(filepath)
                    ext = os.path.splitext(filename)[1].lower()

                    # Basic validation using pydub
                    from pydub import AudioSegment
                    audio = AudioSegment.from_file(filepath)

                    track_info = {
                        "filename": filename,
                        "filepath": filepath,
                        "format": ext[1:],  # remove the dot
                        "duration": len(audio) / 1000.0,  # seconds
                        "sample_rate": audio.frame_rate,
                        "channels": audio.channels
                    }

                    # Check minimum duration (30+ seconds for looping/reuse)
                    if track_info["duration"] >= 30.0:
                        valid_tracks.append(track_info)
                        total_duration += track_info["duration"]

                        # Update format breakdown
                        fmt = track_info["format"]
                        validation_result["format_breakdown"][fmt] = validation_result["format_breakdown"].get(fmt, 0) + 1

                except Exception as e:
                    validation_result["issues"].append(f"Invalid track {os.path.basename(filepath)}: {str(e)}")

            validation_result["valid_tracks"] = len(valid_tracks)

            if not valid_tracks:
                validation_result["issues"].append("No valid music tracks found (must be 30+ seconds)")
                return validation_result

            # Select tracks for use (prefer mp3 for compatibility, then by duration)
            validation_result["music_available"] = True
            validation_result["status"] = "ready"
            validation_result["average_duration"] = total_duration / len(valid_tracks)

            # Sort by format preference (mp3 first), then duration
            format_priority = {"mp3": 0, "wav": 1, "m4a": 2}
            sorted_tracks = sorted(valid_tracks,
                                 key=lambda t: (format_priority.get(t["format"], 99), -t["duration"]))

            # Select up to 3 best tracks
            validation_result["selected_tracks"] = sorted_tracks[:3]

            self.logger.info("Music validation completed",
                           total_tracks=validation_result["total_tracks"],
                           valid_tracks=validation_result["valid_tracks"],
                           available=validation_result["music_available"],
                           best_track=validation_result["selected_tracks"][0]["filename"] if validation_result["selected_tracks"] else None)

            return validation_result

        except Exception as e:
            self.logger.error("Music validation failed", error=str(e))
            return {
                "music_available": False,
                "status": "validation_error",
                "error": str(e),
                "issues": [str(e)]
            }

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

    def _segment_script_into_captions(self, script: str, duration_seconds: float,
                                    density: str, style: str) -> List[Dict]:
        """Segment script text into caption chunks based on density"""
        try:
            words = script.split()

            # Calculate chunks based on density
            if density == 'sparse':
                words_per_caption = 8  # ~3-4 seconds per caption
            elif density == 'medium':
                words_per_caption = 6  # ~2-3 seconds per caption
            elif density == 'dense':
                words_per_caption = 4  # ~1-2 seconds per caption
            else:
                words_per_caption = 6

            # Create caption chunks
            captions = []
            start_time = 0
            duration_per_word = duration_seconds / len(words) if words else 1.0

            for i in range(0, len(words), words_per_caption):
                chunk_words = words[i:i + words_per_caption]
                chunk_text = " ".join(chunk_words)

                if chunk_words:
                    # Calculate timing (approximations)
                    word_count = len(chunk_words)
                    chunk_duration = word_count * duration_per_word

                    end_time = min(start_time + chunk_duration, duration_seconds)

                    captions.append({
                        "start_ms": int(start_time * 1000),
                        "end_ms": int(end_time * 1000),
                        "text": chunk_text.strip()
                    })

                    start_time = end_time

                    if start_time >= duration_seconds:
                        break

            # Ensure we don't exceed video duration
            total_duration = sum((c["end_ms"] - c["start_ms"]) / 1000.0 for c in captions)
            if total_duration > duration_seconds:
                # Scale down timings proportionally
                scale_factor = duration_seconds / total_duration
                current_time = 0
                for caption in captions:
                    duration = (caption["end_ms"] - caption["start_ms"]) / 1000.0 * scale_factor
                    caption["start_ms"] = int(current_time * 1000)
                    caption["end_ms"] = int((current_time + duration) * 1000)
                    current_time += duration

            return captions

        except Exception as e:
            self.logger.error("Failed to segment script into captions", error=str(e))
            # Return single caption as fallback
            return [{
                "start_ms": 0,
                "end_ms": int(duration_seconds * 1000),
                "text": script[:100] + "..." if len(script) > 100 else script
            }]

    def _enhance_captions_with_styling(self, captions: List[Dict],
                                      density: str, style: str) -> List[Dict]:
        """Enhance existing captions with additional styling metadata"""
        try:
            enhanced_captions = []

            for caption in captions:
                enhanced_caption = caption.copy()
                # Add styling hints for adaptive rendering
                enhanced_caption["_styling"] = {
                    "density": density,
                    "style": style,
                    "length": len(caption["text"]),
                    "word_count": len(caption["text"].split())
                }
                enhanced_captions.append(enhanced_caption)

            return enhanced_captions

        except Exception as e:
            self.logger.error("Failed to enhance captions", error=str(e))
            return captions

    def _apply_adaptive_caption_styling(self, caption: Dict,
                                      resolution: Tuple[int, int]) -> Dict:
        """Apply adaptive styling to caption based on resolution and content"""
        try:
            width, height = resolution
            text = caption["text"]
            text_length = len(text)
            word_count = len(text.split())

            # Base font size scaling with resolution
            base_font_size = min(width, height) / 1080 * 72  # Scale from 1080p reference

            # Adaptive sizing based on content
            if text_length > 80:  # Long text
                font_size = max(36, base_font_size * 0.8)
            elif text_length > 40:  # Medium text
                font_size = max(42, base_font_size * 0.9)
            else:  # Short text
                font_size = max(48, base_font_size)

            # Add styling hints for FFmpeg rendering
            styled_caption = {
                "start_ms": caption["start_ms"],
                "end_ms": caption["end_ms"],
                "text": text,
                "_render_config": {
                    "font_size": int(font_size),
                    "stroke_width": max(2, int(font_size * 0.05)),  # 5% of font size
                    "y_position": height - int(height * 0.15),  # 15% from bottom
                    "x_centering": "center",
                    "font_color": "white",
                    "stroke_color": "black",
                    "box": True,
                    "box_color": "black@0.5",  # Semi-transparent
                    "box_border_w": 4
                }
            }

            return styled_caption

        except Exception as e:
            self.logger.error("Failed to apply adaptive caption styling", error=str(e))
            # Return original caption as fallback
            return caption

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
