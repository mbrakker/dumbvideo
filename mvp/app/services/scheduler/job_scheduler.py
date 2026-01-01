"""
Job Scheduler Service

Handles intelligent job scheduling and budget management
"""

import os
import uuid
import random
from datetime import datetime, timedelta
from typing import List, Optional, Tuple, Dict
from app.utils.logging import get_logger
from app.config.schema import VideoFormat, EpisodeConfig
from app.db.models import Job, VideoStatus, CostTracking, FormatWeight
from sqlalchemy.orm import Session
from app.utils.pricing import CostCalculator
from app.utils.time import TimeUtils

logger = get_logger(__name__)

class SchedulingError(Exception):
    """Custom exception for scheduling failures"""
    pass

class JobScheduler:
    def __init__(self):
        self.logger = get_logger(f"{__name__}.JobScheduler")
        self.cost_calculator = CostCalculator()
        self.time_utils = TimeUtils()

        # Scheduling parameters
        self.max_daily_videos = 3
        self.daily_budget = 3.0  # €
        self.format_weights = {
            VideoFormat.TALKING_OBJECT: 1.0,
            VideoFormat.ABSURD_MOTIVATION: 1.0,
            VideoFormat.NOTHING_HAPPENS: 1.0
        }

        self.logger.info("Job scheduler initialized",
                       max_daily_videos=self.max_daily_videos,
                       daily_budget=self.daily_budget)

    def schedule_jobs(
        self,
        session: Session,
        max_jobs: int = 1,
        budget_remaining: float = 3.0
    ) -> List[Job]:
        """
        Schedule new jobs based on current budget and format weights

        Args:
            session: Database session
            max_jobs: Maximum number of jobs to schedule
            budget_remaining: Remaining daily budget

        Returns:
            List of scheduled jobs
        """
        scheduled_jobs = []

        try:
            # Load current format weights from database
            self._load_format_weights(session)

            # Calculate jobs to schedule
            jobs_to_schedule = min(max_jobs, self._calculate_available_job_slots(session))

            self.logger.info("Scheduling jobs",
                           max_possible=max_jobs,
                           budget_remaining=budget_remaining,
                           jobs_to_schedule=jobs_to_schedule)

            for i in range(jobs_to_schedule):
                # Select format based on weights
                selected_format = self._select_format_based_on_weights()

                # Estimate cost for this job
                estimated_cost = self.cost_calculator.estimate_total_video_cost(selected_format)

                if estimated_cost > budget_remaining:
                    self.logger.warning("Cannot schedule more jobs",
                                     reason="budget_exceeded",
                                     remaining_budget=budget_remaining)
                    break

                # Create job
                job = self._create_job(session, selected_format, estimated_cost)
                scheduled_jobs.append(job)

                # Update remaining budget
                budget_remaining -= estimated_cost

                self.logger.info("Scheduled job",
                               job_id=job.id,
                               format=selected_format,
                               estimated_cost=estimated_cost,
                               remaining_budget=budget_remaining)

            return scheduled_jobs

        except Exception as e:
            self.logger.error("Job scheduling failed", error=str(e))
            raise SchedulingError(f"Scheduling failed: {str(e)}")

    def _load_format_weights(self, session: Session):
        """Load format weights from database"""
        try:
            weights = session.query(FormatWeight).all()
            for weight in weights:
                self.format_weights[weight.format] = weight.weight

            self.logger.debug("Loaded format weights",
                            weights=self.format_weights)

        except Exception as e:
            self.logger.error("Failed to load format weights", error=str(e))
            # Use default weights if loading fails
            for fmt in VideoFormat:
                self.format_weights[fmt] = 1.0

    def _calculate_available_job_slots(self, session: Session) -> int:
        """Calculate how many more jobs can be scheduled today"""
        try:
            today = datetime.now().date()
            daily_jobs = session.query(Job).filter(
                Job.created_at >= datetime(today.year, today.month, today.day)
            ).count()

            available_slots = max(0, self.max_daily_videos - daily_jobs)
            self.logger.debug("Calculated available job slots",
                            daily_jobs=daily_jobs,
                            available_slots=available_slots)

            return available_slots

        except Exception as e:
            self.logger.error("Failed to calculate job slots", error=str(e))
            return 0

    def _select_format_based_on_weights(self) -> VideoFormat:
        """Select format based on current weights"""
        try:
            # Normalize weights
            total_weight = sum(self.format_weights.values())
            normalized_weights = {fmt: weight/total_weight for fmt, weight in self.format_weights.items()}

            # Create weighted selection
            formats = list(self.format_weights.keys())
            weights = list(normalized_weights.values())

            # Select format
            selected_format = random.choices(formats, weights=weights, k=1)[0]

            self.logger.debug("Selected format for new job",
                            format=selected_format,
                            weights=normalized_weights)

            return selected_format

        except Exception as e:
            self.logger.error("Failed to select format", error=str(e))
            # Fallback to random selection
            return random.choice(list(VideoFormat))

    def _create_job(self, session: Session, format: VideoFormat, estimated_cost: float) -> Job:
        """Create a new job in the database"""
        try:
            job = Job(
                id=str(uuid.uuid4()),
                format=format,
                status=VideoStatus.PENDING,
                generation_cost=estimated_cost * 0.7,  # 70% for generation
                render_cost=estimated_cost * 0.3,      # 30% for rendering
                created_at=datetime.utcnow(),
                updated_at=datetime.utcnow()
            )

            session.add(job)
            session.commit()

            # Update cost tracking
            self._update_cost_tracking(session, estimated_cost)

            self.logger.info("Created new job",
                           job_id=job.id,
                           format=format)

            return job

        except Exception as e:
            session.rollback()
            self.logger.error("Failed to create job", error=str(e))
            raise SchedulingError(f"Job creation failed: {str(e)}")

    def _update_cost_tracking(self, session: Session, cost: float):
        """Update daily cost tracking"""
        try:
            today = datetime.now().date()

            # Get or create cost tracking record
            cost_tracking = session.query(CostTracking).filter_by(date=today).first()
            if not cost_tracking:
                cost_tracking = CostTracking(
                    date=today,
                    openai_cost=0.0,
                    total_cost=0.0,
                    video_count=0
                )
                session.add(cost_tracking)

            # Update costs
            cost_tracking.openai_cost += cost
            cost_tracking.total_cost += cost
            cost_tracking.video_count += 1

            session.commit()

            self.logger.debug("Updated cost tracking",
                            date=today,
                            openai_cost=cost_tracking.openai_cost,
                            total_cost=cost_tracking.total_cost)

        except Exception as e:
            session.rollback()
            self.logger.error("Failed to update cost tracking", error=str(e))
            raise SchedulingError(f"Cost tracking failed: {str(e)}")

    def get_scheduling_recommendations(self, session: Session) -> Dict:
        """
        Get scheduling recommendations based on current performance

        Args:
            session: Database session

        Returns:
            Dictionary with recommendations
        """
        try:
            # Get recent performance data
            recent_jobs = session.query(Job).filter(
                Job.status == VideoStatus.COMPLETED,
                Job.created_at >= datetime.utcnow() - timedelta(days=7)
            ).all()

            if not recent_jobs:
                return {
                    "recommendation": "insufficient_data",
                    "message": "Not enough recent data for recommendations",
                    "suggested_action": "continue_current_strategy"
                }

            # Analyze format performance (simplified - would use metrics in full implementation)
            format_counts = {}
            for fmt in VideoFormat:
                format_counts[fmt] = len([j for j in recent_jobs if j.format == fmt])

            # Simple recommendation logic
            least_used_format = min(format_counts, key=format_counts.get)

            return {
                "recommendation": "increase_format_weight",
                "format": least_used_format,
                "current_weight": self.format_weights.get(least_used_format, 1.0),
                "suggested_weight": self.format_weights.get(least_used_format, 1.0) * 1.2,
                "reason": f"Format {least_used_format} has been used least recently",
                "confidence": "low"  # Would be higher with actual metrics
            }

        except Exception as e:
            self.logger.error("Failed to generate recommendations", error=str(e))
            return {
                "recommendation": "error",
                "message": f"Recommendation generation failed: {str(e)}",
                "suggested_action": "continue_current_strategy"
            }

    def check_budget_compliance(self, session: Session) -> Tuple[bool, str]:
        """
        Check if we can schedule more jobs today

        Args:
            session: Database session

        Returns:
            Tuple of (compliant: bool, message: str)
        """
        try:
            today = datetime.now().date()

            # Check video count
            daily_jobs = session.query(Job).filter(
                Job.created_at >= datetime(today.year, today.month, today.day)
            ).count()

            if daily_jobs >= self.max_daily_videos:
                return False, f"Maximum daily videos reached ({self.max_daily_videos})"

            # Check budget
            cost_tracking = session.query(CostTracking).filter_by(date=today).first()
            daily_cost = cost_tracking.total_cost if cost_tracking else 0.0

            if daily_cost >= self.daily_budget:
                return False, f"Daily budget exceeded (€{self.daily_budget:.2f})"

            return True, "Budget compliant"

        except Exception as e:
            self.logger.error("Budget compliance check failed", error=str(e))
            return False, f"Budget check error: {str(e)}"

    def schedule_manual_job(self, session: Session, format: VideoFormat) -> Optional[Job]:
        """
        Schedule a manual job (triggered from dashboard)

        Args:
            session: Database session
            format: Video format to generate

        Returns:
            Created job or None if failed
        """
        try:
            # Check budget compliance
            compliant, message = self.check_budget_compliance(session)
            if not compliant:
                self.logger.warning("Manual job request denied",
                                 reason=message)
                return None

            # Estimate cost
            estimated_cost = self.cost_calculator.estimate_total_video_cost(format)

            # Create job
            job = self._create_job(session, format, estimated_cost)

            self.logger.info("Manual job scheduled",
                           job_id=job.id,
                           format=format)

            return job

        except Exception as e:
            self.logger.error("Manual job scheduling failed", error=str(e))
            return None

# Global scheduler instance
job_scheduler = JobScheduler()
