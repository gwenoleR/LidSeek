import os
from utils.logger import setup_logger
from typing import Dict, List
from .filesystem import FileSystemService
from .download_status_tracker import DownloadStatusTracker
from database import DownloadStatus

class AlbumProcessor:
    def __init__(self, filesystem: FileSystemService, status_tracker: DownloadStatusTracker):
        self.filesystem = filesystem
        self.status_tracker = status_tracker
        self.logger = setup_logger('album_processor', 'downloads.log')

    def process_completed_album(self, album: dict) -> None:
        """Traite un album téléchargé en organisant ses fichiers."""
        self.logger.info(f"Traitement post-téléchargement pour {album['title']}")
        
        try:
            # Récupérer le statut et les pistes
            tracks = self.status_tracker.get_tracks_status(album['id'])
            if not tracks:
                self.logger.error(f"Aucune piste trouvée pour l'album {album['id']}")
                return

            # Créer le dossier de destination
            year = album.get('release_date', '').split('-')[0] if album.get('release_date') else ''
            destination_dir = self.filesystem.create_album_directory(
                album['artist_name'], 
                album['title'], 
                year
            )

            # Déplacer et renommer chaque fichier
            for track_id, track_info in tracks.items():
                if track_info['status'] != DownloadStatus.COMPLETED.value or not track_info['local_path']:
                    continue

                # Construire le nouveau nom de fichier
                track_number = str(track_info.get('position', '')).zfill(2)
                track_title = track_info['title']
                ext = os.path.splitext(track_info['local_path'])[1]
                new_filename = f"{track_number} - {track_title}{ext}"

                # Déplacer le fichier
                if not self.filesystem.move_track_file(track_info['local_path'], destination_dir, new_filename):
                    self.logger.error(f"Échec du déplacement de la piste {track_title}")
                    return

            self.logger.info(f"Traitement terminé pour l'album {album['title']}")

        except Exception as e:
            self.logger.error(f"Erreur lors du traitement de l'album: {str(e)}")
            self.logger.exception("Stack trace complète:")