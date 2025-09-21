
from app.database import Database, DownloadStatus
from app.models import Album, Artist, Track
from datetime import datetime

class LibraryService:
    def __init__(self, database: Database):
        self.db = database

    def get_all_albums(self):
        """Récupère tous les albums de la bibliothèque avec leur statut (ORM)."""
        session = self.db.session
        albums = (
            session.query(Album)
            .join(Artist, Album.artist_id == Artist.id)
            .outerjoin(Track, Album.id == Track.album_id)
            .add_entity(Artist)
            .add_entity(Track)
            .all()
        )
        # Regrouper par album
        album_dict = {}
        for album, artist, track in albums:
            if album.id not in album_dict:
                album_dict[album.id] = {
                    'id': album.id,
                    'title': album.title,
                    'cover_url': album.cover_url,
                    'status': album.status,
                    'added_date': album.added_date,
                    'release_date': album.release_date,
                    'artist_id': artist.id if artist else None,
                    'artist_name': artist.name if artist else 'Artiste inconnu',
                    'total_tracks': 0,
                    'completed_tracks': 0
                }
            album_dict[album.id]['total_tracks'] += 1 if track else 0
            if track and track.status == DownloadStatus.COMPLETED.value:
                album_dict[album.id]['completed_tracks'] += 1
        # Trier par release_date DESC, puis added_date DESC
        result = sorted(album_dict.values(), key=lambda x: (x['release_date'] or '', x['added_date']), reverse=True)
        return result

    def get_artist_albums(self, artist_id):
        """Récupère tous les albums d'un artiste spécifique (ORM)."""
        session = self.db.session
        albums = (
            session.query(Album)
            .filter(Album.artist_id == artist_id)
            .outerjoin(Track, Album.id == Track.album_id)
            .add_entity(Track)
            .all()
        )
        album_dict = {}
        for album, track in albums:
            if album.id not in album_dict:
                album_dict[album.id] = {
                    'id': album.id,
                    'title': album.title,
                    'cover_url': album.cover_url,
                    'status': album.status,
                    'added_date': album.added_date,
                    'total_tracks': 0,
                    'completed_tracks': 0
                }
            album_dict[album.id]['total_tracks'] += 1 if track else 0
            if track and track.status == DownloadStatus.COMPLETED.value:
                album_dict[album.id]['completed_tracks'] += 1
        result = sorted(album_dict.values(), key=lambda x: x['added_date'], reverse=True)
        return result