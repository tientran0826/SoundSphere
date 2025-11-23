from typing import Any, Dict, List, Optional

from pydantic import BaseModel


# ----------------------
# Track Models
# ----------------------
class TrackCreate(BaseModel):
    track_title: str
    requested_by: int = 0


class TrackResponse(BaseModel):
    position: int
    title: str
    author: str
    url: str
    requested_by: int


class QueueResponse(BaseModel):
    success: bool
    queue: List[TrackResponse]


# ----------------------
# Album Models
# ----------------------
class AlbumCreate(BaseModel):
    album_name: str
    requested_by: int = 0


class AlbumResponse(BaseModel):
    id: int
    name: str
    created_by: int
    track_count: int


class AlbumTrackResponse(BaseModel):
    track_number: int
    title: str
    author: str
    url: str
    requested_by: int


class AlbumTracksResponse(BaseModel):
    success: bool
    album_name: str
    tracks: List[AlbumTrackResponse]


# ----------------------
# History Models
# ----------------------
class HistoryResponse(BaseModel):
    title: str
    author: str
    url: str
    played_by: int
    played_at: str


# ----------------------
# Config Models
# ----------------------
class ConfigUpdate(BaseModel):
    command_prefix: Optional[str] = None
    default_channel_id: Optional[int] = None


class ConfigResponse(BaseModel):
    success: bool
    config: dict


# ----------------------
# Bot Control Models
# ----------------------
class VoiceControlRequest(BaseModel):
    action: str  # play, pause, resume, skip, stop, disconnect
    user_id: int  # Discord user ID making the request


class UserVoiceCheckResponse(BaseModel):
    success: bool
    in_voice: bool
    channel_name: Optional[str] = None
    same_channel_as_bot: bool = False
    message: str


class BotStatusResponse(BaseModel):
    success: bool
    status: Dict[str, Any]


# ---------------------
# User stqatus
# ---------------------
class CurrentUserStatusRequest(BaseModel):
    user_id: int  # Discord user ID
    is_in_voice: bool
    voice_channel_id: Optional[int] = None


# ----------------------
# Generic Response Models
# ----------------------
class SuccessResponse(BaseModel):
    success: bool
    message: str


class ErrorResponse(BaseModel):
    success: bool = False
    error: str
