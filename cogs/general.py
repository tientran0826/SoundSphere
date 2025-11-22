import discord
from discord.ext import commands
from loguru import logger


class MusicHelp(commands.Cog):
    """Show help info for music bot commands"""

    def __init__(self, bot):
        self.bot = bot

    @commands.command(name="music_help", aliases=["mh"])
    async def music_help(self, ctx):
        """Show music bot commands and usage"""
        embed = discord.Embed(
            title="🎵 Music Bot Help",
            description="Here’s a list of available music commands and how to use them:",
            color=0x1DB954,
        )

        embed.add_field(
            name="!play <query>",
            value="Plays a song or adds it to the queue if something is already playing.\nExample: `!play Never Gonna Give You Up`",
            inline=False,
        )
        embed.add_field(
            name="!pause",
            value="Pauses the currently playing track.\nExample: `!pause`",
            inline=False,
        )
        embed.add_field(
            name="!resume",
            value="Resumes paused track.\nExample: `!resume`",
            inline=False,
        )
        embed.add_field(
            name="!skip",
            value="Skips the current track and plays the next one in queue.\nExample: `!skip`",
            inline=False,
        )
        embed.add_field(
            name="!stop",
            value="Stops playback and clears the queue.\nExample: `!stop`",
            inline=False,
        )
        embed.add_field(
            name="!disconnect",
            value="Disconnects the bot from the voice channel.\nExample: `!disconnect`",
            inline=False,
        )
        embed.add_field(
            name="!queue",
            value="Shows all tracks in the queue.\nExample: `!queue`",
            inline=False,
        )
        embed.add_field(
            name="!now",
            value="Shows the currently playing track.\nExample: `!now`",
            inline=False,
        )
        embed.add_field(
            name="!shuffle",
            value="Shuffles the current queue.\nExample: `!shuffle`",
            inline=False,
        )

        await ctx.send(embed=embed)


# ----------------------
# Setup function
# ----------------------
async def setup(bot):
    await bot.add_cog(MusicHelp(bot))
    logger.info("MusicHelp cog loaded.")
