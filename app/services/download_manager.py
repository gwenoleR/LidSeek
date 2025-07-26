from database import Database, DownloadStatus
from utils.logger import setup_logger
from typing import Dict, List
import time
from .downloaders import Downloader, SlskdDownloader
import difflib

class DownloadManager:
    def __init__(self, database: Database):
        self.db = database
        self.downloader = None
        self.download_dir = "/tmp/downloads"
        self.logger = setup_logger('download_manager', 'downloads.log')

    def configure_downloader(self, downloader: Downloader):
        """Configure le téléchargeur à utiliser."""
        self.downloader = downloader

    def configure_slskd(self, host_url: str, api_key: str, url_base: str = '/'):
        """Configure un téléchargeur Slskd (méthode de compatibilité)."""
        downloader = SlskdDownloader()
        downloader.configure(host_url=host_url, api_key=api_key, url_base=url_base)
        self.configure_downloader(downloader)

    def _flatten_files(self, slskd_tracks: list) -> list:
        """Récupère récursivement tous les fichiers (ayant 'filename') dans une liste à plat."""
        files = []
        for item in slskd_tracks:
            if 'filename' in item:
                files.append(item)
            elif 'files' in item and isinstance(item['files'], list):
                files.extend(self._flatten_files(item['files']))
        return files

    def _flatten_files_with_path(self, slskd_tracks, parent_path=""):
        files = []
        for item in slskd_tracks:
            if 'filename' in item:
                # Ajoute le chemin du dossier parent si besoin
                full_path = f"{parent_path}\\{item['filename']}" if parent_path else item['filename']
                file_copy = dict(item)  # Copie pour ne pas modifier l'original
                file_copy['filename'] = full_path
                files.append(file_copy)
            elif 'files' in item and isinstance(item['files'], list):
                folder_name = item.get('name', '')
                new_parent = f"{parent_path}\\{folder_name}" if parent_path else folder_name
                files.extend(self._flatten_files_with_path(item['files'], new_parent))
        return files

    def _album_match(self, tracks: List[dict], slskd_tracks: List[dict], username: str) -> bool:
        """Vérifie si les pistes correspondent."""
        counted = []
        total_match = 0.0

        self.logger.debug(f"Vérification de la correspondance pour {len(tracks)} pistes de l'utilisateur {username}")

        # Récupérer tous les fichiers à plat
        flat_files = self._flatten_files(slskd_tracks)

        for track in tracks:
            best_match = 0.0
            track_filename = f"{track['title']}.{self.downloader.allowed_filetypes[0]}"

            for slskd_track in flat_files:
                self.logger.debug(f"Fichier Slsk: {slskd_track}")
                slskd_filename = slskd_track['filename']
                ratio = difflib.SequenceMatcher(None, track_filename, slskd_filename).ratio()
                if ratio > best_match:
                    best_match = ratio

            if best_match > self.downloader.minimum_match_ratio:
                counted.append(track_filename)
                total_match += best_match
                self.logger.debug(f"Piste '{track_filename}' correspond avec un ratio de {best_match:.2f}")

        match_result = len(counted) == len(tracks) and username not in self.downloader.ignored_users
        self.logger.info(f"Résultat de la correspondance pour {username}: {match_result} ({len(counted)}/{len(tracks)} pistes)")
        return match_result

    def _search_and_download(self, album_info: dict) -> bool:
        """Recherche et télécharge un album."""
        if not self.downloader:
            error_msg = "Aucun téléchargeur n'est configuré"
            self.logger.error(error_msg)
            raise ValueError(error_msg)

        query = f"{album_info['artist_name']} {album_info['title']}"
        self.logger.info(f"Démarrage de la recherche pour: {query}")

        try:
            search_results = self.downloader.search(query)

            for result in search_results:
                username = result['username']
                if username in self.downloader.ignored_users:
                    self.logger.debug(f"Utilisateur ignoré: {username}")
                    continue

                self.logger.info(f"Analyse des résultats de {username}")
                for file in result['files']:
                    if 'filename' not in file:
                        continue
                    if not any(file['filename'].endswith(ext) for ext in self.downloader.allowed_filetypes):
                        continue

                    file_dir = file['filename'].rsplit("\\", 1)[0]
                    try:
                        directory = self.downloader.get_directory_content(username, file_dir)
                        if isinstance(directory, dict) and 'files' in directory:
                            files = directory['files']
                        else:
                            files = directory
                        if self._album_match(album_info['tracks'], files, username):
                            self.logger.info(f"Correspondance trouvée! Téléchargement depuis {username}")
                            files = self._flatten_files_with_path(files)
                            return self.downloader.start_download(username, files)
                    except Exception as e:
                        self.logger.error(f"Erreur lors de l'accès au dossier de {username}: {str(e)}")
                        continue

            self.logger.warning(f"Aucune correspondance trouvée pour {query}")
            return False

        except Exception as e:
            self.logger.error(f"Erreur lors de la recherche: {str(e)}")
            return False

    def process_pending_downloads(self):
        """Traite les téléchargements en attente."""
        self.logger.info("Début du traitement des téléchargements en attente")
        
        pending_albums = self.db.get_pending_albums()
        self.logger.info(f"Nombre d'albums en attente: {len(pending_albums)}")
        
        for album in pending_albums:
            self.logger.info(f"Traitement de l'album: {album['title']} de {album['artist_name']}")
            success = self._search_and_download(album)
            if success:
                self.logger.info(f"Téléchargement initié pour {album['title']}")
                self.db.update_album_status(album['id'], DownloadStatus.DOWNLOADING)
            else:
                self.logger.warning(f"Échec du téléchargement pour {album['title']}")
                self.db.update_album_status(album['id'], DownloadStatus.ERROR)

        downloading_albums = self.db.get_downloading_albums()
        self.logger.info(f"Vérification de {len(downloading_albums)} téléchargements en cours")
        for album in downloading_albums:
            self._check_download_status(album)

    def _check_download_status(self, album: dict):
        """Vérifie l'état d'un téléchargement en cours."""
        self.logger.debug(f"Vérification du statut pour {album['title']}")
        
        try:
            downloads = self.downloader.get_downloads_status()
            completed = True
            
            for download in downloads:
                if any(d['directory'] == album['title'] for d in download['directories']):
                    incomplete_files = [f for f in download['files'] if 'Completed' not in f['state']]
                    if incomplete_files:
                        completed = False
                        self.logger.debug(f"{len(incomplete_files)} fichiers en cours pour {album['title']}")
                        break

            if completed:
                self.logger.info(f"Téléchargement terminé pour {album['title']}")
                self._process_completed_download(album)
                self.db.update_album_status(album['id'], DownloadStatus.COMPLETED)
                
        except Exception as e:
            self.logger.error(f"Erreur lors de la vérification du statut: {str(e)}")
        
    def _process_completed_download(self, album: dict):
        """Traite un album téléchargé."""
        self.logger.info(f"Traitement post-téléchargement pour {album['title']}")
        # À implémenter : organisation des fichiers téléchargés
        pass

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