import wavelink
from fastapi import APIRouter, HTTPException
from loguru import logger

from api.dependencies import get_bot, get_repo
from api.models import QueueResponse, SuccessResponse, TrackCreate, TrackResponse

router = APIRouter(prefix="/api/queue", tags=["Queue"])


@router.get("/{guild_id}", response_model=QueueResponse)
async def get_queue(guild_id: int):
    """Get queue for a guild"""
    try:
        repo = get_repo()
        tracks = repo.get_all_tracks_from_queue(guild_id)
        return QueueResponse(
            success=True,
            queue=[
                TrackResponse(
                    position=t.position,
                    title=t.track_title,
                    author=t.track_author,
                    url=t.url,
                    requested_by=t.requested_by,
                    identifier=t.identifier,
                )
                for t in tracks
            ],
        )
    except Exception as e:
        logger.error(f"Error getting queue: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/{guild_id}", response_model=SuccessResponse)
async def add_to_queue(guild_id: int, track: TrackCreate):
    """Add track to queue"""
    try:

        repo = get_repo()
        success = repo.save_to_queue(
            guild_id,
            track.track_title,
            track.url,
            track.identifier,
            track.track_author,
            track.requested_by,
        )

        if success:
            return SuccessResponse(
                success=True, message=f'Track "{track.track_title}" added to queue'
            )
        else:
            raise HTTPException(status_code=500, detail="Failed to add track")
    except HTTPException:
        raise
    except Exception as e:
        # Đảm bảo log được ghi lại
        logger.error(f"Error adding to queue for Guild {guild_id}: {e}")
        raise HTTPException(status_code=500, detail=f"Internal Server Error: {str(e)}")


@router.delete("/{guild_id}/{position}", response_model=SuccessResponse)
async def remove_from_queue(guild_id: int, position: int):
    """Remove track from queue by position"""
    try:
        repo = get_repo()
        success = repo.remove_from_queue(guild_id, position)
        if success:
            return SuccessResponse(success=True, message="Track removed from queue")
        else:
            raise HTTPException(status_code=404, detail="Track not found")
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error removing from queue: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/{guild_id}/jump", response_model=SuccessResponse)
async def jump_to_track(guild_id: int, index: int):
    """Jump to a track: play immediately, remove from queue, save to history"""
    try:
        bot = get_bot()
        repo = get_repo()
        guild = bot.get_guild(guild_id)

        if not guild:
            raise HTTPException(status_code=404, detail="Guild not found")

        vc = guild.voice_client
        if not vc:
            raise HTTPException(
                status_code=400, detail="Bot not connected to voice channel"
            )

        # Get the track
        queue = repo.get_all_tracks_from_queue(guild_id)
        track_to_play = next((t for t in queue if t.position == index), None)

        tracks = await wavelink.Playable.search(track_to_play.url)
        if not tracks:
            raise HTTPException(status_code=404, detail="Track not found on YouTube")

        # Find the track that matches the original title
        playable = None
        for track in tracks:
            if track.title == track_to_play.track_title:
                playable = track
                repo.remove_from_queue(guild_id, track_to_play.position)
                break

        if playable is None:
            logger.warning(
                f"Exact match not found for '{track_to_play.track_title}'. Using first search result."
            )
            playable = tracks[0]

        # Play
        await vc.play(playable)

        # Save history
        repo.save_play_history(
            guild_id,
            track_to_play.requested_by,
            track_to_play.track_title,
            track_to_play.identifier,
            track_to_play.track_author,
            track_to_play.url,
        )

        return SuccessResponse(
            success=True, message=f"Now playing: {track_to_play.track_title}"
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error jumping to track: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.delete("/{guild_id}", response_model=SuccessResponse)
async def clear_queue(guild_id: int):
    """Clear entire queue"""
    try:
        repo = get_repo()
        success = repo.clear_queue(guild_id)
        if success:
            return SuccessResponse(success=True, message="Queue cleared")
        else:
            raise HTTPException(status_code=500, detail="Failed to clear queue")
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error clearing queue: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/{guild_id}/shuffle", response_model=SuccessResponse)
async def shuffle_queue(guild_id: int):
    """Shuffle queue"""
    try:
        repo = get_repo()
        success = repo.shuffle_queue(guild_id)
        if success:
            return SuccessResponse(success=True, message="Queue shuffled")
        else:
            raise HTTPException(status_code=500, detail="Failed to shuffle queue")
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error shuffling queue: {e}")
        raise HTTPException(status_code=500, detail=str(e))
