from fastapi import APIRouter, HTTPException
from loguru import logger

from api.dependencies import get_repo
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
        logger.error(f"Error adding to queue: {e}")
        raise HTTPException(status_code=500, detail=str(e))


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
