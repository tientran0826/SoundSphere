import os
import time

import discord
import wavelink
from discord.ext import commands, tasks
from dotenv import load_dotenv
from loguru import logger
from sqlalchemy import create_engine
from sqlalchemy.exc import OperationalError
from sqlalchemy.orm import sessionmaker

from database.models import Base, ServerSettings
from settings import configs

# Load env variables
load_dotenv()

intents = discord.Intents.default()
intents.message_content = True

# ----------------------
# Database setup
# ----------------------
DATABASE_URL = os.getenv("DATABASE_URL")
if not DATABASE_URL:
    raise ValueError("DATABASE_URL is not set.")

engine = None
SessionLocal = None

# 2. Use a single, robust retry loop
for attempt in range(10):
    try:
        engine = create_engine(DATABASE_URL)

        # Attempt to connect/check status by issuing a command
        # This will raise OperationalError if connection fails
        engine.connect()

        Base.metadata.create_all(engine)

        SessionLocal = sessionmaker(bind=engine)
        logger.info("Database connected and tables created!")
        break  # Exit the loop on success

    except OperationalError:
        logger.info(f"Database not ready, retrying... ({attempt + 1}/10)")
        time.sleep(3)
    except Exception:
        # Catch other errors like improper model definition, config errors, etc.
        logger.info(f"Failed to connect or create tables")
        # We still sleep and retry unless it's a fatal config error
        time.sleep(3)

if engine is None:
    raise RuntimeError("Could not connect to database after 10 attempts.")


# ----------------------
# Get server config
# ----------------------
def get_server_config(guild_id: int):
    """Get server configuration from database"""
    session = SessionLocal()
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


async def get_prefix(bot, message):
    """Get command prefix from database for each server"""
    if not message.guild:
        return "!"  # Default for DMs

    config = get_server_config(message.guild.id)
    return config.command_prefix or "!"


bot = commands.Bot(command_prefix=get_prefix, intents=intents)

# ----------------------
# Load cogs
# ----------------------
initial_cogs = ["cogs.music", "cogs.general", "cogs.server"]


async def load_cogs():
    for cog in initial_cogs:
        await bot.load_extension(cog)


# ----------------------
# On ready event
# ----------------------
@bot.event
async def on_ready():
    logger.info(f"Logged in as {bot.user}")

    # Connect Lavalink node
    if not wavelink.Pool.nodes:
        node = wavelink.Node(
            uri=os.getenv("LAVALINK_URI"), password=os.getenv("LAVALINK_PASSWORD")
        )
        await wavelink.Pool.connect(client=bot, nodes=[node])
        logger.info(f"Node initiated: {node}")
        logger.info(f"Node status: {node.status}")

    if not change_status.is_running():
        change_status.start()
        logger.info("Started status rotation task.")

    for guild in bot.guilds:
        config = get_server_config(guild.id)
        channel_name = configs.DEFAULT_CHANNEL
        if config.default_channel_id:
            channel = bot.get_channel(config.default_channel_id)
            if channel:
                channel_name = channel.name

        channel_check = discord.utils.get(guild.text_channels, name=channel_name)
        if not channel_check:
            general_channel = discord.utils.get(guild.text_channels, name="general")
            if general_channel:
                await general_channel.send(
                    f"Creating {configs.DEFAULT_CHANNEL} channel..."
                )
            new_channel = await guild.create_text_channel(configs.DEFAULT_CHANNEL)

            session = SessionLocal()
            config = session.query(ServerSettings).filter_by(guild_id=guild.id).first()
            config.default_channel_id = new_channel.id
            session.commit()
            session.close()
            logger.info(f"Created {configs.DEFAULT_CHANNEL} channel in {guild.name}")
        else:
            session = SessionLocal()
            config = session.query(ServerSettings).filter_by(guild_id=guild.id).first()
            config.default_channel_id = channel_check.id
            session.commit()
            session.close()
    await load_cogs()


@bot.event
async def on_guild_join(guild):
    """Setup when bot joins new server"""
    logger.info(f"Joined new guild: {guild.name}")

    # Create server config
    config = get_server_config(guild.id)

    # Create music channel
    general_channel = discord.utils.get(guild.text_channels, name="general")
    if general_channel:
        await general_channel.send(f"👋 Hello!")
    channel_exist = discord.utils.get(guild.text_channels, name=configs.DEFAULT_CHANNEL)
    if not channel_exist:
        new_channel = await guild.create_text_channel(configs.DEFAULT_CHANNEL)
        # Save channel ID
        session = SessionLocal()
        config = session.query(ServerSettings).filter_by(guild_id=guild.id).first()
        config.default_channel_id = new_channel.id
        session.commit()
        session.close()
    else:
        session = SessionLocal()
        config = session.query(ServerSettings).filter_by(guild_id=guild.id).first()
        config.default_channel_id = channel_exist.id
        session.commit()
        session.close()


@tasks.loop(seconds=10)
async def change_status():
    statuses = [
        "Use play to start 🔥",
        "Use help_music if you are lost 🗺️",
        "music for the galaxy 🎧",
        "lofi beats all day ☕",
        "Spotify but cheaper 😎",
    ]

    import random

    status = random.choice(statuses)

    await bot.change_presence(
        activity=discord.Activity(type=discord.ActivityType.listening, name=status)
    )


@change_status.before_loop
async def before_change_status():
    """Wait until bot is ready before starting status rotation"""
    await bot.wait_until_ready()
    logger.info("Waiting for bot to be ready before status rotation...")


# ----------------------
# Run bot
# ----------------------
def run_bot():
    token = os.getenv("DISCORD_API_KEY")
    bot.run(token)


if __name__ == "__main__":
    run_bot()
