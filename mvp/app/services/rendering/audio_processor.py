"""
Audio Processor Service

Handles advanced audio processing for video rendering
"""

import os
import json
import tempfile
import subprocess
from typing import Dict, List, Optional, Tuple
from datetime import datetime
from app.utils.logging import get_logger
from app.utils.ffmpeg import FFmpegWrapper, FFmpegError
from pydub import AudioSegment
from pydub.effects import normalize, compress_dynamic_range
import numpy as np
import hashlib

logger = get_logger(__name__)

class AudioProcessingError(Exception):
    """Custom exception for audio processing failures"""
    pass

class AudioProcessor:
    def __init__(self):
        self.logger = get_logger(f"{__name__}.AudioProcessor")
        self.ffmpeg = FFmpegWrapper()

        # Configure pydub to use our FFmpeg path
        AudioSegment.converter = self.ffmpeg.ffmpeg_path
        AudioSegment.ffmpeg = self.ffmpeg.ffmpeg_path
        AudioSegment.ffprobe = self.ffmpeg.ffmpeg_path.replace("ffmpeg.exe", "ffprobe.exe")

        # Audio processing parameters
        self.sample_rate = 44100
        self.bitrate = "192k"
        self.target_lufs = -28.0  # YouTube recommended
        self.voice_volume = -12.0  # dB
        self.music_volume = -20.0  # dB

        # Temporary directory
        self.temp_dir = os.path.join("data", "temp")
        os.makedirs(self.temp_dir, exist_ok=True)

        self.logger.info("Audio processor initialized",
                       sample_rate=self.sample_rate,
                       target_lufs=self.target_lufs,
                       ffmpeg_path=self.ffmpeg.ffmpeg_path)

    def process_audio(self, voice_path: str, music_path: Optional[str] = None) -> str:
        """
        Complete audio processing pipeline

        Args:
            voice_path: Path to voice audio file
            music_path: Optional path to music file

        Returns:
            Path to processed audio file
        """
        start_time = datetime.now()
        job_id = hashlib.md5(voice_path.encode()).hexdigest()[:8]
        temp_dir = os.path.join(self.temp_dir, f"audio_{job_id}")
        os.makedirs(temp_dir, exist_ok=True)

        try:
            self.logger.info("Starting audio processing",
                           job_id=job_id,
                           voice=voice_path,
                           music=music_path)

            # Step 1: Load and normalize voice
            voice_processed = self._normalize_audio(voice_path, temp_dir)

            # Step 2: Process music if available
            music_processed = None
            if music_path and os.path.exists(music_path):
                music_processed = self._process_music(music_path, temp_dir)

            # Step 3: Mix audio tracks
            final_audio = self._mix_audio_tracks(voice_processed, music_processed, temp_dir)

            # Step 4: Apply final processing
            output_path = self._finalize_audio(final_audio, temp_dir)

            processing_time = (datetime.now() - start_time).total_seconds()
            self.logger.info("Audio processing completed",
                           job_id=job_id,
                           duration=processing_time,
                           output=output_path)

            return output_path

        except FileNotFoundError as e:
            self.logger.error("Audio processing failed - file not found", job_id=job_id, error=str(e))
            raise AudioProcessingError(f"Audio processing failed - file not found: {str(e)}")
        except Exception as e:
            self.logger.error("Audio processing failed", job_id=job_id, error=str(e))
            raise AudioProcessingError(f"Audio processing failed: {str(e)}")

    def _normalize_audio(self, audio_path: str, temp_dir: str) -> str:
        """Normalize audio to target LUFS"""
        try:
            output_path = os.path.join(temp_dir, "voice_normalized.mp3")

            # Load audio using pydub
            audio = AudioSegment.from_file(audio_path)

            # Normalize to target LUFS (simplified)
            normalized = normalize(audio, headroom=10)

            # Apply compression
            compressed = compress_dynamic_range(normalized, threshold=-20.0, ratio=4.0)

            # Export
            compressed.export(output_path, format="mp3", bitrate=self.bitrate)

            self.logger.debug("Normalized voice audio",
                            input=audio_path,
                            output=output_path)

            return output_path

        except Exception as e:
            self.logger.error("Failed to normalize audio", error=str(e))
            raise AudioProcessingError(f"Normalization failed: {str(e)}")

    def _process_music(self, music_path: str, temp_dir: str) -> str:
        """Process background music"""
        try:
            output_path = os.path.join(temp_dir, "music_processed.mp3")

            # Load music
            music = AudioSegment.from_file(music_path)

            # Apply processing
            processed = music - 10  # Reduce volume by 10dB
            processed = normalize(processed)

            # Export
            processed.export(output_path, format="mp3", bitrate=self.bitrate)

            self.logger.debug("Processed music",
                            input=music_path,
                            output=output_path)

            return output_path

        except Exception as e:
            self.logger.error("Failed to process music", error=str(e))
            raise AudioProcessingError(f"Music processing failed: {str(e)}")

    def _mix_audio_tracks(self, voice_path: str, music_path: Optional[str], temp_dir: str) -> str:
        """Mix voice and music tracks"""
        try:
            output_path = os.path.join(temp_dir, "mixed.mp3")

            # Load voice track
            voice = AudioSegment.from_file(voice_path)

            if music_path and os.path.exists(music_path):
                # Load and mix with music
                music = AudioSegment.from_file(music_path)

                # Ensure same length
                if len(music) > len(voice):
                    music = music[:len(voice)]
                else:
                    music = music.append(AudioSegment.silent(duration=len(voice) - len(music)))

                # Apply ducking effect (simple version)
                mixed = voice.overlay(music - 15)  # Music 15dB quieter when voice is present
            else:
                # No music, just use voice
                mixed = voice

            # Export mixed audio
            mixed.export(output_path, format="mp3", bitrate=self.bitrate)

            self.logger.debug("Mixed audio tracks",
                            voice=voice_path,
                            music=music_path,
                            output=output_path)

            return output_path

        except Exception as e:
            self.logger.error("Failed to mix audio tracks", error=str(e))
            raise AudioProcessingError(f"Audio mixing failed: {str(e)}")

    def _finalize_audio(self, audio_path: str, temp_dir: str) -> str:
        """Apply final audio processing"""
        try:
            output_path = os.path.join(temp_dir, "final_audio.mp3")

            # Load audio
            audio = AudioSegment.from_file(audio_path)

            # Apply final normalization
            final = normalize(audio)

            # Export with high quality
            final.export(output_path, format="mp3", bitrate="320k")

            self.logger.debug("Finalized audio",
                            input=audio_path,
                            output=output_path)

            return output_path

        except Exception as e:
            self.logger.error("Failed to finalize audio", error=str(e))
            raise AudioProcessingError(f"Finalization failed: {str(e)}")

    def generate_silence(self, duration: float, output_path: str) -> str:
        """Generate silent audio track"""
        try:
            silence = AudioSegment.silent(duration=duration * 1000)
            silence.export(output_path, format="mp3", bitrate=self.bitrate)

            self.logger.debug("Generated silence",
                            duration=duration,
                            output=output_path)

            return output_path

        except Exception as e:
            self.logger.error("Failed to generate silence", error=str(e))
            raise AudioProcessingError(f"Silence generation failed: {str(e)}")

    def apply_audio_effects(self, audio_path: str, effects: Dict) -> str:
        """
        Apply various audio effects

        Args:
            audio_path: Input audio file
            effects: Dictionary of effects to apply

        Returns:
            Path to processed audio file
        """
        try:
            output_path = audio_path.replace('.mp3', '_effects.mp3')
            audio = AudioSegment.from_file(audio_path)

            # Apply effects
            if effects.get('pitch_shift'):
                # Simple pitch shift simulation
                new_sample_rate = int(self.sample_rate * effects['pitch_shift'])
                audio = audio._spawn(audio.raw_data, overrides={'frame_rate': new_sample_rate})
                audio = audio.set_frame_rate(self.sample_rate)

            if effects.get('speed'):
                # Speed adjustment
                audio = audio.speedup(playback_speed=effects['speed'])

            if effects.get('reverb'):
                # Simple reverb simulation
                reverb = audio - 15  # Quieter
                delay = 200  # ms
                audio = audio.overlay(reverb, position=delay)

            # Export
            audio.export(output_path, format="mp3", bitrate=self.bitrate)

            self.logger.debug("Applied audio effects",
                            input=audio_path,
                            effects=effects,
                            output=output_path)

            return output_path

        except Exception as e:
            self.logger.error("Failed to apply audio effects", error=str(e))
            raise AudioProcessingError(f"Effects application failed: {str(e)}")

    def get_audio_info(self, audio_path: str) -> Dict:
        """Get detailed audio file information"""
        try:
            audio = AudioSegment.from_file(audio_path)

            return {
                "duration": len(audio) / 1000,  # seconds
                "sample_rate": audio.frame_rate,
                "channels": audio.channels,
                "sample_width": audio.sample_width,
                "dBFS": audio.dBFS,
                "max_dBFS": audio.max_dBFS,
                "format": "mp3"
            }

        except Exception as e:
            self.logger.error("Failed to get audio info", error=str(e))
            return {
                "error": str(e)
            }

    def convert_audio_format(self, input_path: str, output_format: str) -> str:
        """Convert audio to different format"""
        try:
            output_path = input_path.replace('.mp3', f'.{output_format}')

            # Use FFmpeg for conversion
            cmd = [
                self.ffmpeg.ffmpeg_path,
                '-i', input_path,
                '-c:a', 'aac' if output_format == 'm4a' else output_format,
                '-b:a', self.bitrate,
                output_path
            ]

            subprocess.run(cmd, check=True, capture_output=True)

            self.logger.debug("Converted audio format",
                            input=input_path,
                            output=output_path,
                            format=output_format)

            return output_path

        except Exception as e:
            self.logger.error("Failed to convert audio format", error=str(e))
            raise AudioProcessingError(f"Format conversion failed: {str(e)}")

# Global audio processor instance
audio_processor = AudioProcessor()
