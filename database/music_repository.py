from typing import List, Optional

from loguru import logger
from sqlalchemy import create_engine, func
from sqlalchemy.orm import selectinload, sessionmaker

from database.models import Album, AlbumTrack, PlayHistory, QueueTracks, ServerSettings


class MusicRepository:
    """Repository pattern for all database operations"""

    def __init__(self, database_url: str):
        self.engine = create_engine(database_url)
        self.Session = sessionmaker(bind=self.engine)

    # ----------------------
    # Server Settings
    # ----------------------
    def get_server_config(self, guild_id: int) -> ServerSettings:
        """Get server configuration"""
        session = self.Session()
        try:
            config = session.query(ServerSettings).filter_by(guild_id=guild_id).first()
            if not config:
                config = ServerSettings(
                    guild_id=guild_id, command_prefix="!", default_channel_id=None
                )
                session.add(config)
                session.commit()
                session.refresh(config)
            return config
        finally:
            session.close()

    def update_server_config(
        self, guild_id: int, command_prefix: str = None, default_channel_id: int = None
    ) -> bool:
        """Update server configuration"""
        session = self.Session()
        try:
            config = session.query(ServerSettings).filter_by(guild_id=guild_id).first()
            if not config:
                config = ServerSettings(guild_id=guild_id)
                session.add(config)

            if command_prefix:
                config.command_prefix = command_prefix
            if default_channel_id:
                config.default_channel_id = default_channel_id

            session.commit()
            return True
        except Exception as e:
            logger.error(f"Error updating server config: {e}")
            session.rollback()
            return False
        finally:
            session.close()

    # ----------------------
    # Play History
    # ----------------------
    def save_play_history(
        self,
        guild_id: int,
        user_id: int,
        track_title: str,
        identifier: Optional[str],
        track_author: str,
        url: str,
    ) -> bool:
        """Save play history to database"""
        session = self.Session()
        try:
            history = PlayHistory(
                guild_id=guild_id,
                user_id=user_id,
                track_title=track_title,
                track_author=track_author,
                identifier=identifier,
                url=url,
            )
            session.add(history)
            session.commit()
            return True
        except Exception as e:
            logger.error(f"Error saving play history: {e}")
            session.rollback()
            return False
        finally:
            session.close()

    def get_play_history(self, guild_id: int, limit: int = 10) -> List[PlayHistory]:
        """Get recent play history"""
        session = self.Session()
        try:
            history = (
                session.query(PlayHistory)
                .filter_by(guild_id=guild_id)
                .order_by(PlayHistory.played_at.desc())
                .limit(limit)
                .all()
            )
            return history
        finally:
            session.close()

    # ----------------------
    # Queue Management
    # ----------------------
    def save_to_queue(
        self,
        guild_id: int,
        track_title: str,
        url: str,
        identifier: Optional[str],
        track_author: str,
        requested_by: int,
    ) -> bool:
        """Add track to queue"""
        session = self.Session()
        try:
            max_pos = (
                session.query(func.max(QueueTracks.position))
                .filter_by(guild_id=guild_id)
                .scalar()
            )
            next_pos = (max_pos if max_pos is not None else 0) + 1

            queue_track = QueueTracks(
                guild_id=guild_id,
                track_title=track_title,
                url=url,
                requested_by=requested_by,
                identifier=identifier,
                track_author=track_author,
                position=next_pos,
            )
            session.add(queue_track)
            session.commit()
            return True
        except Exception as e:
            logger.error(f"Error saving to queue: {e}")
            session.rollback()
            return False
        finally:
            session.close()

    def get_all_tracks_from_queue(self, guild_id: int) -> List[QueueTracks]:
        """Fetch all tracks in queue"""
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
            logger.error(f"Error fetching queue: {e}")
            return []
        finally:
            session.close()

    def pop_next_track(self, guild_id: int) -> Optional[QueueTracks]:
        """Pop first track from queue and recalculate positions"""
        session = self.Session()
        try:
            track = (
                session.query(QueueTracks)
                .filter_by(guild_id=guild_id)
                .order_by(QueueTracks.position.asc())
                .first()
            )
            if not track:
                return None

            session.delete(track)
            session.commit()

            # Recalculate positions
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
            logger.error(f"Error popping track: {e}")
            session.rollback()
            return None
        finally:
            session.close()

    def remove_from_queue(self, guild_id: int, track_position: int) -> bool:
        """Remove specific track from queue"""
        session = self.Session()
        try:
            session.query(QueueTracks).filter_by(
                guild_id=guild_id, position=track_position
            ).delete()
            session.commit()
            return True
        except Exception as e:
            logger.error(f"Error removing from queue: {e}")
            session.rollback()
            return False
        finally:
            session.close()

    def jump_to_track(self, guild_id: int, track_position: int) -> bool:
        """Set the queue's current track to the specified position"""
        session = self.Session()
        try:
            # Example: store current track in some QueueStatus table or update a flag in QueueTracks
            current_track = (
                session.query(QueueTracks)
                .filter_by(guild_id=guild_id, position=track_position)
                .first()
            )

            if not current_track:
                return False

            # Update "currently playing" marker
            session.query(QueueTracks).filter_by(guild_id=guild_id).update(
                {"is_playing": False}
            )
            current_track.is_playing = True
            session.commit()
            return True
        except Exception as e:
            logger.error(f"Error jumping to track: {e}")
            session.rollback()
            return False
        finally:
            session.close()

    def clear_queue(self, guild_id: int) -> bool:
        """Clear entire queue"""
        session = self.Session()
        try:
            session.query(QueueTracks).filter_by(guild_id=guild_id).delete()
            session.commit()
            return True
        except Exception as e:
            logger.error(f"Error clearing queue: {e}")
            session.rollback()
            return False
        finally:
            session.close()

    def shuffle_queue(self, guild_id: int) -> bool:
        """Shuffle queue"""
        session = self.Session()
        try:
            tracks = session.query(QueueTracks).filter_by(guild_id=guild_id).all()
            import random

            random.shuffle(tracks)
            for index, track in enumerate(tracks, start=1):
                track.position = index
            session.commit()
            return True
        except Exception as e:
            logger.error(f"Error shuffling queue: {e}")
            session.rollback()
            return False
        finally:
            session.close()

    # ----------------------
    # Album Management
    # ----------------------
    def create_album(
        self,
        guild_id: int,
        album_name: str,
        requested_by: int,
        album_img_url: Optional[str],
    ) -> bool:
        """Create new album"""
        print("Create album function")
        session = self.Session()
        try:
            album = Album(
                guild_id=guild_id,
                album_name=album_name,
                created_by=requested_by,
                album_img_url=album_img_url,
            )
            session.add(album)
            session.commit()
            return True
        except Exception as e:
            logger.error(f"Error creating album: {e}")
            print(e)
            session.rollback()
            return False
        finally:
            session.close()

    def remove_album(self, guild_id: int, album_name: str) -> bool:
        """Remove album and its tracks"""
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
                return True
            return False
        except Exception as e:
            logger.error(f"Error removing album: {e}")
            session.rollback()
            return False
        finally:
            session.close()

    def get_all_albums(self, guild_id: int) -> List[Album]:
        """Get all albums for guild"""
        session = self.Session()
        try:
            albums = (
                session.query(Album)
                .options(selectinload(Album.tracks))
                .filter_by(guild_id=guild_id)
                .all()
            )
            return albums
        except Exception as e:
            logger.error(f"Error fetching albums: {e}")
            return []
        finally:
            session.close()

    def update_album_info(
        self, guild_id: int, album_name: str, album_img_url: str
    ) -> bool:
        """Update album image URL"""
        session = self.Session()
        try:
            album = (
                session.query(Album)
                .filter_by(guild_id=guild_id, album_name=album_name)
                .first()
            )
            if album:
                album.album_img_url = album_img_url
                session.commit()
                return True
            return False
        except Exception as e:
            logger.error(f"Error updating album image: {e}")
            session.rollback()
            return False
        finally:
            session.close()

    def get_album_tracks(self, guild_id: int, album_name: str) -> List[AlbumTrack]:
        """Get all tracks from specific album"""
        session = self.Session()
        try:
            album = (
                session.query(Album)
                .filter_by(guild_id=guild_id, album_name=album_name)
                .first()
            )
            if not album:
                return []
            return album.tracks
        except Exception as e:
            logger.error(f"Error fetching album tracks: {e}")
            return []
        finally:
            session.close()

    def add_track_to_album(
        self,
        album_id: int,
        track_title: str,
        url: str,
        identifier: Optional[str],
        track_author: str,
        requested_by: int,
    ) -> Optional[AlbumTrack]:
        """Add track to album"""
        session = self.Session()
        try:
            max_track_number = (
                session.query(func.max(AlbumTrack.track_number))
                .filter_by(album_id=album_id)
                .scalar()
            )
            next_track_number = (
                max_track_number if max_track_number is not None else 0
            ) + 1

            album_track = AlbumTrack(
                album_id=album_id,
                track_title=track_title,
                track_number=next_track_number,
                url=url,
                identifier=identifier,
                track_author=track_author,
                requested_by=requested_by,
            )
            session.add(album_track)
            session.commit()
            session.refresh(album_track)
            return album_track
        except Exception as e:
            logger.error(f"Error adding track to album: {e}")
            session.rollback()
            return None
        finally:
            session.close()

    def add_album_to_queue(self, guild_id: int, album_name: int) -> List[dict]:
        session = self.Session()
        try:
            album = (
                session.query(Album)
                .options(selectinload(Album.tracks))  # eager load tracks
                .filter_by(guild_id=guild_id, album_name=album_name)
                .first()
            )
            # Extract plain Python list of tracks (avoid using ORM objects after session close)
            album_tracks = [
                {
                    "track_title": t.track_title,
                    "url": t.url,
                    "track_author": t.track_author,
                    "identifier": t.identifier,
                    "requested_by": t.requested_by,
                }
                for t in sorted(
                    album.tracks, key=lambda x: getattr(x, "track_number", x.id)
                )
            ]
            return album_tracks
        except Exception as e:
            logger.error(f"Error getting album tracks for queue: {e}")
            return []
        finally:
            session.close()

    def delele_all_tracks_from_queue(self, guild_id: int) -> bool:
        """Delete all tracks from queue"""
        session = self.Session()
        try:
            session.query(QueueTracks).filter_by(guild_id=guild_id).delete()
            session.commit()
            return True
        except Exception as e:
            logger.error(f"Error deleting all tracks from queue: {e}")
            session.rollback()
            return False
        finally:
            session.close()

    def remove_track_from_album(self, album_id: int, track_number: int) -> bool:
        """Remove track from album"""
        session = self.Session()
        try:
            track = (
                session.query(AlbumTrack)
                .filter_by(album_id=album_id, track_number=track_number)
                .first()
            )
            if track:
                session.delete(track)
                session.commit()
                return True
            return False
        except Exception as e:
            logger.error(f"Error removing track from album: {e}")
            session.rollback()
            return False
        finally:
            session.close()

    def get_album_by_id(self, album_id: int) -> Optional[Album]:
        """Get album by ID"""
        session = self.Session()
        try:
            album = session.query(Album).filter_by(id=album_id).first()
            return album
        finally:
            session.close()

    def get_album_by_name(self, guild_id: int, album_name: str) -> Optional[Album]:
        """Get album by name"""
        session = self.Session()
        try:
            album = (
                session.query(Album)
                .filter_by(guild_id=guild_id, album_name=album_name)
                .first()
            )
            return album
        finally:
            session.close()

    def get_max_track_number(self, album_id: int) -> int:
        """Get max track number in album"""
        session = self.Session()
        try:
            max_track_number = (
                session.query(func.max(AlbumTrack.track_number))
                .filter_by(album_id=album_id)
                .scalar()
            )
            return max_track_number if max_track_number is not None else 0
        finally:
            session.close()

    def add_track_to_album_with_number(
        self,
        album_id: int,
        track_title: str,
        url: str,
        track_author: str,
        requested_by: int,
        identifier: Optional[str],
        track_number: int,
    ) -> Optional[AlbumTrack]:
        """Add track to album with specific track number"""
        session = self.Session()
        try:
            album_track = AlbumTrack(
                album_id=album_id,
                track_title=track_title,
                track_number=track_number,
                url=url,
                identifier=identifier,
                track_author=track_author,
                requested_by=requested_by,
            )
            session.add(album_track)
            session.commit()
            session.refresh(album_track)
            return album_track
        except Exception as e:
            logger.error(f"Error adding track to album: {e}")
            session.rollback()
            return None
        finally:
            session.close()

    def remove_track_from_album_by_number(
        self, guild_id: int, album_name: str, track_number: int
    ) -> tuple[bool, Optional[str]]:
        """
        Remove track from album by track number.
        Returns (success: bool, track_title: Optional[str])
        """
        session = self.Session()
        try:
            # Find album first
            album = (
                session.query(Album)
                .filter_by(album_name=album_name, guild_id=guild_id)
                .first()
            )
            if not album:
                return False, None

            # Find track within that album
            track = (
                session.query(AlbumTrack)
                .filter_by(track_number=track_number, album_id=album.id)
                .first()
            )
            if not track:
                return False, None

            track_title = track.track_title
            session.delete(track)
            session.commit()
            return True, track_title
        except Exception as e:
            logger.error(f"Error removing track from album: {e}")
            session.rollback()
            return False, None
        finally:
            session.close()
