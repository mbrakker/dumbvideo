#!/usr/bin/env python3
"""
Test FFmpeg import
"""

import ffmpeg as ff

print("FFmpeg imported successfully")
print(f"ff.input: {hasattr(ff, 'input')}")
print(f"ff.output: {hasattr(ff, 'output')}")
print(f"ff.filter: {hasattr(ff, 'filter')}")

try:
    # Test basic functionality
    stream = ff.input("dummy.mp4")
    print("ff.input works")
except Exception as e:
    print(f"ff.input failed: {e}")

print("Test completed")
