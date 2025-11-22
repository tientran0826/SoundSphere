import os

import discord
from discord.ext import commands
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from database.models import ServerSettings


class ServerSettingsCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        database_url = os.getenv("DATABASE_URL")
        self.engine = create_engine(database_url)
        self.Session = sessionmaker(bind=self.engine)

    @commands.command(name="set_prefix")
    async def set_prefix(self, ctx, prefix: str):
        """Set a custom command prefix for this server."""
        session = self.Session()
        try:
            settings = (
                session.query(ServerSettings).filter_by(guild_id=ctx.guild.id).first()
            )
            if not settings:
                settings = ServerSettings(guild_id=ctx.guild.id, command_prefix=prefix)
                session.add(settings)
            else:
                settings.command_prefix = prefix
            session.commit()
            await ctx.send(f"Command prefix set to: `{prefix}`")
        except Exception as e:
            session.rollback()
            await ctx.send("An error occurred while setting the prefix.")
        finally:
            session.close()

    @commands.command(name="set_default_channel")
    async def set_default_channel(self, ctx, channel: discord.TextChannel):
        """Set the default channel for music commands."""
        session = self.Session()
        try:
            settings = (
                session.query(ServerSettings).filter_by(guild_id=ctx.guild.id).first()
            )
            if not settings:
                settings = ServerSettings(
                    guild_id=ctx.guild.id, default_channel_id=channel.id
                )
                session.add(settings)
            else:
                settings.default_channel_id = channel.id
            session.commit()
            await ctx.send(f"Default music channel set to: {channel.mention}")
        except Exception as e:
            session.rollback()
            await ctx.send("An error occurred while setting the default channel.")
        finally:
            session.close()

    def get_prefix(self, guild_id):
        session = self.Session()
        try:
            settings = (
                session.query(ServerSettings).filter_by(guild_id=guild_id).first()
            )
            if settings and settings.command_prefix:
                return settings.command_prefix
            return "!"
        finally:
            session.close()


async def setup(bot):
    await bot.add_cog(ServerSettingsCog(bot))
