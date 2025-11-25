import wavelink
from fastapi import APIRouter, HTTPException
from loguru import logger

from api.dependencies import get_bot, get_repo, verify_user_in_voice
from api.models import (
    BotStatusResponse,
    SeekRequest,
    SuccessResponse,
    TrackCreate,
    UserVoiceCheckResponse,
    VoiceControlRequest,
    VolumeAbsoluteRequest,
)

router = APIRouter(prefix="/api/bot", tags=["Bot Control"])


@router.get("/status", response_model=BotStatusResponse)
async def get_bot_status():
    """Get overall bot status"""
    try:
        bot = get_bot()
        repo = get_repo()

        guilds_status = []
        for guild in bot.guilds:
            vc = guild.voice_client

            guild_info = {
                "guild_id": guild.id,
                "guild_name": guild.name,
                "connected": vc is not None,
                "channel_name": vc.channel.name if vc and vc.channel else None,
                "playing": vc.playing if vc else False,
                "paused": vc.paused if vc else False,
                "current_track": None,
                "queue_length": len(repo.get_all_tracks_from_queue(guild.id)),
            }

            if vc and vc.current:
                guild_info["current_track"] = {
                    "title": vc.current.title,
                    "author": vc.current.author,
                    "duration": vc.current.length // 1000,
                    "position": vc.position // 1000,
                }

            guilds_status.append(guild_info)

        return BotStatusResponse(
            success=True,
            status={
                "bot_name": bot.user.name,
                "bot_id": bot.user.id,
                "guilds_count": len(bot.guilds),
                "guilds": guilds_status,
            },
        )
    except Exception as e:
        logger.error(f"Error getting bot status: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/{guild_id}/status", response_model=BotStatusResponse)
