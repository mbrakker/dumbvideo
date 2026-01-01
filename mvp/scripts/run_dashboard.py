#!/usr/bin/env python3
"""
YouTube Shorts Factory Dashboard

Streamlit dashboard for monitoring and controlling the factory
"""

import os
import sys
import streamlit as st
from dotenv import load_dotenv

# Add project root to path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.utils.logging import configure_logging, get_logger
from app.config.schema import config, VideoFormat
from app.db.models import Base, Job, VideoStatus, VideoMetric, Config, FormatWeight
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from datetime import datetime, timedelta
import pandas as pd
from typing import List, Dict, Any

# Load environment variables
load_dotenv()

# Configure logging
logger = configure_logging(log_level=os.getenv("LOG_LEVEL", "INFO"))

# Initialize database
engine = create_engine(os.getenv("DATABASE_URL", "sqlite:///data/youtube_shorts.db"))
Base.metadata.create_all(engine)
Session = sessionmaker(bind=engine)

# Page configuration
st.set_page_config(
    page_title="YouTube Shorts Factory",
    page_icon="🎥",
    layout="wide",
    initial_sidebar_state="expanded"
)

class Dashboard:
    def __init__(self):
        self.logger = get_logger("Dashboard")
        self.logger.info("Dashboard initialized")

    def run(self):
        """Run the dashboard"""
        st.title("🎥 YouTube Shorts Factory")
        st.markdown("Automated Shorts Generation & Publishing System")

        # Sidebar navigation
        page = st.sidebar.radio(
            "Navigation",
            ["📊 Overview", "⚙️ Settings", "🎬 Jobs", "📈 Analytics", "🔄 Optimization", "🗃️ Database Explorer"]
        )

        if page == "📊 Overview":
            self._show_overview()
        elif page == "⚙️ Settings":
            self._show_settings()
        elif page == "🎬 Jobs":
            self._show_jobs()
        elif page == "📈 Analytics":
            self._show_analytics()
        elif page == "🔄 Optimization":
            self._show_optimization()
        elif page == "🗃️ Database Explorer":
            self._show_database_explorer()

    def _show_overview(self):
        """Show system overview"""
        st.header("📊 System Overview")

        session = Session()
        try:
            # Get current stats
            today = datetime.now().date()
            jobs_today = session.query(Job).filter(
                Job.created_at >= datetime(today.year, today.month, today.day)
            ).all()

            completed = sum(1 for j in jobs_today if j.status == VideoStatus.COMPLETED)
            failed = sum(1 for j in jobs_today if j.status == VideoStatus.FAILED)
            pending = sum(1 for j in jobs_today if j.status == VideoStatus.PENDING)
            processing = sum(1 for j in jobs_today if j.status in [VideoStatus.GENERATING, VideoStatus.RENDERING, VideoStatus.UPLOADING])

            # Get cost tracking
            from app.db.models import CostTracking
            cost_tracking = session.query(CostTracking).filter_by(date=today).first()
            daily_cost = cost_tracking.total_cost if cost_tracking else 0.0

            # Display metrics
            col1, col2, col3, col4 = st.columns(4)
            col1.metric("Completed Today", completed)
            col2.metric("Failed Today", failed)
            col3.metric("Pending Jobs", pending)
            col4.metric("Processing Jobs", processing)

            # Budget tracking
            st.subheader("💰 Budget Tracking")
            budget_progress = daily_cost / config.config.daily_budget
            st.progress(budget_progress)
            st.metric("Daily Cost", f"€{daily_cost:.2f}", f"€{config.config.daily_budget - daily_cost:.2f} remaining")

            # Next scheduled videos
            st.subheader("📅 Next Scheduled Videos")
            scheduled_jobs = session.query(Job).filter(
                Job.scheduled_publish_time.isnot(None),
                Job.status == VideoStatus.COMPLETED
            ).order_by(Job.scheduled_publish_time).limit(5).all()

            if scheduled_jobs:
                for job in scheduled_jobs:
                    st.write(f"🎬 **{job.episode_data.get('title_options', ['Untitled'])[0]}**")
                    st.write(f"📅 {job.scheduled_publish_time.strftime('%Y-%m-%d %H:%M')} | 🏷️ {job.format}")
            else:
                st.info("No videos scheduled for upload")

            # System status
            st.subheader("🔧 System Status")
            col1, col2 = st.columns(2)

            with col1:
                automation_config = session.query(Config).filter_by(key="automation_enabled").first()
                automation_status = "✅ Enabled" if automation_config and automation_config.value else "❌ Disabled"
                st.write(f"**Automation:** {automation_status}")

            with col2:
                kill_switch = session.query(Config).filter_by(key="kill_switch_enabled").first()
                kill_status = "❌ Not Active" if not kill_switch or not kill_switch.value else "⚠️ ACTIVE"
                st.write(f"**Kill Switch:** {kill_status}")

        finally:
            session.close()

    def _show_settings(self):
        """Show system settings"""
        st.header("⚙️ System Settings")

        session = Session()
        try:
            # Automation controls
            st.subheader("🤖 Automation Controls")

            col1, col2 = st.columns(2)

            with col1:
                automation_config = session.query(Config).filter_by(key="automation_enabled").first()
                automation_enabled = st.toggle(
                    "Enable Automation",
                    value=automation_config.value if automation_config else False
                )

                if automation_enabled != (automation_config.value if automation_config else False):
                    automation_config.value = automation_enabled
                    automation_config.updated_at = datetime.utcnow()
                    session.commit()
                    st.success("Automation setting updated")

            with col2:
                kill_switch_config = session.query(Config).filter_by(key="kill_switch_enabled").first()
                kill_switch_enabled = st.toggle(
                    "🚨 Kill Switch (STOP ALL PROCESSING)",
                    value=kill_switch_config.value if kill_switch_config else False,
                    help="Immediately stops all processing and prevents new jobs"
                )

                if kill_switch_enabled != (kill_switch_config.value if kill_switch_config else False):
                    kill_switch_config.value = kill_switch_enabled
                    kill_switch_config.updated_at = datetime.utcnow()
                    session.commit()
                    st.warning("Kill switch updated - all processing stopped")

            # Budget settings
            st.subheader("💰 Budget Settings")

            budget_config = session.query(Config).filter_by(key="daily_budget").first()
            new_budget = st.number_input(
                "Daily Budget (€)",
                min_value=1.0,
                max_value=100.0,
                value=float(budget_config.value["value"]) if budget_config else 3.0,
                step=0.5
            )

            if st.button("Update Budget"):
                budget_config.value = {"value": new_budget, "currency": "EUR"}
                budget_config.updated_at = datetime.utcnow()
                session.commit()
                st.success("Budget updated")

            # Format weights
            st.subheader("🎭 Format Weights")

            weights = {}
            for fmt in VideoFormat:
                weight_config = session.query(FormatWeight).filter_by(format=fmt).first()
                weights[fmt] = st.slider(
                    f"{fmt.value.replace('_', ' ').title()} Weight",
                    min_value=0.1,
                    max_value=10.0,
                    value=weight_config.weight if weight_config else 1.0,
                    step=0.1
                )

            if st.button("Update Format Weights"):
                for fmt, weight in weights.items():
                    weight_config = session.query(FormatWeight).filter_by(format=fmt).first()
                    if weight_config:
                        weight_config.weight = weight
                        weight_config.last_updated = datetime.utcnow()
                        weight_config.reason = "Manual update via dashboard"
                session.commit()
                st.success("Format weights updated")

            # Manual run controls
            st.subheader("🚀 Manual Controls")

            if st.button("🔄 Run Now (Generate 1 Video)"):
                # This would trigger the worker to generate one video
                st.info("Manual run triggered - worker will process this request")
                self.logger.info("Manual run triggered from dashboard")

        finally:
            session.close()

    def _show_jobs(self):
        """Show jobs management"""
        st.header("🎬 Jobs Management")

        session = Session()
        try:
            # Get all jobs
            jobs = session.query(Job).order_by(Job.created_at.desc()).all()

            if not jobs:
                st.info("No jobs found")
                return

            # Convert to DataFrame
            job_data = []
            for job in jobs:
                episode_data = job.episode_data or {}
                job_data.append({
                    "ID": job.id,
                    "Format": job.format,
                    "Status": job.status,
                    "Created": job.created_at.strftime("%Y-%m-%d %H:%M"),
                    "Title": episode_data.get("title_options", ["Untitled"])[0],
                    "YouTube ID": job.youtube_id or "Not uploaded",
                    "Scheduled": job.scheduled_publish_time.strftime("%Y-%m-%d %H:%M") if job.scheduled_publish_time else "Not scheduled",
                    "Cost": f"€{job.generation_cost + job.render_cost:.2f}",
                    "Retries": job.retry_count
                })

            df = pd.DataFrame(job_data)

            # Display with AgGrid
            try:
                from st_aggrid import AgGrid, GridOptionsBuilder

                gb = GridOptionsBuilder.from_dataframe(df)
                gb.configure_pagination()
                gb.configure_side_bar()
                gb.configure_default_column(
                    filterable=True,
                    sortable=True,
                    resizable=True
                )

                grid_options = gb.build()
                AgGrid(df, gridOptions=grid_options, height=400)

            except ImportError:
                st.dataframe(df)

            # Job actions
            st.subheader("Job Actions")

            selected_job_id = st.selectbox(
                "Select job for actions",
                [job.id for job in jobs],
                format_func=lambda x: next(job.episode_data.get("title_options", ["Untitled"])[0] for job in jobs if job.id == x)
            )

            selected_job = next(job for job in jobs if job.id == selected_job_id)

            col1, col2, col3 = st.columns(3)

            with col1:
                if st.button("🔄 Retry Job"):
                    if selected_job.status == VideoStatus.FAILED:
                        selected_job.status = VideoStatus.PENDING
                        selected_job.error_message = None
                        session.commit()
                        st.success("Job marked for retry")
                    else:
                        st.warning("Only failed jobs can be retried")

            with col2:
                if st.button("🗑️ Delete Job"):
                    session.delete(selected_job)
                    session.commit()
                    st.success("Job deleted")

            with col3:
                if selected_job.youtube_id and st.button("🔗 View on YouTube"):
                    st.info(f"Would open: https://youtu.be/{selected_job.youtube_id}")

        finally:
            session.close()

    def _show_analytics(self):
        """Show analytics dashboard"""
        st.header("📈 Performance Analytics")

        session = Session()
        try:
            # Get completed jobs with metrics
            completed_jobs = session.query(Job).filter_by(status=VideoStatus.COMPLETED).all()

            if not completed_jobs:
                st.info("No completed videos with metrics yet")
                return

            # Format performance
            st.subheader("🎭 Format Performance")

            format_stats = {}
            for fmt in VideoFormat:
                fmt_jobs = [j for j in completed_jobs if j.format == fmt]
                if fmt_jobs:
                    avg_views = sum(m.views for j in fmt_jobs for m in j.metrics) / len(fmt_jobs)
                    avg_likes = sum(m.likes for j in fmt_jobs for m in j.metrics) / len(fmt_jobs)
                    avg_view_pct = sum(m.avg_view_percentage for j in fmt_jobs for m in j.metrics) / len(fmt_jobs)

                    format_stats[fmt.value] = {
                        "count": len(fmt_jobs),
                        "avg_views": avg_views,
                        "avg_likes": avg_likes,
                        "avg_view_pct": avg_view_pct
                    }

            if format_stats:
                stats_df = pd.DataFrame(format_stats).T
                st.dataframe(stats_df)

                # Chart
                st.bar_chart(stats_df[["avg_views", "avg_likes"]])

            # Individual video metrics
            st.subheader("📊 Individual Video Performance")

            video_metrics = []
            for job in completed_jobs:
                for metric in job.metrics:
                    video_metrics.append({
                        "ID": job.id,
                        "Title": job.episode_data.get("title_options", ["Untitled"])[0],
                        "Format": job.format,
                        "Window": metric.window,
                        "Views": metric.views,
                        "Likes": metric.likes,
                        "Avg View %": metric.avg_view_percentage,
                        "Subscribers": metric.subscribers_gained
                    })

            if video_metrics:
                metrics_df = pd.DataFrame(video_metrics)
                st.dataframe(metrics_df)

        finally:
            session.close()

    def _show_optimization(self):
        """Show optimization dashboard"""
        st.header("🔄 Optimization Dashboard")

        session = Session()
        try:
            # Get current weights
            st.subheader("📊 Current Format Weights")

            weights_data = []
            for fmt in VideoFormat:
                weight_config = session.query(FormatWeight).filter_by(format=fmt).first()
                if weight_config:
                    weights_data.append({
                        "Format": fmt.value.replace("_", " ").title(),
                        "Weight": weight_config.weight,
                        "Last Updated": weight_config.last_updated.strftime("%Y-%m-%d %H:%M"),
                        "Reason": weight_config.reason or "Initial setup"
                    })

            if weights_data:
                weights_df = pd.DataFrame(weights_data)
                st.dataframe(weights_df)

            # Optimization recommendations
            st.subheader("🤖 Optimization Recommendations")

            if st.button("🔍 Analyze Performance & Recommend"):
                # This would trigger the optimizer to analyze and recommend
                st.info("Analyzing performance data...")

                # Mock recommendation (would be real in implementation)
                st.success("Recommendation: Increase 'Absurd Motivation' weight by 20% based on recent performance")

                # Show optimization history
                st.subheader("📜 Optimization History")

                history_data = [
                    {"Date": "2024-01-01", "Change": "Initial weights set", "Reason": "System startup"},
                    {"Date": "2024-01-03", "Change": "Talking Object +10%", "Reason": "Higher engagement"},
                ]

                history_df = pd.DataFrame(history_data)
                st.dataframe(history_df)

        finally:
            session.close()

    def _show_database_explorer(self):
        """Show comprehensive database explorer with advanced filtering and export capabilities"""
        st.header("🗃️ Database Explorer")
        st.markdown("Comprehensive YouTube Shorts database viewer with advanced filtering and analytics")

        session = Session()
        try:
            # Database statistics overview
            st.subheader("📊 Database Statistics")

            total_jobs = session.query(Job).count()
            completed_jobs = session.query(Job).filter_by(status=VideoStatus.COMPLETED).count()
            failed_jobs = session.query(Job).filter_by(status=VideoStatus.FAILED).count()
            pending_jobs = session.query(Job).filter_by(status=VideoStatus.PENDING).count()
            processing_jobs = session.query(Job).filter(Job.status.in_([VideoStatus.GENERATING, VideoStatus.RENDERING, VideoStatus.UPLOADING])).count()
            total_metrics = session.query(VideoMetric).count()

            col1, col2, col3, col4, col5, col6 = st.columns(6)
            col1.metric("Total Jobs", total_jobs)
            col2.metric("Completed", completed_jobs)
            col3.metric("Failed", failed_jobs)
            col4.metric("Pending", pending_jobs)
            col5.metric("Processing", processing_jobs)
            col6.metric("Metrics", total_metrics)

            # Advanced filtering section
            st.subheader("🔍 Advanced Filters")

            col1, col2, col3, col4 = st.columns(4)

            with col1:
                # Status filter
                status_filter = st.multiselect(
                    "Status",
                    [status.value for status in VideoStatus],
                    default=[status.value for status in VideoStatus]
                )

            with col2:
                # Format filter
                format_filter = st.multiselect(
                    "Format",
                    [fmt.value for fmt in VideoFormat],
                    default=[fmt.value for fmt in VideoFormat]
                )

            with col3:
                # Date range filter
                date_range = st.date_input(
                    "Date Range",
                    value=[datetime.now() - timedelta(days=30), datetime.now()],
                    min_value=datetime(2023, 1, 1),
                    max_value=datetime.now()
                )

            with col4:
                # YouTube upload status filter
                youtube_filter = st.selectbox(
                    "YouTube Status",
                    ["All", "Uploaded", "Not Uploaded"]
                )

            # Search functionality
            search_query = st.text_input("🔎 Search by title, ID, or YouTube ID", "")

            # Apply filters and get data
            query = session.query(Job)

            # Apply status filter
            if status_filter:
                query = query.filter(Job.status.in_(status_filter))

            # Apply format filter
            if format_filter:
                query = query.filter(Job.format.in_(format_filter))

            # Apply date range filter
            if len(date_range) == 2:
                start_date, end_date = date_range
                query = query.filter(
                    Job.created_at >= datetime.combine(start_date, datetime.min.time()),
                    Job.created_at <= datetime.combine(end_date, datetime.max.time())
                )

            # Apply YouTube filter
            if youtube_filter == "Uploaded":
                query = query.filter(Job.youtube_id.isnot(None))
            elif youtube_filter == "Not Uploaded":
                query = query.filter(Job.youtube_id.is_(None))

            # Apply search filter
            if search_query:
                query = query.filter(
                    Job.id.ilike(f"%{search_query}%") |
                    Job.youtube_id.ilike(f"%{search_query}%") |
                    Job.episode_data.ilike(f"%{search_query}%")
                )

            # Get filtered jobs
            filtered_jobs = query.order_by(Job.created_at.desc()).all()

            st.info(f"Found {len(filtered_jobs)} jobs matching filters")

            if filtered_jobs:
                # Convert to DataFrame with comprehensive data
                job_data = []
                for job in filtered_jobs:
                    episode_data = job.episode_data or {}
                    metrics_data = {}

                    # Aggregate metrics if available
                    if job.metrics:
                        total_views = sum(m.views for m in job.metrics)
                        total_likes = sum(m.likes for m in job.metrics)
                        avg_view_pct = sum(m.avg_view_percentage for m in job.metrics) / len(job.metrics) if job.metrics else 0
                        metrics_data = {
                            "total_views": total_views,
                            "total_likes": total_likes,
                            "avg_view_pct": avg_view_pct
                        }

                    job_data.append({
                        "ID": job.id,
                        "Format": job.format,
                        "Status": job.status,
                        "Created": job.created_at.strftime("%Y-%m-%d %H:%M"),
                        "Updated": job.updated_at.strftime("%Y-%m-%d %H:%M"),
                        "Title": episode_data.get("title_options", ["Untitled"])[0],
                        "YouTube ID": job.youtube_id or "Not uploaded",
                        "Scheduled": job.scheduled_publish_time.strftime("%Y-%m-%d %H:%M") if job.scheduled_publish_time else "Not scheduled",
                        "Published": job.actual_publish_time.strftime("%Y-%m-%d %H:%M") if job.actual_publish_time else "Not published",
                        "Generation Cost": f"€{job.generation_cost:.2f}",
                        "Render Cost": f"€{job.render_cost:.2f}",
                        "Total Cost": f"€{job.generation_cost + job.render_cost:.2f}",
                        "Retries": job.retry_count,
                        "Error": job.error_message or "None",
                        "Total Views": metrics_data.get("total_views", 0),
                        "Total Likes": metrics_data.get("total_likes", 0),
                        "Avg View %": f"{metrics_data.get('avg_view_pct', 0):.1f}%",
                        "Privacy": job.privacy_status
                    })

                df = pd.DataFrame(job_data)

                # Display with AgGrid for advanced features
                try:
                    from st_aggrid import AgGrid, GridOptionsBuilder

                    gb = GridOptionsBuilder.from_dataframe(df)
                    gb.configure_pagination(paginationAutoPageSize=True)
                    gb.configure_side_bar()
                    gb.configure_default_column(
                        filterable=True,
                        sortable=True,
                        resizable=True,
                        wrapHeaderText=True,
                        autoHeaderHeight=True
                    )

                    # Custom column configurations
                    gb.configure_column("ID", pinned="left")
                    gb.configure_column("Title", width=200)
                    gb.configure_column("Error", width=150, wrapText=True)

                    grid_options = gb.build()
                    grid_response = AgGrid(
                        df,
                        gridOptions=grid_options,
                        height=500,
                        key="database_grid"
                    )

                    # Export functionality
                    st.subheader("📤 Export Data")

                    col1, col2, col3 = st.columns(3)

                    with col1:
                        if st.button("📥 Export to CSV"):
                            csv = df.to_csv(index=False)
                            st.download_button(
                                label="Download CSV",
                                data=csv,
                                file_name=f"youtube_shorts_database_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv",
                                mime="text/csv"
                            )

                    with col2:
                        if st.button("📥 Export to JSON"):
                            json_data = df.to_json(orient="records", indent=2)
                            st.download_button(
                                label="Download JSON",
                                data=json_data,
                                file_name=f"youtube_shorts_database_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json",
                                mime="application/json"
                            )

                    with col3:
                        if st.button("📥 Export to Excel"):
                            try:
                                excel_file = df.to_excel(f"temp_export_{datetime.now().strftime('%Y%m%d_%H%M%S')}.xlsx", index=False)
                                with open(excel_file, "rb") as f:
                                    st.download_button(
                                        label="Download Excel",
                                        data=f,
                                        file_name=f"youtube_shorts_database_{datetime.now().strftime('%Y%m%d_%H%M%S')}.xlsx",
                                        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
                                    )
                            except ImportError:
                                st.warning("Excel export requires openpyxl library")

                    # Detailed view for selected job
                    st.subheader("🔎 Detailed Job View")

                    selected_job_id = st.selectbox(
                        "Select job for detailed view",
                        [job.id for job in filtered_jobs],
                        format_func=lambda x: next(job.episode_data.get("title_options", ["Untitled"])[0] for job in filtered_jobs if job.id == x)
                    )

                    selected_job = next(job for job in filtered_jobs if job.id == selected_job_id)

                    # Job metadata
                    col1, col2, col3 = st.columns(3)

                    with col1:
                        st.write("**Job Information**")
                        st.write(f"ID: {selected_job.id}")
                        st.write(f"Status: {selected_job.status}")
                        st.write(f"Format: {selected_job.format}")
                        st.write(f"Created: {selected_job.created_at}")
                        st.write(f"Updated: {selected_job.updated_at}")

                    with col2:
                        st.write("**YouTube Information**")
                        st.write(f"ID: {selected_job.youtube_id or 'Not uploaded'}")
                        st.write(f"Scheduled: {selected_job.scheduled_publish_time or 'Not scheduled'}")
                        st.write(f"Published: {selected_job.actual_publish_time or 'Not published'}")
                        st.write(f"Privacy: {selected_job.privacy_status}")

                    with col3:
                        st.write("**Cost Information**")
                        st.write(f"Generation: €{selected_job.generation_cost:.2f}")
                        st.write(f"Render: €{selected_job.render_cost:.2f}")
                        st.write(f"Total: €{selected_job.generation_cost + selected_job.render_cost:.2f}")
                        st.write(f"Retries: {selected_job.retry_count}")

                    # Episode data
                    if selected_job.episode_data:
                        st.write("**Episode Data**")
                        episode_df = pd.DataFrame.from_dict(selected_job.episode_data, orient="index")
                        st.dataframe(episode_df)

                    # Performance metrics
                    if selected_job.metrics:
                        st.write("**Performance Metrics**")

                        metrics_data = []
                        for metric in selected_job.metrics:
                            metrics_data.append({
                                "Window": metric.window,
                                "Views": metric.views,
                                "Likes": metric.likes,
                                "Comments": metric.comments,
                                "Avg Duration (s)": metric.avg_view_duration,
                                "Avg View %": f"{metric.avg_view_percentage:.1f}%",
                                "Subscribers Gained": metric.subscribers_gained,
                                "Timestamp": metric.timestamp
                            })

                        metrics_df = pd.DataFrame(metrics_data)
                        st.dataframe(metrics_df)

                        # Create charts
                        col1, col2 = st.columns(2)

                        with col1:
                            st.write("**Views & Likes Over Time**")
                            st.line_chart(metrics_df.set_index("Window")[["Views", "Likes"]])

                        with col2:
                            st.write("**Engagement Metrics**")
                            st.bar_chart(metrics_df.set_index("Window")[["Avg View %", "Subscribers Gained"]])

                    # Error information
                    if selected_job.error_message:
                        st.error(f"**Error Information:** {selected_job.error_message}")

                except ImportError:
                    st.dataframe(df)

                    # Basic export functionality without AgGrid
                    st.subheader("📤 Export Data")

                    col1, col2 = st.columns(2)

                    with col1:
                        if st.button("📥 Export to CSV"):
                            csv = df.to_csv(index=False)
                            st.download_button(
                                label="Download CSV",
                                data=csv,
                                file_name=f"youtube_shorts_database_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv",
                                mime="text/csv"
                            )

                    with col2:
                        if st.button("📥 Export to JSON"):
                            json_data = df.to_json(orient="records", indent=2)
                            st.download_button(
                                label="Download JSON",
                                data=json_data,
                                file_name=f"youtube_shorts_database_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json",
                                mime="application/json"
                            )

            else:
                st.info("No jobs found matching the current filters. Try adjusting your filter criteria.")

        finally:
            session.close()

if __name__ == "__main__":
    dashboard = Dashboard()
    dashboard.run()
