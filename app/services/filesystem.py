from utils.logger import setup_logger
import os
import shutil
import re

class FileSystemService:
    def __init__(self, base_download_dir: str, formatted_songs_dir: str):
        self.download_dir = base_download_dir
        self.formatted_songs_dir = formatted_songs_dir
        self.logger = setup_logger('filesystem', 'downloads.log')

    def normalize_path(self, path: str) -> str:
        """Normalise un chemin pour le système d'exploitation actuel."""
        return os.path.normpath(path.replace('\\', os.path.sep))

    def extract_filename(self, path: str) -> str:
        """Extrait le nom du fichier d'un chemin."""
        normalized = self.normalize_path(path)
        basename = os.path.basename(normalized)
        return basename

    def extract_dirname(self, path: str) -> str:
        """Extrait le nom du dossier d'un chemin."""
        return os.path.basename(os.path.dirname(self.normalize_path(path)))

    def create_album_directory(self, artist_name: str, album_name: str, year: str = None) -> str:
        """Crée le dossier de destination pour un album."""
        album_dir_name = f"{album_name} ({year})" if year else album_name
        artist_dir = os.path.join(self.formatted_songs_dir, artist_name)
        destination_dir = os.path.join(artist_dir, album_dir_name)
        os.makedirs(destination_dir, exist_ok=True)
        return destination_dir

    def move_track_file(self, src_path: str, dest_dir: str, new_filename: str) -> bool:
        """Déplace un fichier de piste vers sa destination finale."""
        try:
            src_path = os.path.join(self.download_dir, src_path)
            dst_path = os.path.join(dest_dir, new_filename)
            
            if os.path.exists(src_path):
                shutil.move(src_path, dst_path)
                self.logger.info(f"Fichier déplacé: {src_path} -> {dst_path}")
                return True
            else:
                self.logger.warning(f"Fichier source non trouvé: {src_path}")
                return False
        except Exception as e:
            self.logger.error(f"Erreur lors du déplacement du fichier: {str(e)}")
            return False