#!/usr/bin/env python3
"""
Test script to verify FFmpeg rendering works
"""

import os
import sys
import tempfile

# Add the mvp directory to Python path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'mvp'))

from app.utils.ffmpeg_wrapper import FFmpegWrapper

def test_ffmpeg_render():
    """Test basic FFmpeg rendering"""
    try:
        # Initialize FFmpeg wrapper
        ffmpeg = FFmpegWrapper()
        print("FFmpeg initialized successfully")

        # Configure pydub to use our FFmpeg path
        from pydub import AudioSegment
        AudioSegment.converter = ffmpeg.ffmpeg_path
        AudioSegment.ffmpeg = ffmpeg.ffmpeg_path
        AudioSegment.ffprobe = ffmpeg.ffmpeg_path.replace("ffmpeg.exe", "ffprobe.exe")

        # Create a simple test image
        from PIL import Image, ImageDraw
        with tempfile.NamedTemporaryFile(suffix='.png', delete=False) as img_file:
            img = Image.new('RGB', (1080, 1920), color=(100, 100, 100))
            draw = ImageDraw.Draw(img)
            draw.text((50, 50), "Test Image", fill=(255, 255, 255))
            img.save(img_file.name)
            image_path = img_file.name

        # Create a simple test audio
        from pydub import AudioSegment
        from pydub.generators import Sine
        with tempfile.NamedTemporaryFile(suffix='.mp3', delete=False) as audio_file:
            sine_wave = Sine(440).to_audio_segment(duration=1000)
            sine_wave.export(audio_file.name, format="mp3")
            audio_path = audio_file.name

        # Test rendering
        with tempfile.NamedTemporaryFile(suffix='.mp4', delete=False) as output_file:
            output_path = output_file.name

        print(f"Rendering video: {image_path} + {audio_path} -> {output_path}")

        result = ffmpeg.render_video(
            image_path=image_path,
            audio_path=audio_path,
            output_path=output_path,
            duration=2.0,
            resolution=(1080, 1920),
            fps=30
        )

        print(f"Rendering successful: {result}")
        print(f"Output file exists: {os.path.exists(output_path)}")
        print(f"Output file size: {os.path.getsize(output_path) if os.path.exists(output_path) else 0} bytes")

        # Cleanup
        for path in [image_path, audio_path, output_path]:
            try:
                os.unlink(path)
            except:
                pass

        return True

    except Exception as e:
        print(f"Test failed: {e}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    print("FFmpeg Rendering Test")
    print("=" * 30)

    success = test_ffmpeg_render()

    if success:
        print("\n✓ FFmpeg rendering test passed!")
    else:
        print("\n✗ FFmpeg rendering test failed!")
