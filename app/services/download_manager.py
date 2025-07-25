from database import Database, DownloadStatus

class DownloadManager:
    def __init__(self, database: Database):
        self.db = database

    def queue_album(self, album_id: str, artist_id: str, album_info: dict) -> None:
        """Ajoute un album et ses pistes à la file de téléchargement."""
        self.db.add_album(
            album_id,
            artist_id,
            album_info['title'],
            None,  # release_date
            album_info.get('cover_url')
        )

        for track in album_info['tracks']:
            if track.get('id'):
                self.db.add_track(
                    track['id'],
                    album_id,
                    track['title'],
                    track['position'],
                    track['length']
                )

    def cancel_album(self, album_id: str) -> None:
        """Annule le téléchargement d'un album."""
        self.db.cancel_download(album_id)

    def get_album_status(self, album_id: str) -> tuple:
        """Récupère le statut d'un album."""
        return self.db.get_album_status(album_id)

    def get_tracks_status(self, album_id: str) -> dict:
        """Récupère le statut des pistes d'un album."""
        return self.db.get_tracks_status(album_id)

    def get_pending_tracks(self) -> list:
        """Récupère toutes les pistes en attente de téléchargement."""
        return self.db.get_pending_tracks()