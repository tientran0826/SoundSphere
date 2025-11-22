from sqlalchemy import TIMESTAMP, BigInteger, Column, Integer, String, text
from sqlalchemy.orm import declarative_base

Base = declarative_base()


class PlayHistory(Base):
    __tablename__ = "play_history"

    id = Column(Integer, primary_key=True)
    guild_id = Column(BigInteger, nullable=False)
    user_id = Column(BigInteger, nullable=False)
    track_title = Column(String)
    track_author = Column(String)
    url = Column(String)
    played_at = Column(TIMESTAMP, server_default=text("NOW()"))


class QueueTracks(Base):
    __tablename__ = "queue_tracks"

    id = Column(Integer, primary_key=True)
    guild_id = Column(BigInteger, nullable=False)
    track_title = Column(String)
    url = Column(String)
    track_author = Column(String)
    added_at = Column(TIMESTAMP, server_default=text("NOW()"))
    requested_by = Column(BigInteger, nullable=False)
    position = Column(Integer, nullable=False)


class ServerSettings(Base):
    __tablename__ = "server_settings"

    guild_id = Column(BigInteger, primary_key=True)
    default_channel_id = Column(BigInteger)
    command_prefix = Column(String, default="!")
