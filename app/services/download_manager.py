from database import Database, DownloadStatus
from utils.logger import setup_logger
from typing import Dict, List
import os
from config.settings import Config
from .downloaders import Downloader, SlskdDownloader
from .filesystem import FileSystemService
from .track_matcher import TrackMatcher
from .download_status_tracker import DownloadStatusTracker
from .album_processor import AlbumProcessor
from .slsk_models import SlskFile

class DownloadManager:
    def __init__(self, database: Database):
        self.downloader: SlskdDownloader = None
        self.logger = setup_logger('download_manager', 'downloads.log')
        
        # Initialiser les services
        self.filesystem = FileSystemService("/downloads", Config.FORMATTED_SONGS_DIR)
        self.status_tracker = DownloadStatusTracker(database)
        self.track_matcher = TrackMatcher()
        self.album_processor = AlbumProcessor(self.filesystem, self.status_tracker)

    def configure_downloader(self, downloader: Downloader) -> None:
        """Configure le téléchargeur à utiliser."""
        self.downloader = downloader

    def configure_slskd(self, host_url: str, api_key: str, url_base: str = '/') -> None:
        """Configure un téléchargeur Slskd."""
        downloader = SlskdDownloader()
        downloader.configure(host_url=host_url, api_key=api_key, url_base=url_base)
        self.configure_downloader(downloader)

    def queue_album(self, album_id: str, artist_id: str, album_info: dict) -> None:
        """Ajoute un album à la file de téléchargement."""
        # Ajouter l'artiste à la base de données
        artist_name = album_info.get('artist_name')
        if not artist_name and album_info.get('tracks'):
            if album_info['tracks'][0].get('artists'):
                artist_name = album_info['tracks'][0]['artists'][0]
        if not artist_name:
            artist_name = "Artiste Inconnu"
            
        self.status_tracker.add_artist(artist_id, artist_name)
            
        # Ajouter l'album
        self.status_tracker.add_album(
            album_id,
            artist_id,
            album_info['title'],
            album_info.get('release_date'),
            album_info.get('cover_url')
        )

        self.status_tracker.update_album_status(album_id, DownloadStatus.PENDING)

        # Ajouter les pistes
        for track in album_info['tracks']:
            if track.get('id'):
                self.status_tracker.add_track(
                    track['id'],
                    album_id,
                    track['title'],
                    track['position'],
                    track.get('length')
                )

    def get_album_status(self, album_id: str) -> tuple:
        """Récupère le statut d'un album."""
        return self.status_tracker.get_album_status(album_id)

    def get_tracks_status(self, album_id: str) -> dict:
        """Récupère le statut des pistes d'un album."""
        return self.status_tracker.get_tracks_status(album_id)

    def process_pending_downloads(self) -> None:
        """Traite les téléchargements en attente."""
        if not self.downloader:
            raise ValueError("Aucun téléchargeur n'est configuré")

        # Traiter les albums en attente
        pending_albums = self.status_tracker.get_pending_albums()
        self.logger.info(f"Traitement de {len(pending_albums)} albums en attente")
        
        for album in pending_albums:
            success = self._start_album_download(album)
            if success:
                self.status_tracker.update_album_status(album['id'], DownloadStatus.DOWNLOADING)
            else:
                self.status_tracker.update_album_status(album['id'], DownloadStatus.ERROR)

        # Vérifier les téléchargements en cours
        downloading_albums = self.status_tracker.get_downloading_albums()
        for album in downloading_albums:
            self._check_download_status(album)

    def _start_album_download(self, album: dict) -> bool:
        """Démarre le téléchargement d'un album."""
        try:
            # Vérifier si l'album n'est pas déjà en cours
            downloads = self.downloader.get_downloads_status()
            for download in downloads:
                if not isinstance(download, dict):
                    continue
                for directory in download.get('directories', []):
                    if directory.get('directory') == album['title']:
                        return True

            # Rechercher l'album
            query = f"{album['artist_name']} {album['title']}"
            search_results = self.downloader.search(query)
            for r in search_results:
                self.logger.debug(r)
            if not search_results:
                self.logger.warning(f"Aucun résultat trouvé pour la recherche : {query}")
                return False

            best_result = None
            best_match_count = 0
            best_directory_path = ""
            best_files: List[SlskFile] = []

            # Analyser les résultats
            for result in search_results:
                if result.username in self.downloader.ignored_users:
                    continue

                # Filtrer par type de fichier et taille minimale (pour éviter les snippets)
                valid_files = result.filter_by_extension(self.downloader.allowed_filetypes)
                valid_files = result.filter_by_size(min_size_mb=1.0)  # Ignorer les fichiers trop petits

                if not valid_files:
                    continue

                try:
                    # Pour le premier fichier valide, récupérer son dossier parent
                    directory_path = valid_files[0].get_dir_name()
                    self.logger.info(f"Récupération du contenu du dossier: {directory_path}")
                    
                    # Récupérer tous les fichiers du dossier
                    directory_files = self.downloader.get_directory_content(result.username, directory_path)
                    if not directory_files:
                        continue
                    
                    # Trouver les pistes correspondantes
                    matching_files = self.track_matcher.find_matching_tracks(
                        album['tracks'],
                        directory_files,
                        self.downloader.allowed_filetypes
                    )

                    # Log des fichiers trouvés pour le débogage
                    if matching_files:
                        self.logger.info(f"Fichiers correspondants trouvés ({len(matching_files)}):")
                        for track_id, file in matching_files.items():
                            self.logger.info(f"  - Track ID: {track_id} -> {file.filename}")

                    if matching_files and len(matching_files) > best_match_count:
                        best_directory_path = directory_path
                        best_result = result
                        best_match_count = len(matching_files)
                        best_files = matching_files.values()
                        for track_id, file in matching_files.items():
                            self.status_tracker.update_track_status(track_id,DownloadStatus.PENDING,None,file.filename)

                except Exception as e:
                    self.logger.warning(f"Erreur lors du traitement des fichiers de {result.username}: {str(e)}")
                    continue

            # Démarrer le téléchargement du meilleur résultat
            self.logger.debug(matching_files)
            if best_result and best_match_count > 0:
                self.logger.info(f"Démarrage du téléchargement avec {best_result.username} ({best_match_count} fichiers)")
                return self.downloader.start_download(best_result.username, best_directory_path, best_files)

            self.logger.warning(f"Aucune correspondance trouvée pour l'album : {album['title']}")
            return False

        except Exception as e:
            self.logger.error(f"Erreur lors du démarrage du téléchargement: {str(e)}")
            self.logger.exception("Stack trace complète:")
            return False

    def _check_download_status(self, album: dict) -> None:
        """Vérifie l'état d'un téléchargement en cours."""
        try:
            # Récupérer les fichiers du dossier
            album_folder = self.filesystem.extract_filename(album['title'])
            files = self.downloader.get_directory_files_status(album_folder)
            if not files:
                return

            # Récupérer les pistes et leur statut
            tracks = self.status_tracker.get_tracks_status(album['id'])
            completed_tracks = 0
            total_tracks = len(tracks)

            for track_id, track_info in tracks.items():
                self.logger.debug(f"Recherche de correspondance pour la piste {track_id} : {track_info['title']} dans la liste des téléchargements.")
                for file in files:
                    file_name = self.filesystem.extract_filename(file['filename'])
                    normalized_path = self.filesystem.normalize_path(file['filename'])
                    local_path = f"{os.path.basename(os.path.dirname(normalized_path))}/{os.path.basename(normalized_path)}"

                    ratio = self.track_matcher.compare_track_names(f"{track_info['title']}.fakeext", file_name)

                    if file_name == track_info['slsk_id']:
                        self.logger.debug(f"File status: {file['state']}")
                        if file['state'] == 'Completed, Succeeded':
                            self.status_tracker.update_track_status(
                                track_id,
                                DownloadStatus.COMPLETED,
                                local_path,
                                track_info['slsk_id']
                            )
                            completed_tracks += 1
                        elif file['state'] == 'InProgress':
                            self.status_tracker.update_track_status(
                                track_id,
                                DownloadStatus.DOWNLOADING,
                                None,
                                track_info['slsk_id']
                            )
                        elif 'Completed' in file['state'] and 'Error' in file['state']:
                            self.status_tracker.update_track_status(track_id, DownloadStatus.ERROR)
                        break
                        

           
            self.logger.debug(f"Total files: {len(files)}")

            # Mettre à jour le statut de l'album
            self.status_tracker.update_album_progress(album, completed_tracks, total_tracks)

            # Traiter l'album s'il est terminé
            if completed_tracks == total_tracks:
                self.album_processor.process_completed_album(album)
                for downloadedFile in files:
                    self.downloader.remove_download(downloadedFile['username'], downloadedFile['id'], )
                    # self.downloader.clear_completed_downloads()

        except Exception as e:
            self.logger.error(f"Erreur lors de la vérification du statut: {str(e)}")

    def cancel_album(self, album_id: str) -> None:
        """Annule le téléchargement d'un album."""
        self.status_tracker.cancel_download(album_id)