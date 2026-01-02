#!/usr/bin/env python3
"""
Test FFmpeg wrapper directly
"""

import sys
import os

# Add the mvp directory to the path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'mvp'))

from app.utils.ffmpeg_wrapper import FFmpegWrapper

def test_ffmpeg_wrapper():
    """Test FFmpeg wrapper"""
    print("Testing FFmpeg wrapper...")

    try:
        wrapper = FFmpegWrapper()
        print(f"FFmpeg path: {wrapper.ffmpeg_path}")

        # Test dependency verification
        deps = wrapper.verify_dependencies()
        print(f"Dependencies: {deps}")

        print("✅ FFmpeg wrapper test passed!")
        return True

    except Exception as e:
        print(f"❌ FFmpeg wrapper test failed: {e}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    success = test_ffmpeg_wrapper()
    sys.exit(0 if success else 1)
