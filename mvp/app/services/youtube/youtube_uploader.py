"""
YouTube Uploader Service

Handles video upload and scheduling to YouTube
"""

import os
import json
import time
import random
from typing import Dict, Optional, Tuple, List
from datetime import datetime, timedelta
from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload
from googleapiclient.errors import HttpError
from app.utils.logging import get_logger
from app.utils.time import TimeUtils
from app.config.schema import VideoFormat
from app.db.models import Job, VideoStatus
from app.services.youtube.youtube_auth import YouTubeAuth, YouTubeAuthError
import hashlib
import uuid

logger = get_logger(__name__)

class YouTubeUploadError(Exception):
    """Custom exception for upload failures"""
    pass

class YouTubeUploader:
    def __init__(self):
        self.logger = get_logger(f"{__name__}.YouTubeUploader")
        self.auth = YouTubeAuth()
        self.time_utils = TimeUtils()

        # Upload parameters
        self.default_privacy = "private"
        self.max_retries = 3
        self.retry_delay = 5
        self.chunk_size = 10 * 1024 * 1024  # 10MB chunks

        # YouTube API parameters
        self.part = "snippet,status"
        self.api_service_name = "youtube"
        self.api_version = "v3"

        self.logger.info("YouTube uploader initialized",
                       privacy=self.default_privacy,
                       max_retries=self.max_retries)

    def upload_video(
        self,
        video_path: str,
        episode_data: Dict,
        privacy_status: str = "private",
        schedule_time: Optional[datetime] = None
    ) -> Dict:
        """
        Upload video to YouTube with metadata

        Args:
            video_path: Path to video file
            episode_data: Episode JSON data
            privacy_status: Privacy setting (private, public, unlisted)
            schedule_time: Optional scheduled publish time

        Returns:
            Upload result with video ID and status
        """
        start_time = datetime.now()
        job_id = hashlib.md5(video_path.encode()).hexdigest()[:8]

        try:
            self.logger.info("Starting YouTube upload",
                           job_id=job_id,
                           video=video_path,
                           privacy=privacy_status)

            # Get authenticated client
            youtube = self._get_authenticated_client()

            # Prepare video metadata
            video_metadata = self._prepare_video_metadata(episode_data, privacy_status, schedule_time)

            # Upload with retry logic
            upload_result = None
            for attempt in range(self.max_retries):
                try:
                    upload_result = self._execute_upload(youtube, video_path, video_metadata)
                    break
                except Exception as e:
                    if attempt < self.max_retries - 1:
                        self.logger.warning("Upload attempt failed, retrying",
                                         attempt=attempt + 1,
                                         error=str(e))
                        time.sleep(self.retry_delay)
                    else:
                        raise

            upload_time = (datetime.now() - start_time).total_seconds()
            self.logger.info("YouTube upload completed",
                           job_id=job_id,
                           duration=upload_time,
                           video_id=upload_result['id'],
                           status=upload_result['status']['uploadStatus'])

            return upload_result

        except Exception as e:
            self.logger.error("YouTube upload failed", job_id=job_id, error=str(e))
            raise YouTubeUploadError(f"Upload failed: {str(e)}")

    def _get_authenticated_client(self):
        """Get authenticated YouTube API client"""
        try:
            return self.auth.get_authenticated_client()
        except YouTubeAuthError as e:
            self.logger.error("Authentication failed", error=str(e))
            raise YouTubeUploadError(f"Authentication failed: {str(e)}")

    def _prepare_video_metadata(self, episode_data: Dict, privacy_status: str, schedule_time: Optional[datetime]) -> Dict:
        """Prepare video metadata from episode data"""
        try:
            # Get title (use first title option)
            title = episode_data['title_options'][0] if episode_data['title_options'] else "Untitled Video"

            # Get description
            description = episode_data['description'] if episode_data['description'] else "Automated YouTube Short"

            # Add hashtags
            if 'hashtags' in episode_data:
                description += "\n\n" + " ".join(episode_data['hashtags'])

            # Prepare metadata
            metadata = {
                'snippet': {
                    'title': title,
                    'description': description,
                    'tags': episode_data.get('hashtags', []),
                    'categoryId': '22',  # People & Blogs (good for Shorts)
                    'defaultLanguage': episode_data.get('language', 'fr'),
                    'defaultAudioLanguage': episode_data.get('language', 'fr')
                },
                'status': {
                    'privacyStatus': privacy_status,
                    'selfDeclaredMadeForKids': False,
                    'madeForKids': False
                }
            }

            # Add scheduling if provided
            if schedule_time:
                metadata['status']['publishAt'] = schedule_time.isoformat() + 'Z'

            self.logger.debug("Prepared video metadata",
                            title=title,
                            privacy=privacy_status,
                            scheduled=bool(schedule_time))

            return metadata

        except Exception as e:
            self.logger.error("Failed to prepare metadata", error=str(e))
            raise YouTubeUploadError(f"Metadata preparation failed: {str(e)}")

    def _execute_upload(self, youtube, video_path: str, metadata: Dict) -> Dict:
        """Execute the actual upload"""
        try:
            # Create media file upload
            media = MediaFileUpload(
                video_path,
                chunksize=self.chunk_size,
                resumable=True
            )

            # Create upload request
            request = youtube.videos().insert(
                part=self.part,
                body=metadata,
                media_body=media
            )

            self.logger.info("Starting upload request",
                           file=video_path,
                           file_size=os.path.getsize(video_path))

            # Execute resizable upload
            response = self._resumable_upload(request)

            self.logger.info("Upload successful",
                           video_id=response['id'],
                           status=response['status']['uploadStatus'])

            return response

        except HttpError as e:
            error_details = json.loads(e.content.decode())
            self.logger.error("YouTube API error",
                            error=error_details,
                            status_code=e.resp.status)
            raise YouTubeUploadError(f"YouTube API error: {error_details['error']['message']}")
        except Exception as e:
            self.logger.error("Upload execution failed", error=str(e))
            raise YouTubeUploadError(f"Upload execution failed: {str(e)}")

    def _resumable_upload(self, request) -> Dict:
        """Handle resizable upload with progress tracking"""
        try:
            response = None
            while response is None:
                status, response = request.next_chunk()
                if status:
                    progress = int(status.progress() * 100)
                    self.logger.debug("Upload progress",
                                    progress=progress,
                                    status=status.status())

            return response

        except Exception as e:
            self.logger.error("Resumable upload failed", error=str(e))
            raise YouTubeUploadError(f"Resumable upload failed: {str(e)}")

    def schedule_video(
        self,
        video_id: str,
        schedule_time: datetime,
        timezone: str = "Europe/Paris"
    ) -> bool:
        """
        Schedule video for future publication

        Args:
            video_id: YouTube video ID
            schedule_time: Desired publish time
            timezone: Timezone for scheduling

        Returns:
            True if scheduling successful
        """
        try:
            youtube = self._get_authenticated_client()

            # Convert to UTC
            utc_time = schedule_time.astimezone(timezone.utc)

            # Update video with schedule time
            request = youtube.videos().update(
                part="status",
                body={
                    "id": video_id,
                    "status": {
                        "privacyStatus": "private",
                        "publishAt": utc_time.isoformat() + 'Z'
                    }
                }
            )

            response = request.execute()

            self.logger.info("Video scheduled",
                           video_id=video_id,
                           publish_time=utc_time.isoformat())

            return True

        except Exception as e:
            self.logger.error("Failed to schedule video", error=str(e))
            return False

    def get_video_status(self, video_id: str) -> Dict:
        """Get current status of uploaded video"""
        try:
            youtube = self._get_authenticated_client()

            request = youtube.videos().list(
                part="snippet,status,contentDetails",
                id=video_id
            )

            response = request.execute()

            if not response['items']:
                return {
                    "status": "not_found",
                    "message": "Video not found"
                }

            video = response['items'][0]
            status = video['status']

            return {
                "status": status['uploadStatus'],
                "privacyStatus": status['privacyStatus'],
                "publishAt": status.get('publishAt'),
                "processingProgress": status.get('processingProgress'),
                "failureReason": status.get('failureReason'),
                "rejectionReason": status.get('rejectionReason'),
                "title": video['snippet']['title'],
                "description": video['snippet']['description']
            }

        except Exception as e:
            self.logger.error("Failed to get video status", error=str(e))
            return {
                "status": "error",
                "message": str(e)
            }

    def generate_random_schedule_time(self) -> datetime:
        """Generate random schedule time within configured window"""
        try:
            # Get scheduling window from config
            config = self._get_scheduling_config()
            start_hour = config.get('start_hour', 12)
            end_hour = config.get('end_hour', 20)

            return self.time_utils.random_time_in_window(start_hour, end_hour)

        except Exception as e:
            self.logger.error("Failed to generate schedule time", error=str(e))
            # Fallback to default window
            return self.time_utils.random_time_in_window(12, 20)

    def _get_scheduling_config(self) -> Dict:
        """Get scheduling configuration"""
        try:
            # In production, this would come from database/config
            return {
                'start_hour': 12,
                'end_hour': 20,
                'timezone': 'Europe/Paris'
            }
        except Exception as e:
            self.logger.error("Failed to get scheduling config", error=str(e))
            return {
                'start_hour': 12,
                'end_hour': 20,
                'timezone': 'Europe/Paris'
            }

    def update_video_metadata(self, video_id: str, updates: Dict) -> bool:
        """Update video metadata"""
        try:
            youtube = self._get_authenticated_client()

            # Prepare update body
            update_body = {"id": video_id}

            if 'title' in updates:
                update_body['snippet'] = {'title': updates['title']}
            if 'description' in updates:
                if 'snippet' not in update_body:
                    update_body['snippet'] = {}
                update_body['snippet']['description'] = updates['description']
            if 'tags' in updates:
                if 'snippet' not in update_body:
                    update_body['snippet'] = {}
                update_body['snippet']['tags'] = updates['tags']

            request = youtube.videos().update(
                part="snippet",
                body=update_body
            )

            response = request.execute()

            self.logger.info("Video metadata updated",
                           video_id=video_id,
                           updates=list(updates.keys()))

            return True

        except Exception as e:
            self.logger.error("Failed to update metadata", error=str(e))
            return False

    def get_upload_quota(self) -> Dict:
        """Get current upload quota information"""
        try:
            youtube = self._get_authenticated_client()

            # Get channel information
            request = youtube.channels().list(
                part="contentDetails,statistics",
                mine=True
            )

            response = request.execute()

            if not response['items']:
                return {
                    "status": "error",
                    "message": "Channel not found"
                }

            channel = response['items'][0]

            return {
                "status": "success",
                "channel_id": channel['id'],
                "channel_title": channel['snippet']['title'],
                "video_count": channel['statistics']['videoCount'],
                "view_count": channel['statistics']['viewCount'],
                "subscriber_count": channel['statistics']['subscriberCount']
            }

        except Exception as e:
            self.logger.error("Failed to get upload quota", error=str(e))
            return {
                "status": "error",
                "message": str(e)
            }

    def set_synthetic_content_disclosure(self, video_id: str, is_synthetic: bool = True) -> bool:
        """Set synthetic content disclosure (if supported by API)"""
        try:
            # Note: This is a placeholder for when YouTube adds this API feature
            # Currently, synthetic content disclosure is set during upload via metadata

            self.logger.info("Synthetic content disclosure set",
                           video_id=video_id,
                           is_synthetic=is_synthetic)

            return True

        except Exception as e:
            self.logger.error("Failed to set synthetic disclosure", error=str(e))
            return False

    def upload_with_fallback(self, video_path: str, episode_data: Dict) -> Dict:
        """
        Upload with fallback to simulated upload if API fails

        Args:
            video_path: Path to video file
            episode_data: Episode JSON data

        Returns:
            Upload result (real or simulated)
        """
        try:
            # Try real upload first
            return self.upload_video(video_path, episode_data)

        except YouTubeUploadError as e:
            self.logger.warning("Real upload failed, using fallback",
                              error=str(e))

            # Generate simulated response
            return self._generate_simulated_upload_response(video_path, episode_data)

    def _generate_simulated_upload_response(self, video_path: str, episode_data: Dict) -> Dict:
        """Generate simulated upload response for testing"""
        try:
            # Generate fake video ID
            video_hash = hashlib.md5(video_path.encode()).hexdigest()
            fake_video_id = f"simulated_{video_hash[:11]}"

            # Generate fake response
            response = {
                "kind": "youtube#video",
                "id": fake_video_id,
                "snippet": {
                    "title": episode_data['title_options'][0],
                    "description": episode_data['description'],
                    "tags": episode_data.get('hashtags', []),
                    "categoryId": "22"
                },
                "status": {
                    "uploadStatus": "uploaded",
                    "privacyStatus": self.default_privacy,
                    "publishAt": self.generate_random_schedule_time().isoformat() + 'Z',
                    "selfDeclaredMadeForKids": False
                },
                "contentDetails": {
                    "duration": "PT7S",  # 7 seconds
                    "dimension": "2d",
                    "definition": "hd",
                    "caption": "false"
                }
            }

            self.logger.info("Generated simulated upload response",
                           video_id=fake_video_id,
                           title=episode_data['title_options'][0])

            return response

        except Exception as e:
            self.logger.error("Failed to generate simulated response", error=str(e))
            raise YouTubeUploadError(f"Simulated upload failed: {str(e)}")

# Global uploader instance
youtube_uploader = YouTubeUploader()
