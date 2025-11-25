from typing import List

import wavelink
from fastapi import APIRouter, HTTPException
from loguru import logger

from api.dependencies import get_bot, get_repo, verify_user_in_voice
from api.models import (
    AlbumCreate,
    AlbumResponse,
    AlbumTrackResponse,
    AlbumTracksResponse,
    SuccessResponse,
    TrackCreate,
)

router = APIRouter(prefix="/api/albums", tags=["Albums"])


@router.get("/{guild_id}", response_model=List[AlbumResponse])
async def get_albums(guild_id: int):
    """Get all albums for a guild"""
    try:
        repo = get_repo()
        albums = repo.get_all_albums(guild_id)
        return [
            AlbumResponse(
                id=a.id,
                name=a.album_name,
                created_by=a.created_by,
                track_count=len(a.tracks),
            )
            for a in albums
        ]
    except Exception as e:
        logger.error(f"Error getting albums: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/{guild_id}/{album_name}", response_model=AlbumTracksResponse)
async def get_album_tracks(guild_id: int, album_name: str):
    """Get tracks from specific album"""
    try:
        repo = get_repo()
        tracks = repo.get_album_tracks(guild_id, album_name)
        albums = repo.get_all_albums(guild_id)
        album_obj = next((a for a in albums if a.album_name == album_name), None)

        if not album_obj:
            raise HTTPException(
                status_code=404, detail=f"Album '{album_name}' not found"
            )

        return AlbumTracksResponse(
            success=True,
            album_name=album_name,
            tracks=[
                AlbumTrackResponse(
                    track_number=t.track_number,
                    title=t.track_title,
                    identifier=t.identifier,
                    author=t.track_author,
                    url=t.url,
                    requested_by=t.requested_by,
                )
                for t in sorted(tracks, key=lambda x: x.track_number)
            ],
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting album tracks: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/{guild_id}", response_model=SuccessResponse)
async def create_album(guild_id: int, album: AlbumCreate):
    """Create new album"""
    try:
        repo = get_repo()
        success = repo.create_album(guild_id, album.album_name, album.requested_by)

        if success:
            return SuccessResponse(
                success=True, message=f'Album "{album.album_name}" created'
            )
        else:
            raise HTTPException(status_code=500, detail="Failed to create album")
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error creating album: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.delete("/{guild_id}/{album_name}", response_model=SuccessResponse)
async def delete_album(guild_id: int, album_name: str):
    """Delete album and all its tracks"""
    try:
        repo = get_repo()
        success = repo.remove_album(guild_id, album_name)
        if success:
            return SuccessResponse(
                success=True, message=f"Album '{album_name}' deleted"
            )
        else:
            raise HTTPException(status_code=404, detail="Album not found")
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error deleting album: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/{guild_id}/{album_name}/tracks", response_model=SuccessResponse)
async def add_track_to_album(guild_id: int, album_name: str, track: TrackCreate):
    """Add track to album"""
    try:
        repo = get_repo()
        album = repo.get_album_by_name(guild_id, album_name)
        if not album:
            raise HTTPException(
                status_code=404, detail=f"Album '{album_name}' not found"
            )

        added_track = repo.add_track_to_album(
            album.id,
            track.track_title,
            track.url,
            track.identifier,
            track.track_author,
            track.requested_by,
        )

        if added_track:
            return SuccessResponse(
                success=True,
                message=f'Track "{track.track_title}" added to album "{album_name}"',
            )
        else:
            raise HTTPException(status_code=500, detail="Failed to add track to album")
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error adding track to album: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.delete(
    "/{guild_id}/{album_name}/tracks/{track_number}", response_model=SuccessResponse
)
async def remove_track_from_album(guild_id: int, album_name: str, track_number: int):
    """Remove track from album by track number"""
    try:
        repo = get_repo()
        success, track_title = repo.remove_track_from_album_by_number(
            guild_id, album_name, track_number
        )

        if success:
            return SuccessResponse(
                success=True,
                message=f'Track "{track_title}" removed from album "{album_name}"',
            )
        else:
            raise HTTPException(
                status_code=404,
                detail=f"Album '{album_name}' or track #{track_number} not found",
            )
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error removing track from album: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/{guild_id}/{album_name}/play", response_model=SuccessResponse)
async def play_album_queue(guild_id: int, user_id: int, album_name: str):
    """Play first track and add remaining album tracks to queue"""
    try:
        bot = get_bot()
        repo = get_repo()
        guild = bot.get_guild(guild_id)
        vc = guild.voice_client

        if not guild:
            raise HTTPException(status_code=404, detail="Guild not found")

        album_tracks = repo.add_album_to_queue(guild_id, album_name)
        if not album_tracks:
            raise HTTPException(
                status_code=404,
                detail=f"Album '{album_name}' not found or has no tracks",
            )

        # Verify user is in voice channel
        is_valid, message, user_channel, bot_channel = verify_user_in_voice(
            guild, user_id, require_same_channel=True
        )
        if not is_valid:
            raise HTTPException(status_code=403, detail=message)

        # Clear existing queue
        repo.clear_queue(guild_id)

        # Add all tracks to queue
        for track in album_tracks:
            repo.save_to_queue(
                guild_id,
                track["track_title"],
                track["url"],
                track["identifier"],
                track["track_author"],
                track["requested_by"],
            )

        # Pop first track to play immediately
        first_track = repo.pop_next_track(guild_id)
        tracks = await wavelink.Playable.search(first_track.url)
        playable = next((t for t in tracks if t.title == first_track.track_title), None)
        if not playable:
            raise HTTPException(status_code=404, detail="First track not found")

        # Play first track
        await vc.play(playable)

        # Save play history
        repo.save_play_history(
            guild_id,
            user_id,
            playable.title,
            playable.identifier,
            playable.author,
            playable.uri,
        )

        return SuccessResponse(
            success=True,
            message=f'Now playing: {playable.title}, album "{album_name}" ({len(album_tracks)-1} tracks remaining in queue).',
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error adding album to queue: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/{guild_id}/{album_name}/add", response_model=SuccessResponse)
async def add_album_to_queue(guild_id: int, album_name: str):
    """Add all album tracks to queue"""
    try:
        repo = get_repo()
        album_tracks = repo.add_album_to_queue(guild_id, album_name)
        if not album_tracks:
            raise HTTPException(
                status_code=404,
                detail=f"Album '{album_name}' not found or has no tracks",
            )

        for track in album_tracks:
            repo.save_to_queue(
                guild_id,
                track["track_title"],
                track["url"],
                track["identifier"],
                track["track_author"],
                track["requested_by"],
            )

        return SuccessResponse(
            success=True,
            message=f'Album "{album_name}" ({len(album_tracks)} tracks) added to queue',
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error adding album to queue: {e}")
        raise HTTPException(status_code=500, detail=str(e))
