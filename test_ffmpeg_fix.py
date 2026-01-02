#!/usr/bin/env python3
"""
Test script to verify FFmpeg fixes
"""

import sys
import os

# Add the mvp directory to the path so we can import the modules
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'mvp'))

from app.utils.ffmpeg import FFmpegWrapper, ffmpeg_wrapper

def test_ffmpeg_detection():
    """Test FFmpeg auto-detection"""
    print("Testing FFmpeg auto-detection...")

    try:
        # Test the global instance
        print(f"FFmpeg path found: {ffmpeg_wrapper.ffmpeg_path}")
        print(f"FFmpeg exists: {os.path.exists(ffmpeg_wrapper.ffmpeg_path)}")

        # Test dependency verification
        deps = ffmpeg_wrapper.verify_dependencies()
        print(f"Dependency verification: {deps}")

        # Test FFmpeg info
        info = ffmpeg_wrapper.get_ffmpeg_info()
        print(f"FFmpeg info: {info}")

        # Test error formatting
        try:
            raise FileNotFoundError("Test file not found error")
        except FileNotFoundError as e:
            formatted = ffmpeg_wrapper.format_error_message(e, {"file": "test.mp3", "operation": "read"})
            print(f"Formatted error: {formatted}")

        print("✅ All tests passed!")
        return True

    except Exception as e:
        print(f"❌ Test failed: {e}")
        return False

if __name__ == "__main__":
    success = test_ffmpeg_detection()
    sys.exit(0 if success else 1)
