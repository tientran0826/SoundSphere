from fastapi import APIRouter, HTTPException
from loguru import logger

from api.dependencies import get_repo
from api.models import ConfigResponse, ConfigUpdate, SuccessResponse

router = APIRouter(prefix="/api/config", tags=["Config"])


@router.get("/{guild_id}", response_model=ConfigResponse)
async def get_config(guild_id: int):
    """Get server configuration"""
    try:
        repo = get_repo()
        config = repo.get_server_config(guild_id)
        return ConfigResponse(
            success=True,
            config={
                "guild_id": config.guild_id,
                "command_prefix": config.command_prefix,
                "default_channel_id": config.default_channel_id,
            },
        )
    except Exception as e:
        logger.error(f"Error getting config: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.put("/{guild_id}", response_model=SuccessResponse)
async def update_config(guild_id: int, config: ConfigUpdate):
    """Update server configuration"""
    try:
        repo = get_repo()
        success = repo.update_server_config(
            guild_id, config.command_prefix, config.default_channel_id
        )

        if success:
            return SuccessResponse(success=True, message="Config updated successfully")
        else:
            raise HTTPException(status_code=500, detail="Failed to update config")
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error updating config: {e}")
        raise HTTPException(status_code=500, detail=str(e))
