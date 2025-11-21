import discord
from discord.ext import commands
from dotenv import load_dotenv
import os
import wavelink
from database.models import QueueTracks

load_dotenv()

intents = discord.Intents.default()
intents.message_content = True

bot = commands.Bot(command_prefix="!", intents=intents)
DEFAULT_CHANNEL = "music-player"

# ----------------------
# Load cogs
# ----------------------
initial_cogs = ["cogs.music", "cogs.general"]
async def load_cogs():
    for cog in initial_cogs:
        await bot.load_extension(cog)

# ----------------------
# On ready event
# ----------------------
@bot.event
async def on_ready():
    print(f"Logged in as {bot.user}")

    # Connect Lavalink node
    if not wavelink.Pool.nodes:
        node = wavelink.Node(
            uri=os.getenv("LAVALINK_URI"),
            password=os.getenv("LAVALINK_PASSWORD")
        )
        await wavelink.Pool.connect(client=bot, nodes=[node])
        print(f"Node initiated: {node}")
        print(f"Node status: {node.status}")

    guild = bot.guilds[0]
    channel_check = discord.utils.get(guild.text_channels, name=DEFAULT_CHANNEL)
    if not channel_check:
        general_channel = discord.utils.get(guild.text_channels, name="general")
        if general_channel:
            await general_channel.send(f"Creating {DEFAULT_CHANNEL} channel...")
        await guild.create_text_channel(DEFAULT_CHANNEL)
    else:
        general_channel = discord.utils.get(guild.text_channels, name="general")
        if general_channel:
            await general_channel.send(f"Channel {DEFAULT_CHANNEL} already exists. Ready!")
    await load_cogs()

@bot.event


@bot.event
async def on_wavelink_node_ready(payload: wavelink.NodeReadyEventPayload):
    print(f"Lavalink node {payload.node.identifier} is connected and ready!")
    
# ----------------------
# Run bot
# ----------------------
def run_bot():
    token = os.getenv("DISCORD_API_KEY")
    bot.run(token)

if __name__ == "__main__":
    run_bot()
