from database import Database, DownloadStatus

class DownloadManager:
    def __init__(self, database: Database):
        self.db = database

    def queue_album(self, album_id: str, artist_id: str, album_info: dict) -> None:
        """Ajoute un album et ses pistes à la file de téléchargement."""
        if not artist_id:
            raise ValueError("L'ID de l'artiste est requis pour ajouter un album")

        # Récupérer le nom de l'artiste depuis les informations de l'album
        artist_name = album_info.get('artist_name')
        
        if not artist_name and album_info.get('tracks'):
            # Fallback: utiliser le nom du premier artiste de la première piste
            if album_info['tracks'][0].get('artists'):
                artist_name = album_info['tracks'][0]['artists'][0]
        
        if not artist_name:
            artist_name = "Artiste Inconnu"
            
        # Ajouter l'artiste à la base de données
        self.db.add_artist(artist_id, artist_name)
            
        # Récupérer la date de sortie (soit de release_date soit de date)
        release_date = album_info.get('release_date') or album_info.get('date')
            
        # Ensuite ajouter l'album
        self.db.add_album(
            album_id,
            artist_id,
            album_info['title'],
            release_date,
            album_info.get('cover_url')
        )

        # Et enfin les pistes
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