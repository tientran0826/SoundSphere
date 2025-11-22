import os
from datetime import datetime
from typing import Optional

import discord
import wavelink
from discord import Embed
from discord.ext import commands, tasks
from loguru import logger
from sqlalchemy import create_engine, func
from sqlalchemy.orm import sessionmaker

from database.models import PlayHistory, QueueTracks, ServerSettings
from settings import configs


def track_embed(
    track: wavelink.Playable,
    requested_by: int,
    title: str = "▶️ Now Playing",
    description: Optional[str] = None,
    color: int = 0x1DB954,
) -> Embed:
    """
    Create a flexible Discord embed for a Wavelink track.

    Args:
        track (wavelink.Playable): The track object.
        requested_by (int): Discord user ID who requested the track.
        title (str): Embed title (default: "Now Playing").
        description (Optional[str]): Optional custom description; defaults to track title & author.
        color (int): Embed color.

    Returns:
        discord.Embed: The embed ready to send.
    """
    # Default description
    if description is None:
        description = f"**{track.title}** - {track.author}"

    # Format duration in mm:ss
    minutes, seconds = divmod(track.length // 1000, 60)
    duration_str = f"{minutes}:{seconds:02}"

    embed = Embed(title=title, description=description, color=color)

    embed.add_field(name="Requested by", value=f"<@{requested_by}>", inline=True)
    embed.add_field(name="Duration", value=duration_str, inline=True)

    if hasattr(track, "artwork") and track.artwork:
        embed.set_thumbnail(url=track.artwork)

    if hasattr(track, "uri") and track.uri:
        embed.add_field(name="Link", value=f"[Click here]({track.uri})", inline=False)

    return embed


class Music(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        # Setup database connection
        database_url = os.getenv("DATABASE_URL")
        self.engine = create_engine(database_url)
        self.Session = sessionmaker(bind=self.engine)
        self.idle_checker.start()

    # Only listen to music channel
    async def cog_check(self, ctx):
        config = self.get_server_config(ctx.guild.id)
        channel = None

        if config.default_channel_id:
            channel = self.bot.get_channel(config.default_channel_id)

        if not channel and configs.DEFAULT_CHANNEL:
            channel = discord.utils.get(
                ctx.guild.text_channels, name=configs.DEFAULT_CHANNEL
            )
        if channel:
            if ctx.channel.id != channel.id:
                await ctx.send(
                    f"Please use {channel.mention} channel for music commands."
                )
                return False

        return True

    def get_server_config(self, guild_id: int):
        """Get server configuration from database"""
        session = self.Session()
        try:
            config = session.query(ServerSettings).filter_by(guild_id=guild_id).first()
            if not config:
                # Create default config for new server
                config = ServerSettings(
                    guild_id=guild_id, command_prefix="!", default_channel_id=None
                )
                session.add(config)
                session.commit()
                session.refresh(config)
            return config
        finally:
            session.close()

    @commands.Cog.listener()
    async def on_wavelink_node_ready(self, payload: wavelink.NodeReadyEventPayload):
        logger.info(f"Lavalink node {payload.node.identifier} is connected and ready!")

    @commands.Cog.listener()
    async def on_wavelink_track_end(self, payload: wavelink.TrackEndEventPayload):
        # Fetch next track from DB
        player = payload.player
        reason = payload.reason
        if reason.upper() == "STOPPED" or reason.upper() == "REPLACED":
            return
        next_track = self.pop_next_track(player.guild.id)
        channel_id = self.get_server_config(player.guild.id).default_channel_id
        channel = player.guild.get_channel(channel_id)
        if not next_track:
            if channel:
                await channel.send("📭 Queue is empty!")
            return

        playable = (await wavelink.Playable.search(next_track.url))[0]
        await player.play(playable)

        # Save play history
        self.save_play_history(
            player.guild.id,
            next_track.requested_by,
            next_track.track_title,
            next_track.track_author,
            next_track.url,
        )

        await channel.send(
            embed=track_embed(playable, next_track.requested_by, title="▶️ Now Playing")
        )

    def save_play_history(
        self, guild_id: int, user_id: int, track_title: str, track_author: str, url: str
    ):
        """Save play history to database"""
        session = self.Session()
        try:
            history = PlayHistory(
                guild_id=guild_id,
                user_id=user_id,
                track_title=track_title,
                track_author=track_author,
                url=url,
            )
            session.add(history)
            session.commit()
        except Exception as e:
            logger.info(f"Error saving play history: {e}")
            session.rollback()
        finally:
            session.close()

    def get_all_tracks_from_queue(self, guild_id: int):
        """Fetch all tracks in the queue for a guild, ordered by position."""
        session = self.Session()
        try:
            tracks = (
                session.query(QueueTracks)
                .filter_by(guild_id=guild_id)
                .order_by(QueueTracks.position.asc())
                .all()
            )
            return tracks
        except Exception as e:
            logger.info(f"Error fetching queue tracks: {e}")
            return []
        finally:
            session.close()

    def delele_all_tracks_from_queue(self, guild_id: int):
        """Clear the queue for a guild."""
        session = self.Session()
        try:
            session.query(QueueTracks).filter_by(guild_id=guild_id).delete()
            session.commit()
        except Exception as e:
            logger.info(f"Error clearing queue: {e}")
            session.rollback()
        finally:
            session.close()

    def save_to_queue(
        self,
        guild_id: int,
        track_title: str,
        url: str,
        track_author: str,
        requested_by: int,
    ):
        """Add track to DB queue"""
        session = self.Session()
        try:
            # Determine next position using func.max for robustness
            max_pos = (
                session.query(func.max(QueueTracks.position))
                .filter_by(guild_id=guild_id)
                .scalar()
            )

            # Use max_pos or 0 if the queue is empty, then add 1
            next_pos = (max_pos if max_pos is not None else 0) + 1

            queue_track = QueueTracks(
                guild_id=guild_id,
                track_title=track_title,
                url=url,
                requested_by=requested_by,
                track_author=track_author,
                position=next_pos,
            )
            session.add(queue_track)
            session.commit()
        except Exception as e:
            logger.info(f"Error saving to queue: {e}")
            session.rollback()
        finally:
            session.close()

    def remove_from_queue(self, guild_id: int, url: str):
        """Remove track from database queue when played"""
        session = self.Session()
        try:
            session.query(QueueTracks).filter_by(guild_id=guild_id, url=url).delete()
            session.commit()
        except Exception as e:
            logger.info(f"Error removing from queue: {e}")
            session.rollback()
        finally:
            session.close()

    def get_next_track(self, guild_id: int):
        """Fetch the first track in queue (FIFO)"""
        session = self.Session()
        try:
            track = (
                session.query(QueueTracks)
                .filter_by(guild_id=guild_id)
                .order_by(QueueTracks.position.asc())
                .first()
            )
            return track
        finally:
            session.close()

    def shuffle_queue(self, guild_id: int):
        """Shuffle the queue for a guild"""
        session = self.Session()
        try:
            tracks = session.query(QueueTracks).filter_by(guild_id=guild_id).all()
            import random

            random.shuffle(tracks)
            for index, track in enumerate(tracks, start=1):
                track.position = index
            session.commit()
        except Exception as e:
            logger.info(f"Error shuffling queue: {e}")
            session.rollback()
        finally:
            session.close()

    def pop_next_track(self, guild_id: int):
        """Pop the first track in queue and remove it from DB"""
        session = self.Session()
        try:
            track = (
                session.query(QueueTracks)
                .filter_by(guild_id=guild_id)
                .order_by(QueueTracks.position.asc())
                .first()
            )
            if track:
                session.delete(track)
                session.commit()
            return track
        except Exception as e:
            logger.info(f"Error popping next track: {e}")
            session.rollback()
        finally:
            session.close()

    # Task
    @tasks.loop(seconds=5)
    async def idle_checker(self):
        for guild in self.bot.guilds:
            vc: wavelink.Player = guild.voice_client
            if not vc:
                continue
            if not vc.playing or vc.paused:
                if not hasattr(vc, "idle_start"):
                    vc.idle_start = datetime.now()
                idle_time = (datetime.now() - vc.idle_start).total_seconds()
                time_out_ratio = 3 if vc.paused else 1  # Longer timeout if paused
                if idle_time >= configs.IDLE_TIMEOUT * time_out_ratio:
                    logger.info(
                        f"Disconnecting from {guild.name} after {configs.IDLE_TIMEOUT} seconds of idling."
                    )
                    channel_id = self.get_server_config(guild.id).default_channel_id
                    channel = guild.get_channel(channel_id)
                    await channel.send("Disconnecting due to inactivity.")
                    await vc.disconnect()
                    self.delele_all_tracks_from_queue(guild.id)
                    if hasattr(vc, "idle_start"):
                        delattr(vc, "idle_start")
            else:
                if hasattr(vc, "idle_start"):
                    logger.debug(
                        f"Resetting idle timer for {guild.name} as player is now active."
                    )
                    delattr(vc, "idle_start")

    # ----------------------
    # Music Commands
    # ----------------------
    @commands.command()
    async def play(self, ctx, *, query: str = None):
        """Play a song. If query provided, add to queue."""
        if not ctx.author.voice:
            return await ctx.send("You need to be in a voice channel!")

        if not wavelink.Pool.nodes:
            return await ctx.send("Lavalink node is not connected!")

        vc: wavelink.Player = ctx.voice_client
        if not vc:
            vc = await ctx.author.voice.channel.connect(cls=wavelink.Player)

        if query:
            tracks = await wavelink.Playable.search(query)
            if not tracks:
                return await ctx.send("No tracks found!")
            track = tracks[0]
            self.save_to_queue(
                ctx.guild.id, track.title, track.uri, track.author, ctx.author.id
            )
            await ctx.send(
                embed=track_embed(track, ctx.author.id, title="📝 Added to Queue")
            )

        if not vc.playing:
            play_track = self.pop_next_track(ctx.guild.id)
            if play_track:
                tracks = await wavelink.Playable.search(play_track.url)
                track = tracks[0]
                await vc.play(track)
                self.save_play_history(
                    ctx.guild.id, ctx.author.id, track.title, track.author, track.uri
                )
                await ctx.send(
                    embed=track_embed(
                        track, play_track.requested_by, title="▶️ Now Playing"
                    )
                )
            else:
                await ctx.send("📭 Queue is empty!")

    @commands.command()
    async def pause(self, ctx):
        vc: wavelink.Player = ctx.voice_client
        if not vc:
            return await ctx.send("Not connected to a voice channel!")
        await vc.pause(True)
        await ctx.send("⏸️ Paused")

    @commands.command()
    async def resume(self, ctx):
        vc: wavelink.Player = ctx.voice_client
        if not vc:
            return await ctx.send("Not connected to a voice channel!")
        await vc.pause(False)
        await ctx.send("▶️ Resumed")

    @commands.command()
    async def skip(self, ctx):
        vc: wavelink.Player = ctx.voice_client
        if not vc or not vc.playing:
            return await ctx.send("❌ Nothing is playing to skip!")

        skipped = await vc.stop()
        await ctx.send(f"⏭️ Skipped: **{skipped.title}**")

        # Play next track from DB
        next_track = self.pop_next_track(ctx.guild.id)
        if next_track:
            tracks = await wavelink.Playable.search(next_track.url)
            track = tracks[0]
            await vc.play(track)
            self.save_play_history(
                ctx.guild.id,
                next_track.requested_by,
                track.title,
                track.author,
                track.uri,
            )
            await ctx.send(
                embed=track_embed(track, next_track.requested_by, title="▶️ Now Playing")
            )
        else:
            await ctx.send("📭 Queue is empty!")

    @commands.command()
    async def stop(self, ctx):
        vc: wavelink.Player = ctx.voice_client
        if not vc:
            return await ctx.send("Not connected to a voice channel!")
        vc.queue.clear()
        await vc.stop()
        await ctx.send("⏹️ Stopped")

    @commands.command()
    async def disconnect(self, ctx):
        vc: wavelink.Player = ctx.voice_client
        if not vc:
            return await ctx.send("Not connected to a voice channel!")
        await vc.disconnect()
        await ctx.send("Disconnected")

    @commands.command()
    async def queue(self, ctx):
        queue_tracks = self.get_all_tracks_from_queue(ctx.guild.id)
        if not queue_tracks:
            return await ctx.send("📭 **The queue is currently empty!**")

        queue_list = []
        for i, track_db in enumerate(queue_tracks, 1):
            # Truncate title if too long
            title = (
                (track_db.track_title[:50] + "...")
                if len(track_db.track_title) > 50
                else track_db.track_title
            )
            queue_list.append(
                f"**{i}.** [{title}]({track_db.url}) (by <@{track_db.requested_by}>)"
            )

        queue_str = "\n".join(queue_list)

        embed = Embed(
            title=f"📜 Music Queue ({len(queue_tracks)} Tracks)",
            description=queue_str,
            color=0x3498DB,  # A nice blue color
        )
        embed.set_footer(text=f"Total tracks in queue: {len(queue_tracks)}")
        await ctx.send(embed=embed)

    @commands.command()
    async def now(self, ctx):
        vc: wavelink.Player = ctx.voice_client
        if not vc or not vc.current:
            return await ctx.send("Nothing is playing!")
        track = vc.current
        await ctx.send(f"🎵 **Now Playing:**\n{track.title} by {track.author}")

    @commands.command()
    async def shuffle(self, ctx):
        self.shuffle_queue(ctx.guild.id)
        await ctx.send("🔀 Queue shuffled!")


# ----------------------
# Setup function
# ----------------------
async def setup(bot):
    await bot.add_cog(Music(bot))
