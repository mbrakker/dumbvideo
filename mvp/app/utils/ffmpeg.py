"""
FFmpeg Module - Global FFmpeg Wrapper Instance

This module provides a global FFmpegWrapper instance for easy access
throughout the application.
"""

from app.utils.ffmpeg_wrapper import FFmpegWrapper

# Create global FFmpeg wrapper instance
ffmpeg_wrapper = FFmpegWrapper()

# Export the wrapper for easy import
__all__ = ['ffmpeg_wrapper']
