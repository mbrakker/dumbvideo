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
import ffmpeg

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

            # Create filter graph based on motion style
            filter_graph = self._build_filter_graph(
                image_path, duration, width, height, motion_style, caption_file
            )

            # Build FFmpeg command
            cmd = (
                ffmpeg
                .input(image_path, loop=1, framerate=fps)
                .input(audio_path)
                .filter("scale", width, height)
                .filter_multimedia("fps", fps=fps)
                .filter_multimedia("setpts", "N/FR/TB")  # Normalize timing
                .filter_multimedia(filter_graph)
                .output(
                    output_path,
                    vcodec="libx264",
                    acodec="aac",
                    pix_fmt="yuv420p",
                    movflags="+faststart",
                    t=duration,
                    shortest=None
                )
                .global_args("-y")  # Overwrite output
                .global_args("-loglevel", "error")
            )

            # Execute command
            self.logger.info("Starting video render", output=output_path, duration=duration)
            cmd.run(overwrite_output=True)
            self.logger.info("Video render completed", output=output_path)

            return output_path

        except ffmpeg.Error as e:
            self.logger.error("FFmpeg render failed", error=str(e), image=image_path, audio=audio_path)
            raise FFmpegError(f"Video rendering failed: {str(e)}")
        except Exception as e:
            self.logger.error("Unexpected render error", error=str(e))
            raise FFmpegError(f"Unexpected error during rendering: {str(e)}")

    def _build_filter_graph(
        self,
        image_path: str,
        duration: float,
        width: int,
        height: int,
        motion_style: str,
        caption_file: str = None
    ) -> str:
        """Build FFmpeg filter graph for motion effects"""
        filters = []

        # Motion effects based on style
        if motion_style == "cuts_zoom_shake":
            # Fast cuts with zoom and shake effects
            filters.extend([
                "[0:v]zoompan=z='min(zoom+0.0015,1.5)':d=1:x='iw/2-(iw/zoom/2)':y='ih/2-(ih/zoom/2)':s=1080x1920[zoom]",
                "[zoom]split=3[z1][z2][z3]",
                "[z1]trim=0:2,setpts=PTS-STARTPTS[cut1]",
                "[z2]trim=2:4,setpts=PTS-STARTPTS,eq=random=1[cut2]",
                "[z3]trim=4:6,setpts=PTS-STARTPTS,eq=random=1[cut3]",
                "[cut1][cut2][cut3]concat=n=3:v=1:a=0[video]"
            ])
        elif motion_style == "ken_burns":
            # Ken Burns effect
            filters.extend([
                "[0:v]zoompan=z='min(zoom+0.001,1.2)':d=1:x='iw/2-(iw/zoom/2)':y='ih/2-(ih/zoom/2)':s=1080x1920[video]"
            ])
        else:  # static
            filters.append("[0:v]scale=1080:1920[video]")

        # Add captions if provided
        if caption_file and os.path.exists(caption_file):
            with open(caption_file, 'r') as f:
                captions = json.load(f)

            caption_filters = []
            for i, caption in enumerate(captions):
                start_time = caption['start_ms'] / 1000
                end_time = caption['end_ms'] / 1000
                text = caption['text'].replace("'", "\\'")

                caption_filters.extend([
                    f"[video]drawtext=fontfile=/path/to/font.ttf:text='{text}':"
                    f"fontcolor=white:fontsize=48:x=(w-text_w)/2:y=h-100:"
                    f"enable='between(t,{start_time},{end_time})':"
                    f"borderw=3:bordercolor=black[caption{i}]"
                ])

            if caption_filters:
                filters.extend(caption_filters)
                filters.append(f"[caption{len(captions)-1}]")

        return "".join(filters)

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
            # Build audio mixing command
            cmd = (
                ffmpeg
                .input(voice_path)
                .input(music_path)
            )

            if ducking:
                # Apply sidechain compression for ducking
                cmd = cmd.filter(
                    ["sidechaincompress", "threshold=0.01", "ratio=4", "attack=0.1", "release=0.3"]
                )

            # Mix and adjust volumes
            cmd = (
                cmd
                .filter_multimedia("amix", inputs=2)
                .filter_multimedia("volume", volume=voice_volume)
                .filter_multimedia("volume", volume=music_volume)
                .output(
                    output_path,
                    acodec="aac",
                    audio_bitrate="192k"
                )
                .global_args("-y")
                .global_args("-loglevel", "error")
            )

            self.logger.info("Mixing audio", voice=voice_path, music=music_path)
            cmd.run(overwrite_output=True)
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

# Global FFmpeg instance
ffmpeg_wrapper = FFmpegWrapper()
