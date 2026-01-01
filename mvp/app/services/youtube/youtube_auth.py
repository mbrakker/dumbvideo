"""
YouTube Authentication Service

Handles OAuth 2.0 authentication with YouTube Data API
"""

import os
import json
import pickle
from typing import Dict, Optional, Tuple
from datetime import datetime, timedelta
from google_auth_oauthlib.flow import InstalledAppFlow
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from app.utils.logging import get_logger
from app.db.models import Job, VideoStatus
import base64
import hashlib

logger = get_logger(__name__)

class YouTubeAuthError(Exception):
    """Custom exception for authentication failures"""
    pass

class YouTubeAuth:
    def __init__(self):
        self.logger = get_logger(f"{__name__}.YouTubeAuth")

        # OAuth configuration
        self.client_id = os.getenv("YOUTUBE_CLIENT_ID")
        self.client_secret = os.getenv("YOUTUBE_CLIENT_SECRET")
        self.redirect_uri = os.getenv("YOUTUBE_REDIRECT_URI", "urn:ietf:wg:oauth:2.0:oob")

        # Scopes
        self.scopes = [
            "https://www.googleapis.com/auth/youtube.upload",
            "https://www.googleapis.com/auth/youtube",
            "https://www.googleapis.com/auth/youtubepartner"
        ]

        # Token storage
        self.token_dir = os.path.join("data", "tokens")
        os.makedirs(self.token_dir, exist_ok=True)
        self.token_file = os.path.join(self.token_dir, "youtube_token.pickle")

        # Validate configuration
        if not self.client_id or not self.client_secret:
            raise YouTubeAuthError("YouTube OAuth credentials not configured")

        self.logger.info("YouTube auth service initialized",
                       client_id=self.client_id[:10] + "...",
                       scopes=self.scopes)

    def get_auth_url(self) -> str:
        """Generate OAuth authorization URL"""
        try:
            flow = InstalledAppFlow.from_client_config(
                {
                    "installed": {
                        "client_id": self.client_id,
                        "client_secret": self.client_secret,
                        "redirect_uris": [self.redirect_uri],
                        "auth_uri": "https://accounts.google.com/o/oauth2/auth",
                        "token_uri": "https://oauth2.googleapis.com/token"
                    }
                },
                scopes=self.scopes
            )

            auth_url, _ = flow.authorization_url(
                prompt='consent',
                access_type='offline',
                include_granted_scopes='true'
            )

            self.logger.info("Generated auth URL", url=auth_url)
            return auth_url

        except Exception as e:
            self.logger.error("Failed to generate auth URL", error=str(e))
            raise YouTubeAuthError(f"Auth URL generation failed: {str(e)}")

    def exchange_code_for_token(self, authorization_code: str) -> Dict:
        """Exchange authorization code for tokens"""
        try:
            flow = InstalledAppFlow.from_client_config(
                {
                    "installed": {
                        "client_id": self.client_id,
                        "client_secret": self.client_secret,
                        "redirect_uris": [self.redirect_uri],
                        "auth_uri": "https://accounts.google.com/o/oauth2/auth",
                        "token_uri": "https://oauth2.googleapis.com/token"
                    }
                },
                scopes=self.scopes
            )

            # Exchange code for tokens
            credentials = flow.fetch_token(code=authorization_code)

            # Save tokens
            self._save_tokens(credentials)

            self.logger.info("Token exchange successful",
                           expires_in=credentials.get('expires_in'))

            return {
                "status": "success",
                "access_token": credentials.get('access_token'),
                "refresh_token": credentials.get('refresh_token'),
                "expires_in": credentials.get('expires_in')
            }

        except Exception as e:
            self.logger.error("Token exchange failed", error=str(e))
            raise YouTubeAuthError(f"Token exchange failed: {str(e)}")

    def get_credentials(self) -> Optional[Credentials]:
        """Get valid credentials (auto-refresh if needed)"""
        try:
            # Load tokens from file
            credentials = self._load_tokens()

            if not credentials:
                self.logger.warning("No stored credentials found")
                return None

            # Check if credentials are expired
            if credentials.expired:
                if credentials.refresh_token:
                    self.logger.info("Refreshing expired credentials")
                    credentials.refresh(Request())
                    self._save_tokens({
                        'token': credentials.token,
                        'refresh_token': credentials.refresh_token,
                        'token_uri': credentials.token_uri,
                        'client_id': credentials.client_id,
                        'client_secret': credentials.client_secret,
                        'scopes': credentials.scopes
                    })
                else:
                    self.logger.error("No refresh token available")
                    return None

            self.logger.debug("Returning valid credentials",
                            expires_at=credentials.expires_at)

            return credentials

        except Exception as e:
            self.logger.error("Failed to get credentials", error=str(e))
            return None

    def _load_tokens(self) -> Optional[Credentials]:
        """Load tokens from storage"""
        try:
            if not os.path.exists(self.token_file):
                return None

            with open(self.token_file, 'rb') as token:
                credentials_data = pickle.load(token)

            return Credentials.from_authorized_user_info(
                credentials_data,
                self.scopes
            )

        except Exception as e:
            self.logger.error("Failed to load tokens", error=str(e))
            return None

    def _save_tokens(self, credentials_data: Dict):
        """Save tokens to storage"""
        try:
            with open(self.token_file, 'wb') as token:
                pickle.dump(credentials_data, token)

            self.logger.info("Saved OAuth tokens", file=self.token_file)

        except Exception as e:
            self.logger.error("Failed to save tokens", error=str(e))
            raise YouTubeAuthError(f"Token save failed: {str(e)}")

    def revoke_tokens(self) -> bool:
        """Revoke current tokens"""
        try:
            credentials = self._load_tokens()
            if not credentials:
                return True

            # Revoke token
            revoke_url = "https://oauth2.googleapis.com/revoke"
            requests.post(revoke_url, params={'token': credentials.token})

            # Remove token file
            if os.path.exists(self.token_file):
                os.remove(self.token_file)

            self.logger.info("Tokens revoked successfully")
            return True

        except Exception as e:
            self.logger.error("Failed to revoke tokens", error=str(e))
            return False

    def get_token_status(self) -> Dict:
        """Get current token status"""
        try:
            credentials = self._load_tokens()

            if not credentials:
                return {
                    "status": "not_authenticated",
                    "message": "No stored credentials"
                }

            if credentials.expired:
                return {
                    "status": "expired",
                    "message": "Credentials expired",
                    "has_refresh_token": bool(credentials.refresh_token)
                }

            expires_at = credentials.expires_at
            if expires_at:
                expires_in = (expires_at - datetime.utcnow()).total_seconds()
            else:
                expires_in = None

            return {
                "status": "valid",
                "expires_in": expires_in,
                "scopes": list(credentials.scopes),
                "token_type": "Bearer"
            }

        except Exception as e:
            self.logger.error("Failed to get token status", error=str(e))
            return {
                "status": "error",
                "message": str(e)
            }

    def encrypt_tokens(self, credentials_data: Dict) -> str:
        """Encrypt credentials for storage (basic obfuscation)"""
        try:
            # Simple encryption for demo purposes
            # In production, use proper encryption
            json_data = json.dumps(credentials_data)
            encrypted = base64.b64encode(json_data.encode()).decode()
            return encrypted

        except Exception as e:
            self.logger.error("Failed to encrypt tokens", error=str(e))
            raise YouTubeAuthError(f"Encryption failed: {str(e)}")

    def decrypt_tokens(self, encrypted_data: str) -> Dict:
        """Decrypt credentials from storage"""
        try:
            decrypted = base64.b64decode(encrypted_data.encode()).decode()
            return json.loads(decrypted)

        except Exception as e:
            self.logger.error("Failed to decrypt tokens", error=str(e))
            raise YouTubeAuthError(f"Decryption failed: {str(e)}")

    def get_authenticated_client(self):
        """Get authenticated YouTube client"""
        try:
            from googleapiclient.discovery import build

            credentials = self.get_credentials()
            if not credentials:
                raise YouTubeAuthError("No valid credentials available")

            return build('youtube', 'v3', credentials=credentials)

        except Exception as e:
            self.logger.error("Failed to create authenticated client", error=str(e))
            raise YouTubeAuthError(f"Client creation failed: {str(e)}")

# Global auth instance
youtube_auth = YouTubeAuth()
