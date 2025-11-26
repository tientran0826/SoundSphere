from dotenv import load_dotenv
from pydantic_settings import BaseSettings

load_dotenv()


class Configs(BaseSettings):
    DISCORD_CLIENT_ID: str
    DISCORD_CLIENT_SECRET: str
    DISCORD_REDIRECT_URI: str
    FASTAPI_BASE_URL: str
    FLASK_SECRET_KEY: str = "thebestsoundbot"
    OAUTH_SCOPE: str = "identify guilds"
    DISCORD_API_BASE_URL: str = "https://discord.com/api/v10"
    LAVALINK_URI: str
    LAVALINK_PASSWORD: str
    YOUTUBE_API_KEY: str


configs = Configs()
