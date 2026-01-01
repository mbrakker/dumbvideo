"""
Time Utility Module

Handles timezone-aware scheduling and timing operations
"""

from datetime import datetime, timedelta, timezone
import pytz
import random
from typing import Tuple, Optional
from app.utils.logging import get_logger

logger = get_logger(__name__)

class TimeUtils:
    def __init__(self, timezone_str: str = "Europe/Paris"):
        self.timezone = pytz.timezone(timezone_str)
        self.logger = get_logger(f"{__name__}.TimeUtils")

    def get_current_time(self) -> datetime:
        """Get current time in configured timezone"""
        return datetime.now(self.timezone)

    def get_utc_time(self) -> datetime:
        """Get current UTC time"""
        return datetime.now(timezone.utc)

    def parse_time(self, time_str: str, timezone_str: Optional[str] = None) -> datetime:
        """Parse time string to timezone-aware datetime"""
        try:
            tz = pytz.timezone(timezone_str) if timezone_str else self.timezone
            return tz.localize(datetime.strptime(time_str, "%Y-%m-%d %H:%M:%S"))
        except Exception as e:
            self.logger.error("Failed to parse time", time_str=time_str, error=str(e))
            raise ValueError(f"Invalid time format: {time_str}")

    def random_time_in_window(
        self,
        start_hour: int = 12,
        end_hour: int = 20
    ) -> datetime:
        """
        Generate random time within scheduling window

        Args:
            start_hour: Start hour (0-23)
            end_hour: End hour (0-23)

        Returns:
            Random datetime within window
        """
        try:
            now = self.get_current_time()
            today = now.date()

            # Calculate window bounds
            start_time = self.timezone.localize(datetime(today.year, today.month, today.day, start_hour, 0, 0))
            end_time = self.timezone.localize(datetime(today.year, today.month, today.day, end_hour, 0, 0))

            # If we're past the window today, schedule for tomorrow
            if now > end_time:
                start_time += timedelta(days=1)
                end_time += timedelta(days=1)

            # Generate random time within window
            time_range = (end_time - start_time).total_seconds()
            random_seconds = random.uniform(0, time_range)
            random_time = start_time + timedelta(seconds=random_seconds)

            self.logger.debug("Generated random schedule time",
                           start_hour=start_hour,
                           end_hour=end_hour,
                           scheduled_time=random_time.isoformat())

            return random_time

        except Exception as e:
            self.logger.error("Failed to generate random time", error=str(e))
            raise

    def format_youtube_timestamp(self, dt: datetime) -> str:
        """Format datetime for YouTube API (ISO 8601)"""
        return dt.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.%fZ")

    def parse_youtube_timestamp(self, timestamp: str) -> datetime:
        """Parse YouTube API timestamp"""
        try:
            return datetime.strptime(timestamp, "%Y-%m-%dT%H:%M:%S.%fZ").replace(tzinfo=timezone.utc)
        except Exception as e:
            self.logger.error("Failed to parse YouTube timestamp", timestamp=timestamp, error=str(e))
            raise ValueError(f"Invalid YouTube timestamp: {timestamp}")

    def get_time_window(self, hours: int = 24) -> Tuple[datetime, datetime]:
        """Get time window for analytics"""
        now = self.get_current_time()
        start = now - timedelta(hours=hours)
        return start, now

    def format_duration(self, seconds: float) -> str:
        """Format duration in human-readable format"""
        if seconds < 60:
            return f"{seconds:.1f}s"
        elif seconds < 3600:
            minutes = int(seconds // 60)
            secs = int(seconds % 60)
            return f"{minutes}m {secs}s"
        else:
            hours = int(seconds // 3600)
            minutes = int((seconds % 3600) // 60)
            return f"{hours}h {minutes}m"

# Global time utils instance
time_utils = TimeUtils()
