from ..database import Database, DownloadStatus
from ..utils.logger import setup_logger
from typing import Dict, List
import time
import re
import difflib
import os
import json
import logging
import shutil
from enum import Enum
from .downloaders import Downloader, SlskdDownloader, SlskdFileState
from ..config.settings import Config

class SlskdState(Enum):
    """États possibles d'un fichier dans Slskd"""
    REQUESTED = "Requested"
    QUEUED = "Queued"
    IN_PROGRESS = "InProgress"
    COMPLETED = "Completed"
    COMPLETED_ERRORED = "Completed, Errored"
    COMPLETED_CANCELLED = "Completed, Cancelled"
    COMPLETED_TIMEOUT = "Completed, TimedOut"

class DownloadManager:
    def __init__(self, database: Database):
        self.db = database
        self.downloader = None
        self.download_dir = "/tmp/downloads"
        self.logger = setup_logger('download_manager', 'downloads.log')

    def _normalize_path(self, path: str) -> str:
        """Normalise un chemin pour le système d'exploitation actuel."""
        return os.path.normpath(path.replace('\\', os.path.sep))

    def _extract_filename(self, path: str) -> str:
        """Extrait le nom du fichier d'un chemin."""
        normalized = self._normalize_path(path)
        self.logger.info(f"Extraction du nom depuis le chemin: '{path}'")
        self.logger.info(f"Chemin normalisé: '{normalized}'")
        basename = os.path.basename(normalized)
        self.logger.info(f"Nom extrait: '{basename}'")
        return basename

    def _extract_dirname(self, path: str) -> str:
        """Extrait le nom du dossier d'un chemin."""
        return os.path.basename(os.path.dirname(self._normalize_path(path)))

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

        # Vérifier si l'album n'est pas déjà en cours de téléchargement
        try:
            downloads = self.downloader.get_downloads_status()
            for download in downloads:
                for directory in download.get('directories', []):
                    if directory.get('directory') == album_info['title']:
                        self.logger.info(f"L'album {album_info['title']} est déjà en cours de téléchargement")
                        return True
        except Exception as e:
            self.logger.error(f"Erreur lors de la vérification des téléchargements existants: {str(e)}")

        query = f"{album_info['artist_name']} {album_info['title']}"
        self.logger.info(f"Démarrage de la recherche pour: {query}")

        try:
            search_results = self.downloader.search(query)
            best_match = None
            best_match_count = 0
            best_match_user = None

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

                        # Compter le nombre de pistes correspondantes
                        matching_files = self._get_matching_tracks(album_info['tracks'], files, username)
                        if matching_files and len(matching_files) > best_match_count:
                            best_match = matching_files
                            best_match_count = len(matching_files)
                            best_match_user = username
                            
                    except Exception as e:
                        self.logger.error(f"Erreur lors de l'accès au dossier de {username}: {str(e)}")
                        continue

            # Télécharger le meilleur résultat trouvé
            if best_match and best_match_user:
                self.logger.info(f"Meilleure correspondance trouvée: {best_match_count} pistes de {best_match_user}")
                return self.downloader.start_download(best_match_user, best_match)

            self.logger.warning(f"Aucune correspondance trouvée pour {query}")
            return False

        except Exception as e:
            self.logger.error(f"Erreur lors de la recherche: {str(e)}")
            return False

    def _get_matching_tracks(self, tracks: List[dict], slskd_files: List[dict], username: str) -> List[dict]:
        """Identifie les pistes correspondantes dans les fichiers Slskd."""
        matching_files = []
        track_matches = 0

        # Récupérer tous les fichiers à plat
        flat_files = self._flatten_files_with_path(slskd_files)
        required_tracks = len(tracks)

        for track in tracks:
            best_match = None
            best_ratio = 0
            track_filename = f"{track['title']}.{self.downloader.allowed_filetypes[0]}"

            for slskd_file in flat_files:
                if not any(slskd_file['filename'].endswith(ext) for ext in self.downloader.allowed_filetypes):
                    continue

                filename = slskd_file['filename'].split("\\")[-1]
                ratio = difflib.SequenceMatcher(None, track_filename, filename).ratio()
                
                if ratio > best_ratio and ratio > self.downloader.minimum_match_ratio:
                    best_ratio = ratio
                    best_match = slskd_file

            if best_match:
                track_matches += 1
                if best_match not in matching_files:  # Éviter les doublons
                    matching_files.append(best_match)

        # Ne retourner les fichiers que si toutes les pistes sont trouvées
        if track_matches == required_tracks:
            self.logger.info(f"Toutes les pistes trouvées ({track_matches}/{required_tracks}) pour {username}")
            return matching_files
        
        self.logger.info(f"Correspondance partielle ({track_matches}/{required_tracks}) pour {username}")
        return []

    def process_pending_downloads(self):
        """Traite les téléchargements en attente."""
        self.logger.info("Début du traitement des téléchargements en attente")
        
        # Traiter les albums en attente
        pending_albums = self.db.get_pending_albums()
        self.logger.info(f"Nombre d'albums en attente: {len(pending_albums)}")
        
        for album in pending_albums:
            self.logger.info(f"Traitement de l'album en attente: {album['title']} de {album['artist_name']}")
            success = self._search_and_download(album)
            if success:
                self.logger.info(f"Téléchargement initié pour {album['title']}")
                self.db.update_album_status(album['id'], DownloadStatus.DOWNLOADING)
            else:
                self.logger.warning(f"Échec du téléchargement pour {album['title']}")
                self.db.update_album_status(album['id'], DownloadStatus.ERROR)

        # Ensuite vérifier les téléchargements en cours
        downloading_albums = self.db.get_downloading_albums()
        self.logger.info(f"Vérification de {len(downloading_albums)} téléchargements en cours")
        for album in downloading_albums:
            self._check_download_status(album)

    def _check_download_status(self, album: dict):
        """Vérifie l'état d'un téléchargement en cours."""
        self.logger.debug(f"Vérification du statut pour l'album: {album}")
        
        try:
            # Récupérer le nom final du dossier de l'album
            album_folder_name = self._extract_filename(album['title'])
            self.logger.info(f"Recherche du dossier avec le nom: '{album_folder_name}'")
            
            # Récupérer directement les fichiers du dossier
            files = self.downloader.get_directory_files_status(album_folder_name)
            if not files:
                self.logger.warning(f"Album '{album_folder_name}' non trouvé dans les téléchargements actifs")
                return
                
            # Récupérer les pistes de l'album depuis la BDD
            album_tracks = self.db.get_tracks_status(album['id'])
            completed_tracks = 0
            total_tracks = len(album_tracks)  # Utiliser le nombre total de pistes de l'album
            
            # Vérifier chaque fichier du répertoire
            for file in files:
                file_name = self._extract_filename(file['filename'])
                
                normalized_filename = os.path.normpath(file['filename'].replace('\\', os.path.sep))
                local_trackname =  os.path.basename( normalized_filename)
                local_foldername = os.path.basename(os.path.split( normalized_filename)[0])
                local_path = f"{local_foldername}/{local_trackname}"
                
                state = file.get('state', '')
                self.logger.debug(f"État du fichier {file_name}: {state}")
                
                # Trouver la piste correspondante
                for track_id, track_info in album_tracks.items():
                    if self._match_filename_to_track(file_name, track_info.get('title', '')):
                        if state == SlskdFileState.COMPLETED.value:
                            self.db.update_track_status(
                                track_id, 
                                DownloadStatus.COMPLETED,
                                local_path
                            )
                            completed_tracks += 1
                            self.logger.info(f"Piste {track_info.get('title')} marquée comme terminée")
                        elif SlskdFileState.is_completed_with_error(state):
                            self.db.update_track_status(track_id, DownloadStatus.ERROR)
                            self.logger.warning(f"Erreur pour la piste {track_info.get('title')}")
                        elif SlskdFileState.is_in_progress(state):
                            self.db.update_track_status(track_id, DownloadStatus.DOWNLOADING)
                            self.logger.debug(f"Piste {track_info.get('title')} en cours de téléchargement")
                        break
            
            # Mise à jour du statut de l'album
            self.logger.info(f"État du téléchargement pour {album_folder_name}: {completed_tracks}/{total_tracks} pistes terminées")
            if completed_tracks == total_tracks:
                self.db.update_album_status(album['id'], DownloadStatus.COMPLETED)
                self._process_completed_download(album)
            else:
                self.db.update_album_status(album['id'], DownloadStatus.DOWNLOADING)
                
        except Exception as e:
            self.logger.error(f"Erreur lors de la vérification du statut: {str(e)}")
            self.logger.exception("Stack trace complète:")

    def _clean_string(self, text: str) -> str:
        """Nettoie une chaîne pour la comparaison."""
        # Enlever l'extension si présente mais garder les autres parties après les points
        if text.lower().endswith(('.mp3', '.flac', '.m4a', '.wav')):
            text = text.rsplit('.', 1)[0]
        
        # Nettoyer en gardant les chiffres et les points
        cleaned = ''
        for c in text.lower():
            if c.isalnum() or c == '.':  # On garde les points
                cleaned += c
            elif c.isspace() and cleaned and not cleaned[-1].isspace():
                cleaned += ' '
        
        # Normaliser les espaces
        return cleaned.strip()

    def _match_filename_to_track(self, filename: str, track_title: str) -> bool:
        """Compare un nom de fichier avec un titre de piste."""
        if not track_title:
            self.logger.warning(f"Titre de piste vide pour le fichier {filename}")
            return False
            
        self.logger.debug(f"Comparaison du fichier '{filename}' avec le titre '{track_title}'")
        
        # Nettoyer les noms pour la comparaison
        clean_filename = self._clean_string(filename)
        clean_title = self._clean_string(track_title)
        
        if not clean_filename or not clean_title:
            self.logger.debug("Un des noms est vide après nettoyage")
            return False
            
        self.logger.debug(f"Noms nettoyés - Fichier: '{clean_filename}', Titre: '{clean_title}'")
        
        # Calculer le ratio de similarité
        ratio = difflib.SequenceMatcher(None, clean_filename, clean_title).ratio()
        self.logger.debug(f"Ratio de similarité: {ratio}")
        
        # La correspondance est vraie si:
        # 1. Le titre fait au moins 4 caractères ET est contenu dans le nom du fichier
        # 2. OU le ratio de similarité est supérieur au minimum requis
        title_match = len(clean_title) >= 4 and clean_title in clean_filename
        ratio_match = ratio > 0.85 #self.downloader.minimum_match_ratio
        
        self.logger.debug(f"Correspondance par contenu: {title_match}")
        self.logger.debug(f"Correspondance par ratio: {ratio_match}")
        
        is_match = title_match or ratio_match
        self.logger.debug(f"Résultat final de la correspondance: {is_match}")
        
        return is_match
    
    def _process_completed_download(self, album: dict):
        """Traite un album téléchargé en déplaçant et renommant les fichiers."""
        self.logger.info(f"Traitement post-téléchargement pour {album['title']}")
        
        try:
            # 1. Obtenir les informations de l'album depuis la BDD
            album_status = self.db.get_album_status(album['id'])
            if not album_status:
                self.logger.error(f"Album {album['id']} non trouvé dans la base de données")
                return

            # Récupérer les pistes et leur statut
            tracks = self.db.get_tracks_status(album['id'])
            if not tracks:
                self.logger.error(f"Aucune piste trouvée pour l'album {album['id']}")
                return

            # 2. Créer le dossier de destination avec l'artiste et l'année
            year = album.get('release_date', '').split('-')[0] if album.get('release_date') else ''
            artist_dir = os.path.join(Config.FORMATTED_SONGS_DIR, album['artist_name'])
            album_dir_name = f"{album['title']} ({year})" if year else album['title']
            destination_dir = os.path.join(artist_dir, album_dir_name)
            os.makedirs(destination_dir, exist_ok=True)

            # 3. Déplacer et renommer chaque fichier
            for track_id, track_info in tracks.items():
                if track_info['status'] != DownloadStatus.COMPLETED.value or not track_info['local_path']:
                    continue

                # Construire le nouveau nom de fichier avec le bon numéro de piste
                track_number = str(track_info.get('position', '')).zfill(2)  # Convertir en string et padding avec des zéros
                track_title = track_info['title']
                ext = os.path.splitext(track_info['local_path'])[1]
                new_filename = f"{track_number} - {track_title}{ext}"
                
                # Construire les chemins source et destination
                src_path = os.path.join(self.download_dir, track_info['local_path'])
                dst_path = os.path.join(destination_dir, new_filename)

                # Déplacer le fichier avec shutil.move
                if os.path.exists(src_path):
                    try:
                        shutil.move(src_path, dst_path)
                        self.logger.info(f"Fichier déplacé: {src_path} -> {dst_path}")
                    except Exception as e:
                        self.logger.error(f"Erreur lors du déplacement du fichier: {str(e)}")
                else:
                    self.logger.warning(f"Fichier source non trouvé: {src_path}")

            # 4. Nettoyer la file Slskd une fois terminé
            self.downloader.clear_completed_downloads()
            self.logger.info("File de téléchargement nettoyée")

        except Exception as e:
            self.logger.error(f"Erreur lors du traitement post-téléchargement: {str(e)}")
            self.logger.exception("Stack trace complète:")

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

        self.db.update_album_status(album_id, DownloadStatus.PENDING)

        # Et enfin les pistes
        for track in album_info['tracks']:
            if track.get('id'):
                self.db.add_track(
                    track['id'],
                    album_id,
                    track['title'],
                    track.get('position'),
                    track.get('length')
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

    def clean_filename(self, filename):
        # Retire l'extension et le numéro de piste au début
        name = os.path.splitext(filename)[0]
        name = re.sub(r'^\d+\.\s*', '', name)
        return name.lower().strip()

    def extract_part_number(self, name):
        # Cherche un numéro de partie dans le nom (ex: "Pt 1", "Part 2", etc.)
        match = re.search(r'(?:pt|part)\s*(\d+)', name.lower())
        return int(match.group(1)) if match else None

    def compare_track_names(self, file_name, track_title):
        file_clean = self.clean_filename(file_name)
        track_clean = track_title.lower().strip()
        
        # Extrait les numéros de partie
        file_part = self.extract_part_number(file_clean)
        track_part = self.extract_part_number(track_clean)
        
        # Retire la partie "Pt X" pour la comparaison principale
        file_base = re.sub(r'\s*(?:pt|part)\s*\d+.*$', '', file_clean)
        track_base = re.sub(r'\s*(?:pt|part)\s*\d+.*$', '', track_clean)
        
        # Compare d'abord les noms de base
        ratio = difflib.SequenceMatcher(None, file_base, track_base).ratio()
        base_match = ratio > 0.8
        
        # Si les noms de base correspondent et qu'il y a des numéros de partie
        if base_match and file_part is not None and track_part is not None:
            return file_part == track_part
        
        # Si pas de numéros de partie, utilise juste la correspondance de base
        return base_match

    def matches_track(self, filename, track_title):
        """Vérifie si un nom de fichier correspond à un titre de piste."""
        matches_by_content = self.compare_track_names(filename, track_title)
        self.logger.debug(f"Comparaison du fichier '{filename}' avec le titre '{track_title}'")
        
        if matches_by_content:
            self.logger.debug("Correspondance trouvée!")
            return True
            
        return False