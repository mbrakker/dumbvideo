"""
Audio Generation Contract Models

Defines data contracts for text-to-speech and audio processing services
"""

from dataclasses import dataclass
from typing import Optional, Dict, Any, List
from datetime import datetime


@dataclass
class TTSGenerationRequest:
    """Request contract for TTS generation"""
    text: str
    model: str = "tts-1-hd"  # tts-1 or tts-1-hd
    voice: str = "alloy"  # alloy, echo, fable, onyx, nova, shimmer
    speed: float = 1.0  # 0.25 to 4.0
    seed: Optional[int] = None  # For reproducible randomness
    user_id: Optional[str] = None
    request_id: str = ""
    schema_version: str = "1.0"


@dataclass
class TTSGenerationResponse:
    """Response contract from TTS generation service"""
    request: TTSGenerationRequest
    audio_data: bytes
    duration_seconds: float
    cost_characters: int = 0
    model_used: str = ""
    voice_used: str = ""
    speed_actual: float = 1.0
    seed_used: Optional[int] = None
    generated_at: datetime = None
    error: Optional[str] = None
    request_id: str = ""
    schema_version: str = "1.0"

    def __post_init__(self):
        if self.generated_at is None:
            self.generated_at = datetime.now()


@dataclass
class AudioNormalizationRequest:
    """Request contract for audio normalization"""
    audio_data: bytes
    target_lufs: float = -28.0  # Target loudness in LUFS
    max_peak_level: float = -1.0  # Maximum peak level in dBTP
    sample_rate: int = 44100
    channels: int = 1  # 1 for mono, 2 for stereo
    format: str = "mp3"
    request_id: str = ""
    schema_version: str = "1.0"


@dataclass
class AudioNormalizationResponse:
    """Response contract from audio normalization"""
    request: AudioNormalizationRequest
    normalized_data: bytes
    original_lufs: Optional[float] = None
    final_lufs: Optional[float] = None
    peak_level: Optional[float] = None
    compression_applied: bool = False
    duration_seconds: float = 0.0
    processed_at: datetime = None
    error: Optional[str] = None
    request_id: str = ""
    schema_version: str = "1.0"

    def __post_init__(self):
        if self.processed_at is None:
            self.processed_at = datetime.now()


@dataclass
class AudioMixRequest:
    """Request contract for audio mixing"""
    voice_audio: bytes
    music_audio: Optional[bytes] = None
    voice_volume_db: float = -12.0
    music_volume_db: float = -20.0
    ducking_threshold: float = 0.02
    ducking_ratio: float = 8.0
    ducking_attack: float = 10.0
    ducking_release: float = 150.0
    crossfade_duration: float = 0.5
    output_format: str = "mp3"
    sample_rate: int = 44100
    request_id: str = ""
    schema_version: str = "1.0"


@dataclass
class AudioMixResponse:
    """Response contract from audio mixing"""
    request: AudioMixRequest
    mixed_audio: bytes
    voice_duration: float
    music_duration: Optional[float] = None
    final_duration: float = 0.0
    ducking_applied: bool = False
    mixed_at: datetime = None
    error: Optional[str] = None
    request_id: str = ""
    schema_version: str = "1.0"

    def __post_init__(self):
        if self.mixed_at is None:
            self.mixed_at = datetime.now()


@dataclass
class AudioAnalysisRequest:
    """Request for audio file analysis"""
    audio_data: bytes
    include_waveform: bool = False
    include_spectrogram: bool = False
    request_id: str = ""
    schema_version: str = "1.0"


@dataclass
class AudioAnalysisResponse:
    """Response from audio analysis"""
    request: AudioAnalysisRequest
    duration_seconds: float
    sample_rate: int
    channels: int
    bit_depth: int
    lufs: Optional[float] = None
    peak_level_db: Optional[float] = None
    rms_level_db: Optional[float] = None
    dynamic_range_db: Optional[float] = None
    waveform_data: Optional[List[float]] = None
    spectrogram_data: Optional[List[List[float]]] = None
    analyzed_at: datetime = None
    error: Optional[str] = None
    request_id: str = ""
    schema_version: str = "1.0"

    def __post_init__(self):
        if self.analyzed_at is None:
            self.analyzed_at = datetime.now()


@dataclass
class MusicValidationRequest:
    """Request for background music validation"""
    music_directory: str
    required_formats: List[str] = None  # ["mp3", "wav", "m4a"]
    min_duration_seconds: float = 30.0
    validate_loudness: bool = True
    request_id: str = ""
    schema_version: str = "1.0"

    def __post_init__(self):
        if self.required_formats is None:
            self.required_formats = ["mp3", "wav", "m4a"]


@dataclass
class MusicValidationResponse:
    """Response from music validation"""
    request: MusicValidationRequest
    music_available: bool = False
    total_tracks: int = 0
    valid_tracks: int = 0
    format_breakdown: Dict[str, int] = None  # format -> count
    average_duration: Optional[float] = None
    average_lufs: Optional[float] = None
    selected_tracks: Optional[List[Dict[str, Any]]] = None
    validated_at: datetime = None
    error: Optional[str] = None
    request_id: str = ""
    schema_version: str = "1.0"

    def __post_init__(self):
        if self.format_breakdown is None:
            self.format_breakdown = {}
        if self.selected_tracks is None:
            self.selected_tracks = []
        if self.validated_at is None:
            self.validated_at = datetime.now()
