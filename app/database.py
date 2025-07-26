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

    def add_track(self, track_id, album_id, title, position=None, length=None):
        """Ajoute ou met à jour une piste."""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute('''
                INSERT OR REPLACE INTO tracks (id, album_id, title, position, length, status)
                VALUES (?, ?, ?, ?, ?, ?)
            ''', (track_id, album_id, title, position, length, DownloadStatus.PENDING.value))
            conn.commit()

    def update_track_status(self, track_id, status, local_path=None):
        """Met à jour le statut d'une piste."""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            if status == DownloadStatus.COMPLETED:
                cursor.execute('''
                    UPDATE tracks 
                    SET status = ?, download_date = ?, local_path = ?
                    WHERE id = ?
                ''', (status.value, datetime.now(), local_path, track_id))
            else:
                cursor.execute('''
                    UPDATE tracks 
                    SET status = ?
                    WHERE id = ?
                ''', (status.value, track_id))
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
        """Récupère le statut de toutes les pistes d'un album."""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute('''
                SELECT id, status, local_path
                FROM tracks
                WHERE album_id = ?
            ''', (album_id,))
            return {row[0]: {'status': row[1], 'local_path': row[2]} for row in cursor.fetchall()}

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