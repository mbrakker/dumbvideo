#!/usr/bin/env python3
"""
YouTube Shorts Factory Worker

Main worker process for video generation, rendering, and upload
"""

import os
import sys
import time
import logging
from datetime import datetime
from typing import Optional
from dotenv import load_dotenv

# Add project root to path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.utils.logging import configure_logging, get_logger
from app.config.schema import config
from app.db.models import Base, Job, VideoStatus
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from app.services.generation.episode_generator import EpisodeGenerator
from app.services.rendering.video_renderer import VideoRenderer
from app.services.youtube.youtube_uploader import YouTubeUploader
from app.services.scheduler.job_scheduler import JobScheduler
from app.services.analytics.metrics_collector import MetricsCollector
from app.services.optimization.format_optimizer import FormatOptimizer
from app.services.safety.content_safety import ContentSafetyChecker

# Load environment variables
load_dotenv()

# Configure logging
logger = configure_logging(
    log_level=os.getenv("LOG_LEVEL", "INFO"),
    log_file=os.getenv("LOG_FILE", "logs/worker.log")
)

class Worker:
    def __init__(self):
        self.logger = get_logger("Worker")
        self.running = False
        self.kill_switch_enabled = False

        # Initialize database
        self.engine = create_engine(os.getenv("DATABASE_URL", "sqlite:///data/youtube_shorts.db"))
        Base.metadata.create_all(self.engine)
        self.Session = sessionmaker(bind=self.engine)

        # Initialize services
        self.scheduler = JobScheduler()
        self.generator = EpisodeGenerator()
        self.renderer = VideoRenderer()
        self.uploader = YouTubeUploader()
        self.metrics = MetricsCollector()
        self.optimizer = FormatOptimizer()
        self.safety = ContentSafetyChecker()

        self.logger.info("Worker initialized", status="ready")

    def start(self):
        """Start the worker main loop"""
        self.running = True
        self.logger.info("Worker started", status="running")

        try:
            while self.running:
                # Check kill switch
                if self._check_kill_switch():
                    self.logger.warning("Kill switch activated", action="stopping")
                    break

                # Check if automation is enabled
                if not config.config.automation_enabled:
                    self.logger.info("Automation disabled", status="idle")
                    time.sleep(60)
                    continue

                # Process jobs
                self._process_jobs()

                # Check for new jobs to schedule
                self._schedule_new_jobs()

                # Sleep before next iteration
                time.sleep(30)

        except KeyboardInterrupt:
            self.logger.info("Worker stopped by user", status="stopped")
        except Exception as e:
            self.logger.error("Worker crashed", error=str(e), status="error")
            raise

    def _check_kill_switch(self) -> bool:
        """Check if kill switch is enabled"""
        # Check database config
        session = self.Session()
        try:
            from app.db.models import Config
            kill_switch = session.query(Config).filter_by(key="kill_switch_enabled").first()
            if kill_switch and kill_switch.value:
                self.kill_switch_enabled = True
                return True
            return False
        finally:
            session.close()

    def _schedule_new_jobs(self):
        """Schedule new jobs based on budget and format weights"""
        try:
            session = self.Session()

            # Check budget compliance
            from app.utils.pricing import pricing
            from app.db.models import CostTracking

            today = datetime.now().date()
            cost_tracking = session.query(CostTracking).filter_by(date=today).first()
            daily_cost = cost_tracking.total_cost if cost_tracking else 0.0
            video_count = session.query(Job).filter(
                Job.created_at >= datetime(today.year, today.month, today.day),
                Job.status != VideoStatus.FAILED
            ).count()

            budget_compliant, message = pricing.check_budget_compliance(
                daily_cost=daily_cost,
                budget=config.config.daily_budget,
                video_count=video_count,
                max_videos=config.config.max_videos_per_day
            )

            if not budget_compliant:
                self.logger.info("Budget check failed", reason=message)
                return

            # Schedule new jobs
            new_jobs = self.scheduler.schedule_jobs(
                session=session,
                max_jobs=config.config.max_videos_per_day - video_count,
                budget_remaining=config.config.daily_budget - daily_cost
            )

            if new_jobs:
                self.logger.info("Scheduled new jobs", count=len(new_jobs))
            else:
                self.logger.debug("No new jobs scheduled", reason="budget_or_limit_reached")

        except Exception as e:
            self.logger.error("Failed to schedule new jobs", error=str(e))
        finally:
            session.close()

    def _process_jobs(self):
        """Process pending jobs"""
        try:
            session = self.Session()

            # Get pending jobs
            pending_jobs = session.query(Job).filter_by(status=VideoStatus.PENDING).all()

            if not pending_jobs:
                self.logger.debug("No pending jobs", status="idle")
                return

            self.logger.info("Processing jobs", count=len(pending_jobs))

            for job in pending_jobs:
                try:
                    # Update job status
                    job.status = VideoStatus.GENERATING
                    session.commit()

                    # Generate episode
                    episode = self._generate_episode(job, session)

                    # Render video
                    video_path = self._render_video(job, episode, session)

                    # Upload to YouTube
                    youtube_id = self._upload_video(job, video_path, session)

                    # Update job status
                    job.status = VideoStatus.COMPLETED
                    job.youtube_id = youtube_id
                    session.commit()

                    self.logger.info("Job completed", job_id=job.id, youtube_id=youtube_id)

                except Exception as e:
                    self.logger.error("Job failed", job_id=job.id, error=str(e))
                    job.status = VideoStatus.FAILED
                    job.error_message = str(e)
                    job.retry_count += 1
                    session.commit()

        except Exception as e:
            self.logger.error("Failed to process jobs", error=str(e))
        finally:
            session.close()

    def _generate_episode(self, job: Job, session) -> dict:
        """Generate episode data for job"""
        try:
            self.logger.info("Generating episode", job_id=job.id, format=job.format)

            # Get format-specific configuration
            episode_config = config.get_episode_config(job.format)

            # Generate episode
            episode = self.generator.generate_episode(episode_config)

            # Safety check
            if not self.safety.check_content_safety(episode):
                self.logger.warning("Content safety check failed", job_id=job.id)
                raise ValueError("Content failed safety check")

            # Update job with episode data
            job.episode_data = episode
            session.commit()

            return episode

        except Exception as e:
            self.logger.error("Episode generation failed", job_id=job.id, error=str(e))
            raise

    def _render_video(self, job: Job, episode: dict, session) -> str:
        """Render video for job"""
        try:
            self.logger.info("Rendering video", job_id=job.id)

            # Determine output path
            output_path = os.path.join("data", "outputs", f"{job.id}.mp4")

            # Render video
            video_path = self.renderer.render_video(
                episode=episode,
                output_path=output_path,
                format=job.format
            )

            return video_path

        except Exception as e:
            self.logger.error("Video rendering failed", job_id=job.id, error=str(e))
            raise

    def _upload_video(self, job: Job, video_path: str, session) -> str:
        """Upload video to YouTube"""
        try:
            self.logger.info("Uploading video", job_id=job.id, video=video_path)

            # Upload video
            youtube_id = self.uploader.upload_video(
                video_path=video_path,
                episode_data=job.episode_data,
                privacy_status="private"
            )

            return youtube_id

        except Exception as e:
            self.logger.error("Video upload failed", job_id=job.id, error=str(e))
            raise

    def stop(self):
        """Stop the worker"""
        self.running = False
        self.logger.info("Worker stopping", status="stopping")

if __name__ == "__main__":
    worker = Worker()

    try:
        worker.start()
    except KeyboardInterrupt:
        worker.stop()
    except Exception as e:
        logger.error("Worker failed", error=str(e))
        sys.exit(1)
