"""
FFmpeg service factory

Provides a lazy, cached FFmpegWrapper instance to avoid expensive work at import time.
"""

from functools import lru_cache
from typing import Optional

from app.utils.ffmpeg_wrapper import FFmpegError, FFmpegWrapper
from app.utils.logging import get_logger, log_event

logger = get_logger(__name__)


@lru_cache(maxsize=1)
def get_ffmpeg_wrapper(ffmpeg_path: Optional[str] = None) -> FFmpegWrapper:
    wrapper = FFmpegWrapper(ffmpeg_path=ffmpeg_path)
    readiness = wrapper.verify_dependencies()
    log_event(
        logger,
        role="service",
        event_type="ffmpeg_ready",
        message="FFmpeg wrapper initialized",
        context=readiness,
        level="info",
    )
    return wrapper

