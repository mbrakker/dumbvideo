"""
Metrics Collector Service

Handles YouTube Analytics API integration and performance tracking
"""

import os
import json
import time
from typing import Dict, List, Optional, Tuple
from datetime import datetime, timedelta
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError
from app.utils.logging import get_logger
from app.db.models import Job, VideoMetric
from sqlalchemy.orm import Session
from app.services.youtube.youtube_auth import YouTubeAuth, YouTubeAuthError
import hashlib

logger = get_logger(__name__)

class MetricsError(Exception):
    """Custom exception for metrics collection failures"""
    pass

class MetricsCollector:
    def __init__(self):
        self.logger = get_logger(f"{__name__}.MetricsCollector")
        self.auth = YouTubeAuth()

        # Analytics parameters
        self.max_retries = 3
        self.retry_delay = 5

        self.logger.info("Metrics collector initialized",
                       max_retries=self.max_retries)

    def collect_video_metrics(self, session: Session, video_id: str, window: str = "24h") -> Dict:
        """
        Collect metrics for a specific video

        Args:
            session: Database session
            video_id: YouTube video ID
            window: Time window (24h, 72h, etc.)

        Returns:
            Dictionary with collected metrics
        """
        try:
            self.logger.info("Collecting metrics",
                           video_id=video_id,
                           window=window)

            # Get YouTube client
            youtube = self._get_authenticated_client()

            # Determine date range
            end_time = datetime.utcnow()
            if window == "24h":
                start_time = end_time - timedelta(hours=24)
            elif window == "72h":
                start_time = end_time - timedelta(hours=72)
            else:
                start_time = end_time - timedelta(hours=int(window))

            # Get metrics from YouTube API
            metrics = self._get_youtube_metrics(youtube, video_id, start_time, end_time)

            # Store metrics in database
            self._store_metrics(session, video_id, metrics, window)

            self.logger.info("Metrics collection completed",
                           video_id=video_id,
                           window=window,
                           views=metrics.get('views', 0))

            return metrics

        except Exception as e:
            self.logger.error("Metrics collection failed", error=str(e))
            raise MetricsError(f"Metrics collection failed: {str(e)}")

    def _get_authenticated_client(self):
        """Get authenticated YouTube Analytics client"""
        try:
            return self.auth.get_authenticated_client()
        except YouTubeAuthError as e:
            self.logger.error("Authentication failed", error=str(e))
            raise MetricsError(f"Authentication failed: {str(e)}")

    def _get_youtube_metrics(self, youtube, video_id: str, start_time: datetime, end_time: datetime) -> Dict:
        """Get metrics from YouTube Analytics API"""
        try:
            # Convert times to ISO format
            start_date = start_time.strftime("%Y-%m-%dT%H:%M:%SZ")
            end_date = end_time.strftime("%Y-%m-%dT%H:%M:%SZ")

            # Get metrics
            request = youtube.reports().query(
                ids=f"channel==MINE",
                startDate=start_date,
                endDate=end_date,
                metrics="views,likes,comments,averageViewDuration,averageViewPercentage",
                dimensions="video",
                filters=f"video=={video_id}",
                sort="video"
            )

            response = request.execute()

            # Parse response (simplified - would be more complex in production)
            if not response.get('rows'):
                return {
                    'views': 0,
                    'likes': 0,
                    'comments': 0,
                    'avg_view_duration': 0,
                    'avg_view_percentage': 0,
                    'subscribers_gained': 0
                }

            # Extract metrics from first row
            row = response['rows'][0]
            return {
                'views': int(row[0]),
                'likes': int(row[1]),
                'comments': int(row[2]),
                'avg_view_duration': float(row[3]),
                'avg_view_percentage': float(row[4]),
                'subscribers_gained': 0  # Would come from different report
            }

        except HttpError as e:
            error_details = json.loads(e.content.decode())
            self.logger.error("YouTube API error",
                            error=error_details,
                            status_code=e.resp.status)
            # Return zeros if API fails
            return {
                'views': 0,
                'likes': 0,
                'comments': 0,
                'avg_view_duration': 0,
                'avg_view_percentage': 0,
                'subscribers_gained': 0
            }
        except Exception as e:
            self.logger.error("Failed to get YouTube metrics", error=str(e))
            return {
                'views': 0,
                'likes': 0,
                'comments': 0,
                'avg_view_duration': 0,
                'avg_view_percentage': 0,
                'subscribers_gained': 0
            }

    def _store_metrics(self, session: Session, video_id: str, metrics: Dict, window: str):
        """Store metrics in database"""
        try:
            # Find the job for this video
            job = session.query(Job).filter_by(youtube_id=video_id).first()
            if not job:
                self.logger.warning("No job found for video", video_id=video_id)
                return

            # Create or update metrics record
            metric = session.query(VideoMetric).filter_by(
                job_id=job.id,
                window=window
            ).first()

            if metric:
                # Update existing record
                metric.views = metrics['views']
                metric.likes = metrics['likes']
                metric.comments = metrics['comments']
                metric.avg_view_duration = metrics['avg_view_duration']
                metric.avg_view_percentage = metrics['avg_view_percentage']
                metric.subscribers_gained = metrics['subscribers_gained']
                metric.timestamp = datetime.utcnow()
            else:
                # Create new record
                metric = VideoMetric(
                    job_id=job.id,
                    window=window,
                    views=metrics['views'],
                    likes=metrics['likes'],
                    comments=metrics['comments'],
                    avg_view_duration=metrics['avg_view_duration'],
                    avg_view_percentage=metrics['avg_view_percentage'],
                    subscribers_gained=metrics['subscribers_gained']
                )
                session.add(metric)

            session.commit()

            self.logger.debug("Stored metrics in database",
                            job_id=job.id,
                            window=window)

        except Exception as e:
            session.rollback()
            self.logger.error("Failed to store metrics", error=str(e))
            raise MetricsError(f"Metrics storage failed: {str(e)}")

    def calculate_performance_score(self, metrics: Dict) -> float:
        """
        Calculate performance score for optimization

        Args:
            metrics: Dictionary of video metrics

        Returns:
            Performance score (0-100)
        """
        try:
            # Simple scoring algorithm
            views = metrics.get('views', 0)
            avg_pct = metrics.get('avg_view_percentage', 0)
            likes = metrics.get('likes', 0)

            # Normalize metrics
            norm_views = min(views / 1000, 1.0)  # Cap at 1000 views
            norm_pct = avg_pct / 100  # Convert to 0-1 range
            norm_likes = min(likes / 100, 1.0)  # Cap at 100 likes

            # Calculate weighted score
            score = (
                0.55 * norm_pct +  # View percentage is most important
                0.25 * norm_views +  # Views matter
                0.20 * norm_likes   # Likes are nice to have
            )

            # Convert to 0-100 scale
            final_score = score * 100

            self.logger.debug("Calculated performance score",
                            score=final_score,
                            views=views,
                            avg_pct=avg_pct,
                            likes=likes)

            return final_score

        except Exception as e:
            self.logger.error("Failed to calculate performance score", error=str(e))
            return 0.0

    def get_format_performance(self, session: Session) -> Dict:
        """Get performance metrics by format"""
        try:
            from app.config.schema import VideoFormat

            # Get all completed jobs with metrics
            jobs = session.query(Job).filter(
                Job.status == "completed",
                Job.youtube_id.isnot(None)
            ).all()

            if not jobs:
                return {
                    fmt.value: {
                        "count": 0,
                        "avg_score": 0,
                        "avg_views": 0,
                        "avg_pct": 0
                    } for fmt in VideoFormat
                }

            # Calculate metrics by format
            format_metrics = {}
            for fmt in VideoFormat:
                fmt_jobs = [j for j in jobs if j.format == fmt]
                if fmt_jobs:
                    scores = []
                    views = []
                    pcts = []

                    for job in fmt_jobs:
                        # Get latest metrics
                        metric = session.query(VideoMetric).filter_by(
                            job_id=job.id
                        ).order_by(VideoMetric.timestamp.desc()).first()

                        if metric:
                            scores.append(metric.avg_view_percentage)
                            views.append(metric.views)
                            pcts.append(metric.avg_view_percentage)

                    format_metrics[fmt.value] = {
                        "count": len(fmt_jobs),
                        "avg_score": sum(scores) / len(scores) if scores else 0,
                        "avg_views": sum(views) / len(views) if views else 0,
                        "avg_pct": sum(pcts) / len(pcts) if pcts else 0
                    }
                else:
                    format_metrics[fmt.value] = {
                        "count": 0,
                        "avg_score": 0,
                        "avg_views": 0,
                        "avg_pct": 0
                    }

            return format_metrics

        except Exception as e:
            self.logger.error("Failed to get format performance", error=str(e))
            return {}

    def collect_all_metrics(self, session: Session):
        """Collect metrics for all videos"""
        try:
            # Get all completed jobs with YouTube IDs
            jobs = session.query(Job).filter(
                Job.status == "completed",
                Job.youtube_id.isnot(None)
            ).all()

            if not jobs:
                self.logger.info("No videos to collect metrics for")
                return

            for job in jobs:
                try:
                    # Collect metrics for each window
                    for window in ["24h", "72h"]:
                        self.collect_video_metrics(session, job.youtube_id, window)
                except Exception as e:
                    self.logger.error("Failed to collect metrics for job",
                                    job_id=job.id,
                                    error=str(e))

            self.logger.info("Completed metrics collection for all videos",
                           count=len(jobs))

        except Exception as e:
            self.logger.error("Failed to collect all metrics", error=str(e))
            raise MetricsError(f"Bulk metrics collection failed: {str(e)}")

    def get_optimization_recommendations(self, session: Session) -> Dict:
        """Get optimization recommendations based on metrics"""
        try:
            # Get format performance
            format_performance = self.get_format_performance(session)

            # Simple recommendation: increase weight for best performing format
            best_format = max(
                format_performance.items(),
                key=lambda x: x[1]['avg_score']
            )[0]

            return {
                "recommendation": "increase_weight",
                "format": best_format,
                "current_performance": format_performance[best_format],
                "suggested_weight_increase": 1.2,
                "reason": f"Format {best_format} has highest average performance score"
            }

        except Exception as e:
            self.logger.error("Failed to generate recommendations", error=str(e))
            return {
                "recommendation": "insufficient_data",
                "message": "Not enough data for recommendations"
            }

# Global metrics collector instance
metrics_collector = MetricsCollector()
