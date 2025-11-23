import os

from fastapi import HTTPException
from loguru import logger

from database.music_repository import MusicRepository

DATABASE_URL = os.getenv("DATABASE_URL")
repo = MusicRepository(DATABASE_URL)

_bot_instance = None


def get_repo() -> MusicRepository:
    """Get repository instance"""
    return repo


def set_bot_instance(bot):
    """Set the bot instance for API to use"""
    global _bot_instance
    _bot_instance = bot
    logger.info("Bot instance set for API")


def get_bot():
    """Get the bot instance"""
    if _bot_instance is None:
        raise HTTPException(status_code=503, detail="Bot not ready")
    return _bot_instance


def verify_user_in_voice(guild, user_id: int, require_same_channel: bool = True):
    """
    Verify if user is in voice channel.
    Returns (is_valid: bool, message: str, user_voice_channel, bot_voice_channel)
    """
    # Get user
    member = guild.get_member(user_id)
    if not member:
        return False, "User not found in guild", None, None

    # Check if user is in voice
    if not member.voice or not member.voice.channel:
        return False, "You must be in a voice channel to control the bot", None, None

    user_channel = member.voice.channel
    bot_channel = guild.voice_client.channel if guild.voice_client else None

    if not bot_channel:
        return (
            False,
            "Bot is not connected to any voice channel. Use Discord to connect the bot first.",
            user_channel,
            None,
        )

    # If bot is connected, verify same channel
    if require_same_channel and bot_channel:
        if user_channel.id != bot_channel.id:
            return (
                False,
                f"You must be in the same voice channel as the bot ({bot_channel.name})",
                user_channel,
                bot_channel,
            )

    return True, "User authorized", user_channel, bot_channel
