import asyncio
import os
from datetime import datetime
from typing import Optional

import discord
import wavelink
from discord import Embed
from discord.ext import commands, tasks
from loguru import logger

from database.music_repository import MusicRepository
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
        self.repo = MusicRepository(database_url)

        self.idle_checker.start()
        self.add_track_mode_users = {}  # {user_id: (album_name, timeout_task)}

    # Only listen to music channel
    async def cog_check(self, ctx):
        config = self.repo.get_server_config(ctx.guild.id)
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
        next_track = self.repo.pop_next_track(player.guild.id)
        channel_id = self.repo.get_server_config(player.guild.id).default_channel_id
        channel = player.guild.get_channel(channel_id)
        if not next_track:
            if channel:
                await channel.send("📭 Queue is empty!")
            return

        playable = (await wavelink.Playable.search(next_track.url))[0]
        await player.play(playable)

        # Save play history
        self.repo.save_play_history(
            player.guild.id,
            next_track.requested_by,
            next_track.track_title,
            next_track.track_author,
            next_track.url,
        )

        await channel.send(
            embed=track_embed(playable, next_track.requested_by, title="▶️ Now Playing")
        )

    # Task
    @tasks.loop(seconds=5)
    async def idle_checker(self):
        for guild in self.bot.guilds:
            vc: wavelink.Player = guild.voice_client

            # Check if bot is connected
            if not vc:
                self.repo.delele_all_tracks_from_queue(guild.id)
                continue

            # Check if voice channel is empty
            if vc.channel:
                non_bot_members = [m for m in vc.channel.members if not m.bot]

                if len(non_bot_members) == 0:
                    logger.info(
                        f"Disconnecting from {guild.name} because bot is alone."
                    )
                    channel_id = self.repo.get_server_config(
                        guild.id
                    ).default_channel_id
                    channel = guild.get_channel(channel_id)
                    await channel.send(
                        "Leaving voice channel because everyone left :face_holding_back_tears: ."
                    )
                    await vc.disconnect()
                    self.repo.delele_all_tracks_from_queue(guild.id)
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
                    channel_id = self.repo.get_server_config(
                        guild.id
                    ).default_channel_id
                    channel = guild.get_channel(channel_id)
                    await channel.send("Disconnecting due to inactivity.")
                    await vc.disconnect()
                    self.repo.delele_all_tracks_from_queue(guild.id)
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
            self.repo.save_to_queue(
                ctx.guild.id, track.title, track.uri, track.author, ctx.author.id
            )
            await ctx.send(
                embed=track_embed(track, ctx.author.id, title="📝 Added to Queue")
            )

        if not vc.playing:
            play_track = self.repo.pop_next_track(ctx.guild.id)
            if play_track:
                tracks = await wavelink.Playable.search(play_track.url)
                track = tracks[0]
                await vc.play(track)
                self.repo.save_play_history(
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

        await ctx.send("Current queue will be cleared. Adding album tracks...")
        self.repo.delele_all_tracks_from_queue(ctx.guild.id)
        album_tracks = self.repo.add_album_to_queue(ctx.guild.id, album_name)
        if not album_tracks:
            return await ctx.send(
                f"❌ Album '{album_name}' not found or has no tracks."
            )

        # Add tracks to queue (save_to_queue opens/closes its own session)
        for t in album_tracks:
            self.repo.save_to_queue(
                ctx.guild.id,
                t["track_title"],
                t["url"],
                t["track_author"],
                ctx.author.id,
            )

        await ctx.send(f"✅ All tracks from album '{album_name}' added to the queue.")

        if not vc.playing:
            play_track = self.repo.pop_next_track(ctx.guild.id)
            if play_track:
                tracks = await wavelink.Playable.search(play_track.url)
                track = tracks[0]
                await vc.play(track)
                self.repo.save_play_history(
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
        next_track = self.repo.pop_next_track(ctx.guild.id)
        if next_track:
            tracks = await wavelink.Playable.search(next_track.url)
            track = tracks[0]
            await vc.play(track)
            self.repo.save_play_history(
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
        queue_track = self.repo.remove_from_queue(ctx.guild.id, track_position)
        if queue_track:
            await ctx.send(f"Removed track ID {track_position} from the queue.")
        else:
            await ctx.send(f"Track ID {track_position} not found in the queue.")

    @commands.command()
    async def clear(self, ctx):
        cleared = self.repo.clear_queue(ctx.guild.id)
        if cleared:
            await ctx.send("Cleared the entire queue.")
        else:
            await ctx.send("Failed to clear the queue.")

    @commands.command()
    async def queue(self, ctx):
        queue_tracks = self.repo.get_all_tracks_from_queue(ctx.guild.id)
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
        self.repo.create_album(
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
        self.repo.remove_album(ctx.guild.id, album_name)
        await ctx.send(f"🗑️ Album '{album_name}' and its tracks have been removed.")

    @commands.command()
    async def albums(self, ctx):
        """List all albums for the server."""
        albums = self.repo.get_all_albums(ctx.guild.id)
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
        tracks = self.repo.get_album_tracks(ctx.guild.id, album_name)
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
        # Use repository to get album
        album = self.repo.get_album_by_name(ctx.guild.id, album_name)

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
                "❌ You are not in add-track mode. Use `!start_add <album>` first."
            )

        # Reset timeout
        self.add_track_mode_users[user_id]["timeout_task"].cancel()
        timeout_task = self.bot.loop.create_task(
            self._remove_add_mode_after(user_id, 30)
        )
        self.add_track_mode_users[user_id]["timeout_task"] = timeout_task

        album_id = self.add_track_mode_users[user_id]["album_id"]

        # Get album using repository
        album = self.repo.get_album_by_id(album_id)
        if not album:
            return await ctx.send("❌ The album no longer exists.")

        # Get next track number
        max_track_number = self.repo.get_max_track_number(album.id)
        next_track_number = max_track_number + 1

        # Search track
        search_tracks = await wavelink.Playable.search(track_title)
        choose_track = search_tracks[0] if search_tracks else None
        if not choose_track:
            return await ctx.send(f"❌ No track found for '{track_title}'.")

        # Add track using repository
        added_track = self.repo.add_track_to_album_with_number(
            album_id=album.id,
            track_title=choose_track.title,
            url=choose_track.uri,
            track_author=choose_track.author,
            requested_by=ctx.author.id,
            track_number=next_track_number,
        )

        if not added_track:
            return await ctx.send("❌ Failed to add track to album.")

        await ctx.send(
            f"✅ Track '{choose_track.title}' added to album '{album.album_name}'."
        )

        # Show updated tracks
        tracks = self.repo.get_album_tracks(ctx.guild.id, album.album_name)
        track_list = []
        for track in tracks:
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

    @commands.command()
    async def remove_from_album(self, ctx, *, args: str):
        """Remove a track from a specific album by track number."""
        parts = args.rsplit(" ", 1)  # Split from the right, max 1 split
        if len(parts) != 2 or not parts[1].isdigit():
            return await ctx.send(
                "❌ Usage: !remove_from_album <album_name> <track_number>"
            )

        album_name, track_number = parts[0], int(parts[1])

        # Use repository to remove track
        success, track_title = self.repo.remove_track_from_album_by_number(
            ctx.guild.id, album_name, track_number
        )

        if not success:
            if track_title is None:
                return await ctx.send(
                    f"❌ Album '{album_name}' or track #{track_number} not found."
                )
            return await ctx.send(f"❌ Failed to remove track from album.")

        await ctx.send(f"✅ Track '{track_title}' removed from album '{album_name}'.")

    @commands.command()
    async def now(self, ctx):
        vc: wavelink.Player = ctx.voice_client
        if not vc or not vc.current:
            return await ctx.send("Nothing is playing!")
        track = vc.current
        await ctx.send(f"🎵 **Now Playing:**\n{track.title} by {track.author}")

    @commands.command()
    async def shuffle(self, ctx):
        self.repo.shuffle_queue(ctx.guild.id)
        await ctx.send("🔀 Queue shuffled!")


# ----------------------
# Setup function
# ----------------------
async def setup(bot):
    await bot.add_cog(Music(bot))
