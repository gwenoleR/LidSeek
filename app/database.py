import sqlite3
from datetime import datetime
from enum import Enum
import os

class DownloadStatus(Enum):
    PENDING = "pending"
    DOWNLOADING = "downloading"
    COMPLETED = "completed"
    ERROR = "error"

class Database:
    def __init__(self, db_path="data/downloads.db"):
        self.db_path = db_path
        os.makedirs(os.path.dirname(self.db_path), exist_ok=True)  # Création du dossier si nécessaire
        self.init_db()

    def init_db(self):
        """Initialise la base de données avec les tables nécessaires."""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            
            # Table des artistes
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS artists (
                    id TEXT PRIMARY KEY,
                    name TEXT NOT NULL,
                    added_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            ''')

            # Table des albums
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS albums (
                    id TEXT PRIMARY KEY,
                    artist_id TEXT NOT NULL,
                    title TEXT NOT NULL,
                    release_date TEXT,
                    cover_url TEXT,
                    status TEXT DEFAULT 'pending',
                    added_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    download_date TIMESTAMP,
                    FOREIGN KEY (artist_id) REFERENCES artists (id)
                )
            ''')

            # Table des pistes
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS tracks (
                    id TEXT PRIMARY KEY,
                    album_id TEXT NOT NULL,
                    title TEXT NOT NULL,
                    position TEXT,
                    length INTEGER,
                    status TEXT DEFAULT 'pending',
                    added_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    download_date TIMESTAMP,
                    local_path TEXT,
                    slsk_id TEXT,
                    artist TEXT, 
                    album TEXT, 
                    track TEXT, 
                    disc TEXT, 
                    year TEXT, 
                    albumartist TEXT,
                    FOREIGN KEY (album_id) REFERENCES albums (id)
                )
            ''')

            conn.commit()

    def add_artist(self, artist_id, name):
        """Ajoute ou met à jour un artiste."""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute('''
                INSERT OR REPLACE INTO artists (id, name)
                VALUES (?, ?)
            ''', (artist_id, name))
            conn.commit()

    def add_album(self, album_id, artist_id, title, release_date=None, cover_url=None):
        """Ajoute ou met à jour un album."""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute('''
                INSERT OR REPLACE INTO albums (id, artist_id, title, release_date, cover_url, status)
                VALUES (?, ?, ?, ?, ?, ?)
            ''', (album_id, artist_id, title, release_date, cover_url, DownloadStatus.PENDING.value))
            conn.commit()

    def add_track(self, track_id, album_id, title, position=None, length=None, artist=None, album=None, track=None, disc=None, year=None, albumartist=None):
        """Ajoute ou met à jour une piste avec tags."""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute('''
                INSERT OR REPLACE INTO tracks (
                    id, album_id, title, position, length, status,
                    artist, album, track, disc, year, albumartist
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''', (
                track_id, album_id, title, position, length, DownloadStatus.PENDING.value,
                artist, album, track, disc, year, albumartist
            ))
            conn.commit()

    def update_track_status(self, track_id, status, local_path=None, slsk_id=None):
        """Met à jour le statut d'une piste."""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            if status == DownloadStatus.COMPLETED:
                cursor.execute('''
                    UPDATE tracks 
                    SET status = ?, download_date = ?, local_path = ?, slsk_id = ?
                    WHERE id = ?
                ''', (status.value, datetime.now(), local_path, slsk_id, track_id))
            else:
                cursor.execute('''
                    UPDATE tracks 
                    SET status = ?, slsk_id = ?
                    WHERE id = ?
                ''', (status.value, slsk_id , track_id))
            conn.commit()

    def update_album_status(self, album_id, status):
        """Met à jour le statut d'un album."""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            if status == DownloadStatus.COMPLETED:
                cursor.execute('''
                    UPDATE albums 
                    SET status = ?, download_date = ?
                    WHERE id = ?
                ''', (status.value, datetime.now(), album_id))
            else:
                cursor.execute('''
                    UPDATE albums 
                    SET status = ?
                    WHERE id = ?
                ''', (status.value, album_id))
            conn.commit()

    def get_pending_tracks(self):
        """Récupère toutes les pistes en attente de téléchargement."""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute('''
                SELECT t.id, t.album_id, t.title, t.position, a.artist_id, ar.name
                FROM tracks t
                JOIN albums a ON t.album_id = a.id
                JOIN artists ar ON a.artist_id = ar.id
                WHERE t.status = ?
            ''', (DownloadStatus.PENDING.value,))
            return cursor.fetchall()

    def get_pending_albums(self):
        """Récupère tous les albums en attente de téléchargement."""
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            cursor.execute('''
                SELECT 
                    a.id, a.title, a.artist_id,
                    ar.name as artist_name,
                    t.id as track_id, t.title as track_title,
                    t.position as track_position
                FROM albums a
                JOIN artists ar ON a.artist_id = ar.id
                JOIN tracks t ON a.id = t.album_id
                WHERE a.status = ?
                ORDER BY a.added_date, t.position
            ''', (DownloadStatus.PENDING.value,))
            
            results = cursor.fetchall()
            albums = {}
            
            for row in results:
                album_id = row['id']
                if album_id not in albums:
                    albums[album_id] = {
                        'id': album_id,
                        'title': row['title'],
                        'artist_name': row['artist_name'],
                        'artist_id': row['artist_id'],
                        'tracks': []
                    }
                
                albums[album_id]['tracks'].append({
                    'id': row['track_id'],
                    'title': row['track_title'],
                    'position': row['track_position']
                })
            
            return list(albums.values())

    def get_downloading_albums(self):
        """Récupère tous les albums en cours de téléchargement."""
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            cursor.execute('''
                SELECT 
                    a.id, a.title, a.artist_id, a.release_date,
                    ar.name as artist_name
                FROM albums a
                JOIN artists ar ON a.artist_id = ar.id
                WHERE a.status = ?
            ''', (DownloadStatus.DOWNLOADING.value,))
            
            return [dict(row) for row in cursor.fetchall()]

    def get_album_status(self, album_id):
        """Récupère le statut d'un album et ses pistes."""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute('''
                SELECT 
                    a.id, a.title, a.status,
                    COUNT(t.id) as total_tracks,
                    SUM(CASE WHEN t.status = 'completed' THEN 1 ELSE 0 END) as completed_tracks
                FROM albums a
                LEFT JOIN tracks t ON a.id = t.album_id
                WHERE a.id = ?
                GROUP BY a.id
            ''', (album_id,))
            return cursor.fetchone()

    def get_tracks_status(self, album_id):
        """Récupère le statut de toutes les pistes d'un album.
        
        Args:
            album_id: L'identifiant de l'album
            
        Returns:
            Un dictionnaire avec les clés étant les IDs des pistes et les valeurs contenant
            'status', 'local_path', 'position' et 'title'
        """
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute('''
                SELECT id, status, local_path, position, title, slsk_id
                FROM tracks
                WHERE album_id = ?
            ''', (album_id,))
            return {row[0]: {
                'status': row[1], 
                'local_path': row[2],
                'position': row[3],
                'title': row[4],
                'slsk_id': row[5]
            } for row in cursor.fetchall()}

    def cancel_download(self, album_id):
        """Annule le téléchargement d'un album et de ses pistes."""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            
            # Supprimer les pistes de l'album
            cursor.execute('''
                DELETE FROM tracks
                WHERE album_id = ?
            ''', (album_id,))
            
            # Supprimer l'album
            cursor.execute('''
                DELETE FROM albums
                WHERE id = ?
            ''', (album_id,))
            conn.commit()