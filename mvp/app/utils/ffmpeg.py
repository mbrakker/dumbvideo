"""
FFmpeg Utility Module

Handles video rendering with FFmpeg on Windows
"""

import os
import subprocess
import json
from typing import List, Dict, Optional, Tuple
import tempfile
import platform
from app.utils.logging import get_logger
import ffmpeg as ff

logger = get_logger(__name__)

class FFmpegError(Exception):
    """Custom exception for FFmpeg operations"""
    pass

class FFmpegWrapper:
    def __init__(self, ffmpeg_path: str = None):
        self.ffmpeg_path = ffmpeg_path or self._auto_detect_ffmpeg()
        self.logger = get_logger(f"{__name__}.FFmpegWrapper")

        if not self.ffmpeg_path:
            raise FFmpegError("FFmpeg not found. Please install FFmpeg and set FFMPEG_PATH in .env")

        self.logger.info("FFmpeg initialized", path=self.ffmpeg_path)

    def _auto_detect_ffmpeg(self) -> Optional[str]:
        """Auto-detect FFmpeg installation"""
        system = platform.system()

        if system == "Windows":
            # Common Windows installation paths
            possible_paths = [
                "C:\\ffmpeg\\bin\\ffmpeg.exe",
                "C:\\Program Files\\ffmpeg\\bin\\ffmpeg.exe",
                "C:\\Program Files (x86)\\ffmpeg\\bin\\ffmpeg.exe",
                "ffmpeg.exe"  # System PATH
            ]

            # Add winget installation path
            winget_path = os.path.expandvars("%LOCALAPPDATA%\\Microsoft\\WinGet\\Packages\\Gyan.FFmpeg_Microsoft.Winget.Source_8wekyb3d8bbwe\\ffmpeg-*\\bin\\ffmpeg.exe")
            possible_paths.insert(0, winget_path)

        else:
            # Linux/macOS
            possible_paths = ["ffmpeg", "/usr/bin/ffmpeg", "/usr/local/bin/ffmpeg"]

        for path in possible_paths:
            if os.path.exists(path) or (not os.path.sep in path and self._check_command_available(path)):
                return path
        return None

    def _check_command_available(self, command: str) -> bool:
        """Check if command is available in system PATH"""
        try:
            result = subprocess.run(
                [command, "-version"],
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                shell=True
            )
            return result.returncode == 0
        except:
            return False

    def verify_dependencies(self) -> Dict:
        """Verify that all required dependencies are available"""
        try:
            # Check FFmpeg availability
            ffmpeg_check = self._check_command_available(self.ffmpeg_path)

            # Check for common codecs and features
            result = subprocess.run(
                [self.ffmpeg_path, "-codecs"],
                capture_output=True,
                text=True,
                shell=True
            )

            required_codecs = ["libx264", "aac", "libmp3lame"]
            available_codecs = []

            for codec in required_codecs:
                if codec in result.stdout:
                    available_codecs.append(codec)

            return {
                "ffmpeg_available": ffmpeg_check,
                "ffmpeg_path": self.ffmpeg_path,
                "available_codecs": available_codecs,
                "missing_codecs": [c for c in required_codecs if c not in available_codecs],
                "status": "ready" if ffmpeg_check else "error"
            }
        except Exception as e:
            return {
                "ffmpeg_available": False,
                "error": str(e),
                "status": "error"
            }

    def render_video(
        self,
        image_path: str,
        audio_path: str,
        output_path: str,
        duration: float,
        resolution: Tuple[int, int] = (1080, 1920),
        fps: int = 30,
        motion_style: str = "cuts_zoom_shake",
        caption_file: str = None
    ) -> str:
        """
        Render video with image, audio, and optional captions

        Args:
            image_path: Path to input image
            audio_path: Path to audio file
            output_path: Output video path
            duration: Video duration in seconds
            resolution: (width, height) tuple
            fps: Frames per second
            motion_style: Motion effect style
            caption_file: Optional caption file (JSON format)
        """
        try:
            width, height = resolution

            video_stream = ff.input(image_path, loop=1, t=duration)
            audio_stream = ff.input(audio_path)

            # Basic video preparation
            video_stream = video_stream.filter("scale", width, height)
            video_stream = video_stream.filter("fps", fps=fps)
            video_stream = self._apply_motion(video_stream, motion_style, width, height, fps)

            # Add captions if provided
            if caption_file and os.path.exists(caption_file):
                video_stream = self._apply_captions(video_stream, caption_file)

            output = (
                ff
                .output(
                    video_stream,
                    audio_stream,
                    output_path,
                    vcodec="libx264",
                    acodec="aac",
                    pix_fmt="yuv420p",
                    movflags="+faststart",
                    t=duration,
                    shortest=None
                )
                .global_args("-y")
                .global_args("-loglevel", "error")
            )

            self.logger.info("Starting video render", output=output_path, duration=duration)
            output.run(overwrite_output=True)
            self.logger.info("Video render completed", output=output_path)

            return output_path

        except Exception as e:
            self.logger.error("Unexpected render error", error=str(e))
            raise FFmpegError(f"Unexpected error during rendering: {str(e)}")

    def _apply_motion(
        self,
        video_stream,
        motion_style: str,
        width: int,
        height: int,
        fps: int
    ):
        """Apply simple motion presets to a video stream"""
        try:
            if motion_style == "cuts_zoom_shake":
                # Gentle zoom effect with slight movement
                video_stream = video_stream.filter(
                    "zoompan",
                    z="min(zoom+0.002,1.2)",
                    d=1,
                    x="iw/2-(iw/zoom/2)",
                    y="ih/2-(ih/zoom/2)",
                    s=f"{width}x{height}"
                )
            elif motion_style == "ken_burns":
                video_stream = video_stream.filter(
                    "zoompan",
                    z="min(zoom+0.0015,1.1)",
                    d=1,
                    x="iw/2-(iw/zoom/2)",
                    y="ih/2-(ih/zoom/2)",
                    s=f"{width}x{height}"
                )
            else:
                video_stream = video_stream.filter("scale", width, height)

            return video_stream
        except Exception as e:
            self.logger.error("Failed to apply motion", error=str(e))
            raise

    def _apply_captions(self, video_stream, caption_file: str):
        """Apply caption overlays using drawtext"""
        try:
            with open(caption_file, "r", encoding="utf-8") as f:
                captions = json.load(f)

            font_path = "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"
            font_exists = os.path.exists(font_path)

            for caption in captions:
                start_time = caption["start_ms"] / 1000
                end_time = caption["end_ms"] / 1000
                drawtext_kwargs = {
                    "text": caption["text"],
                    "fontcolor": "white",
                    "fontsize": 48,
                    "x": "(w-text_w)/2",
                    "y": "h-120",
                    "borderw": 3,
                    "bordercolor": "black",
                    "enable": f"between(t,{start_time},{end_time})",
                }

                if font_exists:
                    drawtext_kwargs["fontfile"] = font_path

                video_stream = video_stream.filter("drawtext", **drawtext_kwargs)

            return video_stream
        except Exception as e:
            self.logger.error("Failed to apply captions", error=str(e))
            raise FFmpegError(f"Caption rendering failed: {str(e)}")

    def mix_audio(
        self,
        voice_path: str,
        music_path: str,
        output_path: str,
        voice_volume: float = -12.0,
        music_volume: float = -20.0,
        ducking: bool = True
    ) -> str:
        """
        Mix voice and music with optional ducking

        Args:
            voice_path: Path to voice audio
            music_path: Path to music audio
            output_path: Output mixed audio path
            voice_volume: Voice volume in dB
            music_volume: Music volume in dB
            ducking: Apply sidechain compression
        """
        try:
            voice_input = ff.input(voice_path).audio.filter("volume", f"{voice_volume}dB")
            music_input = ff.input(music_path).audio.filter("volume", f"{music_volume}dB")

            if ducking:
                # Apply sidechain compression using the voice track as the sidechain input
                music_input = ffmpeg.filter(
                    [music_input, voice_input],
                    "sidechaincompress",
                    threshold=0.05,
                    ratio=4,
                    attack=5,
                    release=250
                )

            mixed_audio = ffmpeg.filter(
                [voice_input, music_input],
                "amix",
                inputs=2,
                duration="shortest",
                dropout_transition=0
            )

            output = (
                ffmpeg
                .output(
                    mixed_audio,
                    output_path,
                    acodec="aac",
                    audio_bitrate="192k"
                )
                .global_args("-y")
                .global_args("-loglevel", "error")
            )

            self.logger.info("Mixing audio", voice=voice_path, music=music_path)
            output.run(overwrite_output=True)
            self.logger.info("Audio mixing completed", output=output_path)

            return output_path

        except Exception as e:
            self.logger.error("Audio mixing failed", error=str(e))
            raise FFmpegError(f"Audio mixing failed: {str(e)}")

    def get_ffmpeg_info(self) -> Dict:
        """Get FFmpeg version and capabilities"""
        try:
            result = subprocess.run(
                [self.ffmpeg_path, "-version"],
                capture_output=True,
                text=True
            )
            return {
                "version": result.stdout.split("\n")[0] if result.stdout else "Unknown",
                "available": True,
                "path": self.ffmpeg_path
            }
        except Exception as e:
            return {
                "version": "Unknown",
                "available": False,
                "error": str(e)
            }

    def format_error_message(self, error: Exception, context: Dict = None) -> str:
        """Format error messages consistently for logging"""
        context = context or {}
        error_type = type(error).__name__

        base_message = f"[{error_type}] {str(error)}"

        if context:
            context_details = ", ".join([f"{k}: {v}" for k, v in context.items()])
            return f"{base_message} | Context: {context_details}"
        return base_message

# Global FFmpeg instance
ffmpeg_wrapper = FFmpegWrapper()