async def get_guild_status(guild_id: int):
    """Get status for specific guild"""
    try:
        bot = get_bot()
        repo = get_repo()
        guild = bot.get_guild(guild_id)

        if not guild:
            raise HTTPException(status_code=404, detail="Guild not found")

        vc = guild.voice_client

        status = {
            "guild_id": guild.id,
            "guild_name": guild.name,
            "connected": vc is not None,
            "channel_name": vc.channel.name if vc and vc.channel else None,
            "playing": vc.playing if vc else False,
            "paused": vc.paused if vc else False,
            "current_track": None,
            "queue_length": len(repo.get_all_tracks_from_queue(guild.id)),
        }

        if vc and vc.current:
            status["current_track"] = {
                "title": vc.current.title,
                "author": vc.current.author,
                "duration": vc.current.length // 1000,
                "position": vc.position // 1000,
                "uri": vc.current.uri,
                "identifier": vc.current.identifier,
            }

        return BotStatusResponse(success=True, status=status)
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting guild status: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get(
    "/{guild_id}/user/{user_id}/voice-check", response_model=UserVoiceCheckResponse
)
async def check_user_voice(guild_id: int, user_id: int):
    """Check if user is in voice channel and same channel as bot"""
    try:
        bot = get_bot()
        guild = bot.get_guild(guild_id)

        if not guild:
            raise HTTPException(status_code=404, detail="Guild not found")

        member = guild.get_member(user_id)
        if not member:
            return UserVoiceCheckResponse(
                success=False,
                in_voice=False,
                same_channel_as_bot=False,
                message="User not found in guild",
            )

        if not member.voice or not member.voice.channel:
            return UserVoiceCheckResponse(
                success=False,
                in_voice=False,
                same_channel_as_bot=False,
                message="User is not in a voice channel",
            )

        user_channel = member.voice.channel
        bot_vc = guild.voice_client
        bot_channel = bot_vc.channel if bot_vc else None

        same_channel = False
        if bot_channel:
            same_channel = user_channel.id == bot_channel.id

        return UserVoiceCheckResponse(
            success=True,
            in_voice=True,
            channel_name=user_channel.name,
            same_channel_as_bot=same_channel,
            message=f"User is in voice channel: {user_channel.name}"
            + (
                f" (same as bot)"
                if same_channel
                else " (different from bot)" if bot_channel else ""
            ),
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error checking user voice: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/{guild_id}/control", response_model=SuccessResponse)
async def control_playback(guild_id: int, control: VoiceControlRequest):
    """Control bot playback (requires user to be in voice channel)"""
    try:
        bot = get_bot()
        repo = get_repo()
        guild = bot.get_guild(guild_id)

        if not guild:
            raise HTTPException(status_code=404, detail="Guild not found")

        # Verify user is in voice channel
        is_valid, message, user_channel, bot_channel = verify_user_in_voice(
            guild, control.user_id, require_same_channel=True
        )

        if not is_valid:
            raise HTTPException(status_code=403, detail=message)

        vc = guild.voice_client
        if not vc:
            raise HTTPException(
                status_code=400, detail="Bot not connected to voice channel"
            )

        action = control.action.lower()

        if action == "pause":
            if vc.playing and not vc.paused:
                await vc.pause(True)
                return SuccessResponse(success=True, message="Playback paused")
            raise HTTPException(status_code=400, detail="Already paused or not playing")

        elif action == "resume":
            if vc.paused:
                await vc.pause(False)
                return SuccessResponse(success=True, message="Playback resumed")
            raise HTTPException(status_code=400, detail="Not paused")

        elif action == "skip":
            if vc.playing or vc.paused:
                current = vc.current
                await vc.stop()

                next_track = repo.pop_next_track(guild_id)
                if next_track:
                    tracks = await wavelink.Playable.search(next_track.url)
                    if tracks:
                        await vc.play(tracks[0])
                        return SuccessResponse(
                            success=True,
                            message=f"Skipped: {current.title if current else 'track'}",
                        )

                return SuccessResponse(success=True, message="Skipped, queue is empty")
            raise HTTPException(status_code=400, detail="Nothing playing to skip")

        elif action == "stop":
            if vc.playing or vc.paused:
                await vc.stop()
                repo.clear_queue(guild_id)
                return SuccessResponse(
                    success=True, message="Playback stopped and queue cleared"
                )
            raise HTTPException(status_code=400, detail="Nothing playing to stop")

        elif action == "disconnect":
            await vc.disconnect()
            repo.clear_queue(guild_id)
            return SuccessResponse(
                success=True, message="Disconnected from voice channel"
            )

        raise HTTPException(
            status_code=400,
            detail="Invalid action. Use: pause, resume, skip, stop, disconnect",
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error controlling playback: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/{guild_id}/volume_absolute", response_model=SuccessResponse)
async def set_volume_absolute(guild_id: int, volume_req: VolumeAbsoluteRequest):
    """
    Set bot volume directly (0-100).
    """
    bot = get_bot()
    guild = bot.get_guild(guild_id)
    if not guild:
        raise HTTPException(status_code=404, detail="Guild not found")

    is_valid, message, _, _ = verify_user_in_voice(
        guild, volume_req.user_id, require_same_channel=True
    )
    if not is_valid:
        raise HTTPException(status_code=403, detail=message)

    vc = guild.voice_client
    if not vc:
        raise HTTPException(status_code=400, detail="Bot not connected to voice")

    new_volume = max(0, min(100, volume_req.volume))
    await vc.set_volume(new_volume)

    return SuccessResponse(success=True, message=f"Volume set to {new_volume}%")


@router.post("/{guild_id}/connect/{user_id}", response_model=SuccessResponse)
async def connect_to_voice(guild_id: int, user_id: int):
    """Connect bot to user's voice channel"""
    try:
        bot = get_bot()
        guild = bot.get_guild(guild_id)

        if not guild:
            raise HTTPException(status_code=404, detail="Guild not found")

        # Check if bot already connected
        if guild.voice_client:
            return SuccessResponse(
                success=True,
                message=f"Bot already connected to {guild.voice_client.channel.name}",
            )

        # Get user
        member = guild.get_member(user_id)
        if not member:
            raise HTTPException(status_code=404, detail="User not found in guild")

        # Check if user in voice
        if not member.voice or not member.voice.channel:
            raise HTTPException(
                status_code=400, detail="User must be in a voice channel"
            )

        # Connect to user's voice channel
        try:
            vc = await member.voice.channel.connect(cls=wavelink.Player)
            vc.set_volume(50)  # Default volume
            logger.info(
                f"Connected to {member.voice.channel.name} in guild {guild.name}"
            )
            return SuccessResponse(
                success=True, message=f"Connected to {member.voice.channel.name}"
            )
        except Exception as e:
            logger.error(f"Failed to connect: {e}")
            raise HTTPException(
                status_code=500, detail=f"Failed to connect to voice channel: {str(e)}"
            )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error connecting to voice: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/{guild_id}/disconnect", response_model=SuccessResponse)
async def disconnect_from_voice(guild_id: int, user_id: int):
    """Disconnect bot from voice channel"""
    try:
        bot = get_bot()
        repo = get_repo()
        guild = bot.get_guild(guild_id)

        if not guild:
            raise HTTPException(status_code=404, detail="Guild not found")

        # Verify user authorization
        is_valid, message, _, _ = verify_user_in_voice(
            guild, user_id, require_same_channel=True
        )

        if not is_valid:
            raise HTTPException(status_code=403, detail=message)

        vc = guild.voice_client
        if not vc:
            raise HTTPException(status_code=400, detail="Bot not connected to voice")

        channel_name = vc.channel.name
        await vc.disconnect()
        repo.clear_queue(guild_id)

        return SuccessResponse(
            success=True, message=f"Disconnected from {channel_name}"
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error disconnecting: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/{guild_id}/play", response_model=SuccessResponse)
async def play_track_api(guild_id: int, track: TrackCreate):
    """Add track to queue and play if not playing (requires user in voice)"""
    try:
        bot = get_bot()
        repo = get_repo()
        guild = bot.get_guild(guild_id)
        if not guild:
            raise HTTPException(status_code=404, detail="Guild not found")

        # Verify user is in voice channel
        is_valid, message, user_channel, bot_channel = verify_user_in_voice(
            guild, track.requested_by, require_same_channel=True
        )

        if not is_valid:
            raise HTTPException(status_code=403, detail=message)

        vc = guild.voice_client
        if not vc:
            raise HTTPException(
                status_code=400,
                detail="Bot not connected to voice channel. Use Discord to connect first.",
            )

        # Search for track
        tracks = await wavelink.Playable.search(track.url)
        playable = None
        if not tracks:
            raise HTTPException(status_code=404, detail="Track not found")
        for t in tracks:
            if t.title == track.track_title:
                playable = t

        # Add to queue
        if playable is None:
            raise HTTPException(status_code=404, detail="Something wrong, retry")

        repo.save_to_queue(
            guild_id,
            playable.title,
            playable.uri,
            playable.identifier,
            playable.author,
            track.requested_by,
        )

        # Play if not playing
        if not vc.playing:
            play_track = repo.pop_next_track(guild_id)
            if play_track:
                await vc.play(playable)
                repo.save_play_history(
                    guild_id,
                    track.requested_by,
                    playable.title,
                    playable.identifier,
                    playable.author,
                    playable.uri,
                )
                return SuccessResponse(
                    success=True, message=f"Now playing: {playable.title}"
                )

        return SuccessResponse(
            success=True, message=f"Added to queue: {playable.title}"
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error playing track: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/{guild_id}/seek", response_model=SuccessResponse)
async def seek_track(guild_id: int, req: SeekRequest):
    """
    Seek to a specific time position (already in seconds).
    """
    try:
        bot = get_bot()
        guild = bot.get_guild(guild_id)

        if not guild:
            raise HTTPException(status_code=404, detail="Guild not found")

        # Check if user is in voice channel
        is_valid, message, _, _ = verify_user_in_voice(
            guild, req.user_id, require_same_channel=True
        )
        if not is_valid:
            raise HTTPException(status_code=403, detail=message)

        vc = guild.voice_client
        if not vc or not vc.current:
            raise HTTPException(status_code=400, detail="Nothing is playing")

        # Track duration and clamp seek value
        duration_sec = vc.current.length // 1000  # yours returns ms → convert once
        seek_sec = max(0, min(req.position, duration_sec))

        await vc.seek(seek_sec * 1000)  # vc.seek() still needs milliseconds

        return SuccessResponse(
            success=True,
            message=f"⏩ Seeked to {seek_sec}s",
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error seeking: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get(
    "/{guild_id}/users-in-channel",
    response_model=dict,
)
async def get_users_in_same_channel(guild_id: int):
    """
    Return list of members in same voice channel as the bot, including avatar URLs
    """
    try:
        bot = get_bot()
        guild = bot.get_guild(guild_id)

        if not guild:
            raise HTTPException(status_code=404, detail="Guild not found")

        vc = guild.voice_client
        if not vc or not vc.channel:
            return {
                "success": False,
                "channel": None,
                "members": [],
                "message": "Bot is not connected to any voice channel",
            }

        channel = vc.channel

        members = []
        for member in channel.members:
            avatar_url = (
                member.display_avatar.url
                if hasattr(member.display_avatar, "url")
                else None
            )

            members.append(
                {
                    "user_id": member.id,
                    "name": member.display_name,
                    "is_bot": member.bot,
                    "status": str(member.status),
                    "avatar": avatar_url,
                }
            )

        return {
            "success": True,
            "channel": channel.name,
            "members": members,
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error retrieving members in bot channel: {e}")
        raise HTTPException(status_code=500, detail=str(e))
