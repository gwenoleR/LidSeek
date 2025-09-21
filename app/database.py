from datetime import datetime
from enum import Enum
from app.db import SessionLocal
from app.utils.logger import setup_logger
from app.models import Artist, Album, Track, AlbumBlacklistSource

class DownloadStatus(Enum):
    PENDING = "pending"
    DOWNLOADING = "downloading"
    COMPLETED = "completed"
    ERROR = "error"

class Database:
    def __init__(self):
        self.session = SessionLocal()
        self.logger = setup_logger('database', 'database.log')

    def add_artist(self, artist_id, name):
        artist = self.session.get(Artist, artist_id)
        if artist:
            artist.name = name
        else:
            artist = Artist(id=artist_id, name=name)
            self.logger.info(f"add_artist: type(artist)={type(artist)} value={artist}")
            if not hasattr(artist, '_sa_instance_state'):
                self.logger.error(f"add_artist: Invalid type passed to session.add: {type(artist)} value={artist}")
                raise TypeError(f"add_artist: Expected SQLAlchemy model instance, got {type(artist)}")
            self.session.add(artist)
        self.session.commit()
        self.logger.info(f"add_artist: committed for id={artist_id}")

    def add_album(self, album_id, artist_id, title, release_date=None, cover_url=None):
        album = self.session.get(Album, album_id)
        if album:
            album.title = title
            album.release_date = release_date
            album.cover_url = cover_url
        else:
            album = Album(id=album_id, artist_id=artist_id, title=title, release_date=release_date, cover_url=cover_url)
            self.logger.info(f"add_album: type(album)={type(album)} value={album}")
            if not hasattr(album, '_sa_instance_state'):
                self.logger.error(f"add_album: Invalid type passed to session.add: {type(album)} value={album}")
                raise TypeError(f"add_album: Expected SQLAlchemy model instance, got {type(album)}")
            self.session.add(album)
        self.session.commit()
        # Vérifie que l'album est bien présent après commit
        album_check = self.session.get(Album, album_id)
        if album_check:
            self.logger.info(f"add_album: commit OK, album present in DB (id={album_id})")
        else:
            self.logger.error(f"add_album: commit FAIL, album NOT present in DB (id={album_id})")

    def add_track(self, track_id, album_id, title, position=None, length=None, artist=None, album_name=None, track_num=None, disc=None, year=None, albumartist=None):
        track_obj = self.session.get(Track, track_id)
        if track_obj:
            track_obj.title = title
            track_obj.position = position
            track_obj.length = length
            track_obj.artist = artist
            track_obj.album_name = album_name
            track_obj.track = track_num
            track_obj.disc = disc
            track_obj.year = year
            track_obj.albumartist = albumartist
        else:
            self.logger.info(f"Track not found on DB. Create it.")
            self.logger.info(f"id={track_id}, album_id={album_id}, title={title}, position={position}, length={length}, artist={artist}, album_name={album_name}, track={track_num}, disc={disc}, year={year}, albumartist={albumartist}")
            track_obj = Track(id=track_id, album_id=album_id, title=title, position=position, length=length, artist=artist, album_name=album_name, track=track_num, disc=disc, year=year, albumartist=albumartist)
            self.logger.info(f"add_track: type(track_obj)={type(track_obj)} value={track_obj}")
            if not hasattr(track_obj, '_sa_instance_state'):
                self.logger.error(f"add_track: Invalid type passed to session.add: {type(track_obj)} value={track_obj}")
                raise TypeError(f"add_track: Expected SQLAlchemy model instance, got {type(track_obj)}")
            self.session.add(track_obj)
        self.session.commit()
        self.logger.info(f"add_track: committed for id={track_id}")

    def add_blacklisted_source(self, album_id, username):
        bl = self.session.query(AlbumBlacklistSource).filter_by(album_id=album_id, username=username).first()
        if not bl:
            bl = AlbumBlacklistSource(album_id=album_id, username=username)
            self.logger.info(f"add_blacklisted_source: type(bl)={type(bl)} value={bl}")
            if not hasattr(bl, '_sa_instance_state'):
                self.logger.error(f"add_blacklisted_source: Invalid type passed to session.add: {type(bl)} value={bl}")
                raise TypeError(f"add_blacklisted_source: Expected SQLAlchemy model instance, got {type(bl)}")
            self.session.add(bl)
            self.session.commit()

    def get_blacklisted_sources(self, album_id):
        return [bl.username for bl in self.session.query(AlbumBlacklistSource).filter_by(album_id=album_id).all()]

    def set_album_source_username(self, album_id, username):
        album = self.session.get(Album, album_id)
        if album:
            album.source_username = username
            self.session.commit()

    def get_album_source_username(self, album_id):
        album = self.session.get(Album, album_id)
        return album.source_username if album and album.source_username else None

    def update_track_status(self, track_id, status, local_path=None, slsk_id=None):
        track = self.session.get(Track, track_id)
        if not track:
            return
        track.status = status.value
        if status == DownloadStatus.COMPLETED:
            track.download_date = datetime.now()
            track.local_path = local_path
            track.slsk_id = slsk_id
        else:
            track.slsk_id = slsk_id
        self.session.commit()

    def update_album_status(self, album_id, status):
        album = self.session.get(Album, album_id)
        if not album:
            self.logger.error(f"update_album_status: Album not found for id={album_id} (status={status})")
            return
        album.status = status.value
        if status == DownloadStatus.COMPLETED:
            album.download_date = datetime.now()
        self.session.commit()

    def get_pending_tracks(self):
        # Retourne (track_id, album_id, title, position, artist_id, artist_name)
        q = (
            self.session.query(Track.id, Track.album_id, Track.title, Track.position, Album.artist_id, Artist.name)
            .join(Album, Track.album_id == Album.id)
            .join(Artist, Album.artist_id == Artist.id)
            .filter(Track.status == DownloadStatus.PENDING.value)
        )
        return q.all()

    def get_pending_albums(self):
        # Retourne une liste de dicts avec id, title, artist_name, artist_id, tracks[]
        q = (
            self.session.query(Album, Artist, Track)
            .join(Artist, Album.artist_id == Artist.id)
            .join(Track, Album.id == Track.album_id)
            .filter(Album.status == DownloadStatus.PENDING.value)
            .order_by(Album.added_date, Track.position)
        )
        albums = {}
        for album, artist, track in q:
            if album.id not in albums:
                albums[album.id] = {
                    'id': album.id,
                    'title': album.title,
                    'artist_name': artist.name,
                    'artist_id': artist.id,
                    'tracks': []
                }
            albums[album.id]['tracks'].append({
                'id': track.id,
                'title': track.title,
                'position': track.position
            })
        return list(albums.values())

    def get_downloading_albums(self):
        # Retourne une liste de dicts avec id, title, artist_id, release_date, artist_name
        q = (
            self.session.query(Album, Artist)
            .join(Artist, Album.artist_id == Artist.id)
            .filter(Album.status == DownloadStatus.DOWNLOADING.value)
        )
        return [
            {
                'id': album.id,
                'title': album.title,
                'artist_id': album.artist_id,
                'release_date': album.release_date,
                'artist_name': artist.name
            }
            for album, artist in q
        ]

    def get_album_status(self, album_id):
        # Retourne (id, title, status, total_tracks, completed_tracks)
        album = self.session.get(Album, album_id)
        if not album:
            return None
        total_tracks = len(album.tracks)
        completed_tracks = sum(1 for t in album.tracks if t.status == DownloadStatus.COMPLETED.value)
        return (album.id, album.title, album.status, total_tracks, completed_tracks)

    def get_tracks_status(self, album_id):
        # Retourne {track_id: {status, local_path, position, title, slsk_id}}
        tracks = self.session.query(Track).filter_by(album_id=album_id).all()
        return {
            t.id: {
                'status': t.status,
                'local_path': t.local_path,
                'position': t.position,
                'title': t.title,
                'slsk_id': t.slsk_id
            }
            for t in tracks
        }

    def cancel_download(self, album_id):
        # Supprime les pistes puis l'album
        self.session.query(Track).filter_by(album_id=album_id).delete()
        self.session.query(Album).filter_by(id=album_id).delete()
        self.session.commit()