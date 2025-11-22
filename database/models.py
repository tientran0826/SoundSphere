from sqlalchemy import (
    TIMESTAMP,
    BigInteger,
    Column,
    ForeignKey,
    Integer,
    String,
    UniqueConstraint,
    text,
)
from sqlalchemy.orm import declarative_base, relationship

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


class Album(Base):
    __tablename__ = "albums"

    id = Column(Integer, primary_key=True)
    guild_id = Column(BigInteger, nullable=False)
    album_name = Column(String, nullable=False)
    album_img_url = Column(String, nullable=True)
    created_at = Column(TIMESTAMP, server_default=text("NOW()"))
    created_by = Column(BigInteger, nullable=False)

    # Ensure no duplicate album name per guild
    __table_args__ = (
        UniqueConstraint("guild_id", "album_name", name="uq_guild_album"),
    )

    # Relationship to tracks
    tracks = relationship(
        "AlbumTrack", back_populates="album", cascade="all, delete-orphan"
    )


class AlbumTrack(Base):
    __tablename__ = "album_tracks"

    id = Column(Integer, primary_key=True)
    album_id = Column(Integer, ForeignKey("albums.id"), nullable=False)
    track_title = Column(String, nullable=False)
    track_number = Column(Integer, nullable=False)
    url = Column(String, nullable=False)
    track_author = Column(String, nullable=True)
    requested_by = Column(BigInteger, nullable=False)
    added_at = Column(TIMESTAMP, server_default=text("NOW()"))

    # Relationship to album
    album = relationship("Album", back_populates="tracks")


class ServerSettings(Base):
    __tablename__ = "server_settings"

    guild_id = Column(BigInteger, primary_key=True)
    default_channel_id = Column(BigInteger)
    command_prefix = Column(String, default="!")
