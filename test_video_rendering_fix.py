#!/usr/bin/env python3
"""
Test script to verify the video rendering fix
"""

import os
import sys
import json
import tempfile
from datetime import datetime

# Add project root to path
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

# Add mvp directory to path for proper imports
sys.path.append(os.path.join(os.path.dirname(os.path.abspath(__file__)), "mvp"))

from app.services.rendering.video_renderer import VideoRenderer
from app.config.schema import VideoFormat

def create_test_episode_data():
    """Create minimal test episode data"""
    return {
        "format": VideoFormat.TALKING_OBJECT.value,
        "language": "fr-FR",
        "hook_text": "Test hook",
        "script": "This is a test script for video rendering verification.",
        "on_screen_captions": [
            {"start_ms": 0, "end_ms": 2000, "text": "Test caption 1"},
            {"start_ms": 2000, "end_ms": 4000, "text": "Test caption 2"}
        ],
        "title_options": ["Test Title 1", "Test Title 2", "Test Title 3"],
        "description": "Test video description",
        "hashtags": ["#test", "#video"],
        "image_prompt": "A simple test image with blue background",
        "visual_recipe": {
            "motion": "cuts_zoom_shake",
            "color_preset": "vibrant",
            "caption_style": "dynamic",
            "font": "Arial"
        },
        "audio_recipe": {
            "voice_preset": "friendly_french_male",
            "music_track_id": "test_music",
            "music_lufs_target": -28
        }
    }

def test_render_video_with_correct_parameters():
    """Test that render_video works with correct parameter passing"""
    print("Testing VideoRenderer.render_video() with correct parameters...")

    renderer = VideoRenderer()
    episode_data = create_test_episode_data()

    # Test with explicit episode_data parameter (correct way)
    try:
        with tempfile.NamedTemporaryFile(suffix='.mp4', delete=False) as tmp_file:
            output_path = tmp_file.name

        video_path = renderer.render_video(
            episode_data=episode_data,
            output_path=output_path
        )

        print(f"✅ SUCCESS: Video rendered successfully to {video_path}")
        print(f"   File exists: {os.path.exists(video_path)}")
        print(f"   File size: {os.path.getsize(video_path)} bytes")

        # Cleanup
        if os.path.exists(video_path):
            os.remove(video_path)

        return True

    except Exception as e:
        print(f"❌ FAILED: {str(e)}")
        return False

def test_render_video_with_wrong_parameters():
    """Test that render_video fails with incorrect parameter passing"""
    print("\nTesting VideoRenderer.render_video() with incorrect parameters...")

    renderer = VideoRenderer()
    episode_data = create_test_episode_data()

    # Test with format parameter (incorrect way - should fail)
    try:
        with tempfile.NamedTemporaryFile(suffix='.mp4', delete=False) as tmp_file:
            output_path = tmp_file.name

        video_path = renderer.render_video(
            episode_data=episode_data,
            output_path=output_path,
            format=VideoFormat.TALKING_OBJECT.value  # This should cause the error
        )

        print(f"❌ UNEXPECTED: Video rendered successfully (should have failed)")
        return False

    except TypeError as e:
        if "unexpected keyword argument 'format'" in str(e):
            print(f"✅ EXPECTED FAILURE: {str(e)}")
            return True
        else:
            print(f"❌ UNEXPECTED ERROR: {str(e)}")
            return False
    except Exception as e:
        print(f"❌ UNEXPECTED ERROR: {str(e)}")
        return False

def main():
    """Run all tests"""
    print("=" * 60)
    print("VIDEO RENDERING FIX VERIFICATION")
    print("=" * 60)

    # Test correct parameter passing
    correct_test_passed = test_render_video_with_correct_parameters()

    # Test incorrect parameter passing
    incorrect_test_passed = test_render_video_with_wrong_parameters()

    print("\n" + "=" * 60)
    print("TEST RESULTS")
    print("=" * 60)
    print(f"Correct parameters test: {'PASSED' if correct_test_passed else 'FAILED'}")
    print(f"Incorrect parameters test: {'PASSED' if incorrect_test_passed else 'FAILED'}")

    if correct_test_passed and incorrect_test_passed:
        print("\n🎉 ALL TESTS PASSED - Fix is working correctly!")
        return 0
    else:
        print("\n💥 SOME TESTS FAILED - Fix needs review")
        return 1

if __name__ == "__main__":
    sys.exit(main())
