"""
Format Optimizer Service

Handles automatic optimization of format weights based on performance
"""

import os
import time
from typing import Dict, List, Optional
from datetime import datetime, timedelta
from app.utils.logging import get_logger
from app.db.models import Job, VideoMetric, FormatWeight
from sqlalchemy.orm import Session
from app.config.schema import VideoFormat
from app.services.analytics.metrics_collector import MetricsCollector

logger = get_logger(__name__)

class OptimizationError(Exception):
    """Custom exception for optimization failures"""
    pass

class FormatOptimizer:
    def __init__(self):
        self.logger = get_logger(f"{__name__}.FormatOptimizer")
        self.metrics_collector = MetricsCollector()

        # Optimization parameters
        self.min_samples = 3  # Minimum samples before optimization
        self.max_adjustment = 0.2  # Max adjustment per optimization
        self.cooldown_period = 24  # Hours between optimizations

        self.logger.info("Format optimizer initialized",
                       min_samples=self.min_samples,
                       max_adjustment=self.max_adjustment)

    def optimize_format_weights(self, session: Session) -> Dict:
        """
        Optimize format weights based on recent performance

        Args:
            session: Database session

        Returns:
            Optimization result
        """
        try:
            self.logger.info("Starting format weight optimization")

            # Get current format performance
            performance = self.metrics_collector.get_format_performance(session)

            # Check if we have enough data
            total_videos = sum(fmt_data['count'] for fmt_data in performance.values())
            if total_videos < self.min_samples:
                return {
                    "status": "insufficient_data",
                    "message": f"Need at least {self.min_samples} videos, have {total_videos}",
                    "action": "no_change"
                }

            # Get current weights
            current_weights = self._get_current_weights(session)

            # Calculate new weights based on performance
            new_weights = self._calculate_new_weights(performance, current_weights)

            # Apply new weights to database
            self._apply_new_weights(session, new_weights)

            self.logger.info("Format weight optimization completed",
                           new_weights=new_weights)

            return {
                "status": "success",
                "old_weights": current_weights,
                "new_weights": new_weights,
                "changes": self._calculate_changes(current_weights, new_weights)
            }

        except Exception as e:
            self.logger.error("Optimization failed", error=str(e))
            raise OptimizationError(f"Optimization failed: {str(e)}")

    def _get_current_weights(self, session: Session) -> Dict:
        """Get current format weights from database"""
        try:
            weights = session.query(FormatWeight).all()
            return {w.format: w.weight for w in weights}

        except Exception as e:
            self.logger.error("Failed to get current weights", error=str(e))
            # Return default weights
            return {
                VideoFormat.TALKING_OBJECT: 1.0,
                VideoFormat.ABSURD_MOTIVATION: 1.0,
                VideoFormat.NOTHING_HAPPENS: 1.0
            }

    def _calculate_new_weights(self, performance: Dict, current_weights: Dict) -> Dict:
        """Calculate new weights based on performance"""
        try:
            # Calculate performance scores
            performance_scores = {}
            for fmt, data in performance.items():
                if data['count'] > 0:
                    # Calculate weighted performance score
                    score = (
                        0.6 * data['avg_pct'] +  # View percentage is most important
                        0.3 * data['avg_views'] +  # Views matter
                        0.1 * data['count']   # Sample size helps
                    )
                    performance_scores[fmt] = score
                else:
                    performance_scores[fmt] = 0

            # Normalize scores
            total_score = sum(performance_scores.values())
            if total_score == 0:
                return current_weights  # No change if no data

            normalized_scores = {fmt: score/total_score for fmt, score in performance_scores.items()}

            # Calculate new weights with constraints
            new_weights = {}
            for fmt in VideoFormat:
                current_weight = current_weights.get(fmt, 1.0)
                target_weight = normalized_scores.get(fmt, 0)

                # Calculate adjustment (limited by max_adjustment)
                adjustment = min(
                    self.max_adjustment,
                    max(-self.max_adjustment, target_weight - current_weight)
                )

                new_weight = current_weight + adjustment
                new_weights[fmt] = max(0.1, new_weight)  # Ensure minimum weight

            # Normalize weights to maintain balance
            total_new_weight = sum(new_weights.values())
            if total_new_weight > 0:
                new_weights = {fmt: weight/total_new_weight * len(new_weights)
                              for fmt, weight in new_weights.items()}

            return new_weights

        except Exception as e:
            self.logger.error("Failed to calculate new weights", error=str(e))
            return current_weights

    def _apply_new_weights(self, session: Session, new_weights: Dict):
        """Apply new weights to database"""
        try:
            for fmt, weight in new_weights.items():
                weight_record = session.query(FormatWeight).filter_by(format=fmt).first()
                if weight_record:
                    weight_record.weight = weight
                    weight_record.last_updated = datetime.utcnow()
                    weight_record.reason = "Automatic optimization based on performance"
                else:
                    new_record = FormatWeight(
                        format=fmt,
                        weight=weight,
                        last_updated=datetime.utcnow(),
                        reason="Initial optimization setup"
                    )
                    session.add(new_record)

            session.commit()

            self.logger.info("Applied new format weights to database",
                           weights=new_weights)

        except Exception as e:
            session.rollback()
            self.logger.error("Failed to apply new weights", error=str(e))
            raise OptimizationError(f"Failed to apply weights: {str(e)}")

    def _calculate_changes(self, old_weights: Dict, new_weights: Dict) -> Dict:
        """Calculate weight changes"""
        changes = {}
        for fmt in VideoFormat:
            old = old_weights.get(fmt, 1.0)
            new = new_weights.get(fmt, 1.0)
            changes[fmt] = {
                "old": old,
                "new": new,
                "change": new - old,
                "percentage_change": ((new - old) / old * 100) if old > 0 else 0
            }
        return changes

    def get_optimization_history(self, session: Session, limit: int = 10) -> List[Dict]:
        """Get recent optimization history"""
        try:
            weights = session.query(FormatWeight).order_by(
                FormatWeight.last_updated.desc()
            ).limit(limit).all()

            return [{
                "format": w.format,
                "weight": w.weight,
                "last_updated": w.last_updated,
                "reason": w.reason
            } for w in weights]

        except Exception as e:
            self.logger.error("Failed to get optimization history", error=str(e))
            return []

    def should_optimize(self, session: Session) -> bool:
        """Check if optimization should run"""
        try:
            # Get last optimization time
            last_optimization = session.query(FormatWeight).order_by(
                FormatWeight.last_updated.desc()
            ).first()

            if not last_optimization:
                return True  # Never optimized before

            # Check cooldown period
            time_since = datetime.utcnow() - last_optimization.last_updated
            return time_since.total_seconds() > (self.cooldown_period * 3600)

        except Exception as e:
            self.logger.error("Failed to check optimization timing", error=str(e))
            return False

    def get_optimization_recommendation(self, session: Session) -> Dict:
        """Get optimization recommendation"""
        try:
            # Get current performance
            performance = self.metrics_collector.get_format_performance(session)

            # Find best and worst performing formats
            sorted_formats = sorted(
                performance.items(),
                key=lambda x: x[1]['avg_score'],
                reverse=True
            )

            best_format = sorted_formats[0]
            worst_format = sorted_formats[-1]

            return {
                "recommendation": "adjust_weights",
                "best_format": {
                    "format": best_format[0],
                    "performance": best_format[1]
                },
                "worst_format": {
                    "format": worst_format[0],
                    "performance": worst_format[1]
                },
                "suggested_action": f"Increase {best_format[0]} weight, decrease {worst_format[0]} weight"
            }

        except Exception as e:
            self.logger.error("Failed to generate recommendation", error=str(e))
            return {
                "recommendation": "insufficient_data",
                "message": "Not enough performance data"
            }

    def manual_optimization(self, session: Session, adjustments: Dict) -> Dict:
        """
        Manually adjust format weights

        Args:
            session: Database session
            adjustments: Dictionary of format: weight adjustments

        Returns:
            Result of manual optimization
        """
        try:
            # Get current weights
            current_weights = self._get_current_weights(session)

            # Apply adjustments
            for fmt, adjustment in adjustments.items():
                if fmt in VideoFormat:
                    current_weights[fmt] = max(0.1, current_weights[fmt] + adjustment)

            # Normalize weights
            total = sum(current_weights.values())
            if total > 0:
                current_weights = {fmt: weight/total * len(current_weights)
                                  for fmt, weight in current_weights.items()}

            # Apply to database
            self._apply_new_weights(session, current_weights)

            return {
                "status": "success",
                "new_weights": current_weights,
                "message": "Manual optimization applied"
            }

        except Exception as e:
            self.logger.error("Manual optimization failed", error=str(e))
            raise OptimizationError(f"Manual optimization failed: {str(e)}")

# Global optimizer instance
format_optimizer = FormatOptimizer()
