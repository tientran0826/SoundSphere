from typing import List

from fastapi import APIRouter, HTTPException, Query
from loguru import logger

from api.dependencies import get_repo
from api.models import HistoryResponse

router = APIRouter(prefix="/api/history", tags=["History"])


@router.get("/{guild_id}", response_model=List[HistoryResponse])
async def get_history(guild_id: int, limit: int = Query(10, ge=1, le=100)):
    """Get play history for a guild"""
    try:
        repo = get_repo()
        history = repo.get_play_history(guild_id, limit)

        return [
            HistoryResponse(
                title=h.track_title,
                author=h.track_author,
                url=h.url,
                played_by=h.user_id,
                played_at=h.played_at.isoformat(),
            )
            for h in history
        ]
    except Exception as e:
        logger.error(f"Error getting history: {e}")
        raise HTTPException(status_code=500, detail=str(e))
