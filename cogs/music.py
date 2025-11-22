import asyncio
import os
from datetime import datetime
from typing import Optional

import discord
import wavelink
from discord import Embed
from discord.ext import commands, tasks
from loguru import logger
from sqlalchemy import create_engine, func
from sqlalchemy.orm import selectinload, sessionmaker

from database.models import Album, AlbumTrack, PlayHistory, QueueTracks, ServerSettings
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
        self.add_track_mode_users = {}  # {user_id: (album_name, timeout_task)}

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

    def remove_track_from_ablumn(self, album_id: int, track_id: int):
        """Remove track from album in DB"""
        session = self.Session()
        try:
            session.query(AlbumTrack).filter_by(album_id=album_id, id=track_id).delete()
            session.commit()
        except Exception as e:
            logger.info(f"Error removing track from album: {e}")
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

    def _create_ablumn(
        self,
        guild_id: int,
        album_name: str,
        requested_by: int,
    ):
        """Add album track to DB"""
        session = self.Session()
        try:
            album = Album(
                guild_id=guild_id,
                album_name=album_name,
                created_by=requested_by,
            )
            session.add(album)
            session.commit()
        except Exception as e:
            logger.info(f"Error saving album track: {e}")
            session.rollback()
        finally:
            session.close()

    def _remove_album(self, guild_id: int, album_name: str):
        """Remove album and its tracks from DB"""
        session = self.Session()
        try:
            album = (
                session.query(Album)
                .filter_by(guild_id=guild_id, album_name=album_name)
                .first()
            )
            if album:
                session.delete(album)
                session.commit()
        except Exception as e:
            logger.info(f"Error removing album: {e}")
            session.rollback()
        finally:
            session.close()

    def get_all_albums(self, guild_id: int):
        """Fetch all albums with their tracks for a specific guild."""
        session = self.Session()
        try:
            albums = (
                session.query(Album)
                .options(selectinload(Album.tracks))  # eagerly load tracks
                .filter_by(guild_id=guild_id)
                .all()
            )
            return albums  # list of Album objects with tracks loaded
        except Exception as e:
            logger.info(f"Error fetching albums: {e}")
            return []
        finally:
            session.close()

    def get_album_tracks(self, guild_id: int, album_name: str):
        """Fetch all tracks of a specific album for a guild."""
        session = self.Session()
        try:
            album = (
                session.query(Album)
                .filter_by(guild_id=guild_id, album_name=album_name)
                .first()
            )
            if not album:
                return []  # Album not found
            return album.tracks  # list of AlbumTrack objects
        except Exception as e:
            logger.info(f"Error fetching album tracks: {e}")
            return []
        finally:
            session.close()

    def clear_queue(self, guild_id: int):
        session = self.Session()
        try:
            session.query(QueueTracks).filter_by(guild_id=guild_id).delete()
            session.commit()
            return True
        except Exception as e:
            logger.info(f"Error removing from queue: {e}")
            session.rollback()
            return False

    def remove_from_queue(self, guild_id: int, track_position: int):
        session = self.Session()
        try:
            session.query(QueueTracks).filter_by(
                guild_id=guild_id, position=track_position
            ).delete()
            session.commit()
            return True
        except Exception as e:
            logger.info(f"Error removing from queue: {e}")
            session.rollback()
            return False

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
        """Pop the first track in queue, remove it from DB, and recalc positions."""
        session = self.Session()
        try:
            # Get the first track
            track = (
                session.query(QueueTracks)
                .filter_by(guild_id=guild_id)
                .order_by(QueueTracks.position.asc())
                .first()
            )
            if not track:
                return None

            # Remove it
            session.delete(track)
            session.commit()  # commit deletion first

            # Recalculate positions for remaining tracks
            remaining_tracks = (
                session.query(QueueTracks)
                .filter_by(guild_id=guild_id)
                .order_by(QueueTracks.position.asc())
                .all()
            )

            for i, t in enumerate(remaining_tracks, start=1):
                t.position = i
            session.commit()

            return track
        except Exception as e:
            logger.info(f"Error popping next track: {e}")
            session.rollback()
            return None
        finally:
            session.close()

    # Task
    @tasks.loop(seconds=5)
    async def idle_checker(self):
        for guild in self.bot.guilds:
            vc: wavelink.Player = guild.voice_client

            # Check if bot is connected
            if not vc:
                self.delele_all_tracks_from_queue(guild.id)
                continue

            # Check if voice channel is empty
            if vc.channel:
                non_bot_members = [m for m in vc.channel.members if not m.bot]

                if len(non_bot_members) == 0:
                    logger.info(
                        f"Disconnecting from {guild.name} because bot is alone."
                    )
                    channel_id = self.get_server_config(guild.id).default_channel_id
                    channel = guild.get_channel(channel_id)
                    await channel.send(
                        "Leaving voice channel because everyone left :face_holding_back_tears: ."
                    )
                    await vc.disconnect()
                    self.delele_all_tracks_from_queue(guild.id)
                    if hasattr(vc, "idle_start"):
                        delattr(vc, "idle_start")
                    continue

            # Check for idle timeout
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
    async def play_album(self, ctx, *, album_name: str):
        """Play all tracks from an album by adding them to the queue."""
        if not ctx.author.voice:
            return await ctx.send("You need to be in a voice channel!")

        if not wavelink.Pool.nodes:
            return await ctx.send("Lavalink node is not connected!")

        vc: wavelink.Player = ctx.voice_client
        if not vc:
            try:
                vc = await ctx.author.voice.channel.connect(cls=wavelink.Player)
            except wavelink.ChannelTimeoutException:
                return await ctx.send(
                    f"❌ Unable to connect to `{ctx.author.voice.channel.name}` (timed out)."
                )
            except Exception as e:
                logger.exception("Error connecting to voice channel")
                return await ctx.send("❌ Failed to connect to the voice channel.")

        session = self.Session()
        try:
            album = (
                session.query(Album)
                .options(selectinload(Album.tracks))  # eager load tracks
                .filter_by(guild_id=ctx.guild.id, album_name=album_name)
                .first()
            )
            if not album:
                return await ctx.send(f"❌ Album '{album_name}' does not exist.")
            # Extract plain Python list of tracks (avoid using ORM objects after session close)
            album_tracks = [
                {
                    "track_title": t.track_title,
                    "url": t.url,
                    "track_author": t.track_author,
                }
                for t in sorted(
                    album.tracks, key=lambda x: getattr(x, "track_number", x.id)
                )
            ]
        finally:
            session.close()

        await ctx.send("Current queue will be cleared. Adding album tracks...")
        self.delele_all_tracks_from_queue(ctx.guild.id)

        # Add tracks to queue (save_to_queue opens/closes its own session)
        for t in album_tracks:
            self.save_to_queue(
                ctx.guild.id,
                t["track_title"],
                t["url"],
                t["track_author"],
                ctx.author.id,
            )

        await ctx.send(f"✅ All tracks from album '{album_name}' added to the queue.")

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
    async def remove(self, ctx, track_position: int):
        """Remove a specific track from the queue by its ID."""
        queue_track = self.remove_from_queue(ctx.guild.id, track_position)
        if queue_track:
            await ctx.send(f"Removed track ID {track_position} from the queue.")
        else:
            await ctx.send(f"Track ID {track_position} not found in the queue.")

    @commands.command()
    async def clear(self, ctx):
        cleared = self.clear_queue(ctx.guild.id)
        if cleared:
            await ctx.send("Cleared the entire queue.")
        else:
            await ctx.send("Failed to clear the queue.")

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
                f"**{track_db.position}.** [{title}]({track_db.url}) (by <@{track_db.requested_by}>)"
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
    async def create_album(self, ctx, *, album_name: str):
        """Create an album by adding tracks to the database."""
        self._create_ablumn(
            guild_id=ctx.guild.id,
            album_name=album_name,
            requested_by=ctx.author.id,
        )
        await ctx.send(
            f"📀 Album '{album_name}' created successfully! Please add tracks."
        )

    @commands.command()
    async def remove_album(self, ctx, *, album_name: str):
        """Remove an album and its tracks from the database."""
        self._remove_album(ctx.guild.id, album_name)
        await ctx.send(f"🗑️ Album '{album_name}' and its tracks have been removed.")

    @commands.command()
    async def albums(self, ctx):
        """List all albums for the server."""
        albums = self.get_all_albums(ctx.guild.id)
        if not albums:
            return await ctx.send("📭 No albums found for this server.")

        album_list = []
        for i, album in enumerate(albums, 1):
            album_list.append(
                f"**{i}.** {album.album_name} (Tracks: {len(album.tracks)})"
            )

        album_str = "\n".join(album_list)

        embed = Embed(
            title=f"📀 Albums ({len(albums)} Total)",
            description=album_str,
            color=0x9B59B6,  # A nice purple color
        )
        await ctx.send(embed=embed)

    @commands.command()
    async def show_album(self, ctx, *, album_name: str):
        """List all tracks in a specific album."""
        tracks = self.get_album_tracks(ctx.guild.id, album_name)
        if not tracks:
            return await ctx.send(f"📭 No tracks found for album '{album_name}'.")

        track_list = []
        for i, track in enumerate(tracks, 1):
            # Truncate title if too long
            title = (
                (track.track_title[:50] + "...")
                if len(track.track_title) > 50
                else track.track_title
            )
            track_list.append(
                f"**{track.track_number}.** [{title}]({track.url}) - {track.track_author} (by <@{track.requested_by}>)"
            )

        track_str = "\n".join(track_list)

        embed = Embed(
            title=f"🎵 Tracks in Album: {album_name} ({len(tracks)} Tracks)",
            description=track_str,
            color=0x2ECC71,
        )
        await ctx.send(embed=embed)

    async def _remove_add_mode_after(self, user_id: int, timeout: int):
        try:
            await asyncio.sleep(timeout)
            user_data = self.add_track_mode_users.pop(user_id, None)
            if not user_data:
                return

            channel = self.bot.get_channel(user_data["channel_id"])
            if channel:
                await channel.send(
                    f"⏰ <@{user_id}>, your **add-track mode** has expired due to inactivity."
                )
        except asyncio.CancelledError:
            # Timer was reset
            pass

    @commands.command()
    async def start_add(self, ctx, *, album_name: str):
        """Start add-track mode for a specific album."""
        session = self.Session()
        try:
            album = (
                session.query(Album)
                .filter_by(guild_id=ctx.guild.id, album_name=album_name)
                .first()
            )
            if not album:
                return await ctx.send(f"❌ Album '{album_name}' does not exist.")

            user_id = ctx.author.id

            # Cancel previous timeout if exists
            if user_id in self.add_track_mode_users:
                self.add_track_mode_users[user_id]["timeout_task"].cancel()

            timeout_task = self.bot.loop.create_task(
                self._remove_add_mode_after(user_id, 30)
            )
            self.add_track_mode_users[user_id] = {
                "album_id": album.id,
                "timeout_task": timeout_task,
                "channel_id": ctx.channel.id,
            }

            await ctx.send(
                f"✅ You are now in **add-track mode** for album '{album_name}'. "
                f"All tracks you add will go into this album until you end the mode or 30s pass without activity."
            )
        finally:
            session.close()

    @commands.command()
    async def end(self, ctx):
        """End add-track mode manually."""
        user_id = ctx.author.id
        if user_id in self.add_track_mode_users:
            self.add_track_mode_users[user_id]["timeout_task"].cancel()
            self.add_track_mode_users.pop(user_id)
            await ctx.send("✅ Add-track mode ended.")
        else:
            await ctx.send("❌ You are not in add-track mode.")

    @commands.command()
    async def add(self, ctx, *, track_title: str):
        """Add a track to the album currently in add-track mode."""
        user_id = ctx.author.id

        if user_id not in self.add_track_mode_users:
            return await ctx.send(
                "❌ You are not in add-track mode. Use `!start_add_album_tracks <album>` first."
            )

        # Reset timeout
        self.add_track_mode_users[user_id]["timeout_task"].cancel()
        timeout_task = self.bot.loop.create_task(
            self._remove_add_mode_after(user_id, 30)
        )
        self.add_track_mode_users[user_id]["timeout_task"] = timeout_task

        album_id = self.add_track_mode_users[user_id]["album_id"]

        session = self.Session()
        try:
            album = session.query(Album).filter_by(id=album_id).first()
            if not album:
                return await ctx.send("❌ The album no longer exists.")
            max_track_number = (
                session.query(func.max(AlbumTrack.track_number))
                .filter_by(album_id=album.id)
                .scalar()
            )
            next_track_number = (
                max_track_number if max_track_number is not None else 0
            ) + 1
            # Search track
            search_tracks = await wavelink.Playable.search(track_title)
            choose_track = search_tracks[0] if search_tracks else None
            if not choose_track:
                return await ctx.send(f"❌ No track found for '{track_title}'.")

            album_track = AlbumTrack(
                album_id=album.id,
                track_title=choose_track.title,
                track_number=next_track_number,
                url=choose_track.uri,
                track_author=choose_track.author,
                requested_by=ctx.author.id,
            )
            session.add(album_track)
            session.commit()
            await ctx.send(
                f"✅ Track '{choose_track.title}' added to album '{album.album_name}'."
            )

            # Show update tracks
            tracks = self.get_album_tracks(ctx.guild.id, album.album_name)
            track_list = []
            for i, track in enumerate(tracks, 1):
                # Truncate title if too long
                title = (
                    (track.track_title[:50] + "...")
                    if len(track.track_title) > 50
                    else track.track_title
                )
                track_list.append(
                    f"**{track.track_number}.** [{title}]({track.url}) - {track.track_author} (by <@{track.requested_by}>)"
                )
            track_str = "\n".join(track_list)
            embed = Embed(
                title=f"🎵 Updated Tracks in Album: {album.album_name} ({len(tracks)} Tracks)",
                description=track_str,
                color=0x2ECC71,
            )
            await ctx.send(embed=embed)
        finally:
            session.close()

    @commands.command()
    async def remove_from_album(self, ctx, *, args: str):
        """Remove a track from a specific album by track number."""
        parts = args.rsplit(" ", 1)  # Split from the right, max 1 split
        if len(parts) != 2 or not parts[1].isdigit():
            return await ctx.send(
                "❌ Usage: !remove_from_album <album_name> <track_number>"
            )

        album_name, track_number = parts[0], int(parts[1])

        session = self.Session()
        try:
            # Find album first
            album = (
                session.query(Album)
                .filter_by(album_name=album_name, guild_id=ctx.guild.id)
                .first()
            )
            if not album:
                return await ctx.send(f"❌ Album with ID {album_name} does not exist.")

            # Find track within that album
            track = (
                session.query(AlbumTrack)
                .filter_by(track_number=track_number, album_id=album.id)
                .first()
            )
            if not track:
                return await ctx.send(
                    f"❌ Track ID {track_number} not found in this album."
                )

            session.delete(track)
            session.commit()
            await ctx.send(
                f"✅ Track '{track.track_title}' removed from album '{album.album_name}'."
            )
        finally:
            session.close()

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
