from ..database import Database, DownloadStatus
import sqlite3
from datetime import datetime

class LibraryService:
    def __init__(self, database: Database):
        self.db = database

    def get_all_albums(self):
        """Récupère tous les albums de la bibliothèque avec leur statut."""
        with self.db._get_connection() as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            cursor.execute('''
                SELECT 
                    a.id, a.title, a.cover_url, a.status, a.added_date, a.release_date,
                    ar.id as artist_id, ar.name as artist_name,
                    COUNT(t.id) as total_tracks,
                    SUM(CASE WHEN t.status = 'completed' THEN 1 ELSE 0 END) as completed_tracks
                FROM albums a
                LEFT JOIN artists ar ON a.artist_id = ar.id
                LEFT JOIN tracks t ON a.id = t.album_id
                GROUP BY a.id, ar.id, ar.name
                ORDER BY a.release_date DESC, a.added_date DESC
            ''')
            
            return [{
                'id': row['id'],
                'title': row['title'],
                'cover_url': row['cover_url'],
                'status': row['status'],
                'added_date': datetime.fromisoformat(row['added_date']),
                'release_date': row['release_date'],
                'artist_id': row['artist_id'],
                'artist_name': row['artist_name'] or 'Artiste inconnu',
                'total_tracks': row['total_tracks'],
                'completed_tracks': row['completed_tracks']
            } for row in cursor.fetchall()]

    def get_artist_albums(self, artist_id):
        """Récupère tous les albums d'un artiste spécifique."""
        with self.db._get_connection() as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            cursor.execute('''
                SELECT 
                    a.id, a.title, a.cover_url, a.status, a.added_date, a.release_date,
                    COUNT(t.id) as total_tracks,
                    SUM(CASE WHEN t.status = 'completed' THEN 1 ELSE 0 END) as completed_tracks
                FROM albums a
                LEFT JOIN tracks t ON a.id = t.album_id
                WHERE a.artist_id = ?
                GROUP BY a.id
                ORDER BY a.release_date DESC, a.added_date DESC
            ''', (artist_id,))
            
            return [{
                'id': row['id'],
                'title': row['title'],
                'cover_url': row['cover_url'],
                'status': row['status'],
                'added_date': datetime.fromisoformat(row['added_date']),
                'release_date': row['release_date'],
                'total_tracks': row['total_tracks'],
                'completed_tracks': row['completed_tracks']
            } for row in cursor.fetchall()]