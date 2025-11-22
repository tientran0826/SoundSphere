import discord
from discord.ext import commands
from loguru import logger


class MusicHelp(commands.Cog):
    """Show help info for music bot commands"""

    def __init__(self, bot):
        self.bot = bot

    @commands.command(name="help_music", aliases=["music", "h"])
    async def help_command(self, ctx):
        """Shows help for all music and album commands."""

        # Create an embed for the help message
        embed = discord.Embed(
            title="🎶 Discord Music Bot Commands",
            description="Use these commands to control the music and manage your saved albums.",
            color=0x42F5AA,  # A light green color
        )

        # Define the command groups and descriptions
        command_groups = {
            "Playback & Control": [
                (
                    "play [query/url]",
                    "Play a track immediately, or add a search query/URL to the queue.",
                ),
                ("pause", "Pause the currently playing track."),
                ("resume", "Resume the paused track."),
                ("skip", "Skip the current track and play the next one in the queue."),
                (
                    "stop",
                    "Stop the current track and clear the player's internal queue (but **not** the DB queue).",
                ),
                ("disconnect", "Disconnect the bot from the voice channel."),
            ],
            "Queue Management": [
                ("queue", "View all tracks currently waiting in the queue."),
                (
                    "remove <position>",
                    "Remove a specific track from the queue by its position number.",
                ),
                ("clear", "Clear the entire music queue."),
            ],
            "Album Management": [
                ("create_album <name>", "Create a new album with the given name."),
                ("remove_album <name>", "Delete an album and all its tracks."),
                ("albums", "List all saved albums for this server."),
                ("show_album <name>", "List all tracks stored in a specific album."),
                (
                    "play_album <name>",
                    "Clear the queue and play all tracks from the specified album.",
                ),
                (
                    "start_add <album_name>",
                    "Enter **add-track mode** for an album (tracks added via `!add` will be saved).",
                ),
                (
                    "add <track_title>",
                    "In add-track mode, search for a track and save it to the current album.",
                ),
                ("end", "Manually exit add-track mode."),
                (
                    "remove_from_album <album_name> <track_number>",
                    "Remove a track from a specific album by its track number.",
                ),
            ],
        }

        # Add fields to the embed based on the groups
        for title, commands_list in command_groups.items():
            field_value = "\n".join(
                [f"**!{cmd}** - {desc}" for cmd, desc in commands_list]
            )
            embed.add_field(name=f"--- {title} ---", value=field_value, inline=False)

        # Set the footer
        embed.set_footer(
            text=f"Requested by {ctx.author.display_name}",
            icon_url=(
                ctx.author.avatar.url
                if ctx.author.avatar
                else ctx.author.default_avatar.url
            ),
        )

        await ctx.send(embed=embed)


# ----------------------
# Setup function
# ----------------------
async def setup(bot):
    await bot.add_cog(MusicHelp(bot))
    logger.info("MusicHelp cog loaded.")
