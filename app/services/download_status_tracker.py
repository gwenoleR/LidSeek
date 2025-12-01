from app.database import Database, DownloadStatus
from app.utils.logger import setup_logger, with_context
from typing import Dict, List, Optional

class DownloadStatusTracker:
    def __init__(self, database: Database):
        self.db = database
        self.logger = setup_logger('download_tracker', 'downloads.log')

    def update_album_status(self, album_id: str, status: DownloadStatus) -> None:
        """Met à jour le statut d'un album."""
        self.db.update_album_status(album_id, status)
        log = with_context(self.logger, album_mbid=album_id, status=str(status))
        log.info("Album status updated")

    def update_track_status(self, track_id: str, status: DownloadStatus, local_path: Optional[str] = None, slsk_id: Optional[str] = None) -> None:
        """Met à jour le statut d'une piste."""
        self.db.update_track_status(track_id, status, local_path, slsk_id)
        log = with_context(self.logger, track_mbid=track_id, status=str(status), local_path=local_path, slsk_id=slsk_id)
        log.info("Track status updated")

    def get_album_status(self, album_id: str) -> tuple:
        """Récupère le statut d'un album."""
        return self.db.get_album_status(album_id)

    def get_tracks_status(self, album_id: str) -> Dict:
        """Récupère le statut des pistes d'un album."""
        return self.db.get_tracks_status(album_id)

    def get_pending_albums(self) -> List[Dict]:
        """Récupère tous les albums en attente de téléchargement."""
        return self.db.get_pending_albums()

    def get_downloading_albums(self) -> List[Dict]:
        """Récupère tous les albums en cours de téléchargement."""
        return self.db.get_downloading_albums()

    def update_album_progress(self, album: dict, completed_tracks: int, total_tracks: int) -> None:
        """Met à jour le statut d'un album en fonction de sa progression."""
        if completed_tracks == total_tracks:
            self.update_album_status(album['id'], DownloadStatus.COMPLETED)
            log = with_context(self.logger, album_mbid=album['id'], album_title=album['title'], completed=completed_tracks, total=total_tracks)
            log.info("Album completed")
        else:
            self.update_album_status(album['id'], DownloadStatus.DOWNLOADING)
            log = with_context(self.logger, album_mbid=album['id'], album_title=album['title'], completed=completed_tracks, total=total_tracks)
            log.info("Album in progress")

    def cancel_download(self, album_id: str) -> None:
        """Annule le téléchargement d'un album."""
        self.db.cancel_download(album_id)
        log = with_context(self.logger, album_mbid=album_id)
        log.info("Download canceled")
        
    def add_artist(self, artist_id: str, artist_name: str) -> None:
        """Ajoute un artiste à la base de données."""
        self.db.add_artist(artist_id, artist_name)
        log = with_context(self.logger, artist_mbid=artist_id, artist_name=artist_name)
        log.info("Artist added")
        
    def add_album(self, album_id: str, artist_id: str, title: str, 
                 release_date: Optional[str] = None, cover_url: Optional[str] = None) -> None:
        """Ajoute un album à la base de données."""
        self.db.add_album(album_id, artist_id, title, release_date, cover_url)
        log = with_context(self.logger, album_mbid=album_id, artist_mbid=artist_id, album_title=title, release_date=release_date)
        log.info("Album added")
        
    def add_track(self, track_id: str, album_id: str, title: str, position: str, length: Optional[str] = None,
                 artist: Optional[str] = None, album_name: Optional[str] = None, track_num: Optional[str] = None,
                 disc: Optional[str] = None, year: Optional[str] = None, albumartist: Optional[str] = None) -> None:
        """Ajoute une piste à la base de données avec tous les tags utiles."""
        self.db.add_track(track_id, album_id, title, position, length, artist, album_name, track_num, disc, year, albumartist)
        log = with_context(self.logger, track_mbid=track_id, album_mbid=album_id, track_title=title, position=position)
        log.info("Track added")