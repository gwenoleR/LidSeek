from abc import ABC, abstractmethod
from typing import Dict, List, Union
import slskd_api
import time
import difflib
from utils.logger import setup_logger
from enum import Enum
import os
from typing import List, Dict, Optional
from .slsk_models import SlskDirectory, SlskFile, SlskSearchResult

class SlskdFileState(Enum):
    """États possibles d'un fichier dans Slskd"""
    REQUESTED = "Requested"
    QUEUED = "Queued"
    IN_PROGRESS = "InProgress"
    COMPLETED = "Completed, Succeeded"
    COMPLETED_ERRORED = "Completed, Errored"
    COMPLETED_CANCELLED = "Completed, Cancelled"
    COMPLETED_TIMEOUT = "Completed, TimedOut"

    @classmethod
    def is_completed_with_error(cls, state: str) -> bool:
        """Vérifie si l'état est un état d'erreur."""
        return state in [
            cls.COMPLETED_ERRORED.value,
            cls.COMPLETED_CANCELLED.value,
            cls.COMPLETED_TIMEOUT.value
        ]

    @classmethod
    def is_in_progress(cls, state: str) -> bool:
        """Vérifie si l'état est un état en cours."""
        return state in [
            cls.REQUESTED.value,
            cls.QUEUED.value,
            cls.IN_PROGRESS.value
        ]

class Downloader(ABC):
    """Interface abstraite pour les téléchargeurs"""
    
    def __init__(self):
        self.logger = setup_logger('downloader', 'downloads.log')
        self.minimum_match_ratio = 0.5
        self.allowed_filetypes = ["mp3", "flac"]
        self.ignored_users = []
        
    @abstractmethod
    def configure(self, **kwargs):
        """Configure le téléchargeur avec les paramètres nécessaires"""
        pass
        
    @abstractmethod
    def search(self, query: str) -> List[Dict]:
        """Effectue une recherche"""
        pass
        
    @abstractmethod
    def get_directory_content(self, username: str, directory: str) -> List[Dict]:
        """Récupère le contenu d'un répertoire"""
        pass
        
    @abstractmethod
    def start_download(self, username: str, files: List[Dict]) -> bool:
        """Démarre un téléchargement"""
        pass
        
    @abstractmethod
    def get_downloads_status(self) -> List[Dict]:
        """Récupère le statut des téléchargements en cours"""
        pass
        
    @abstractmethod
    def cancel_download(self, username: str, files: List[Dict]) -> None:
        """Annule un téléchargement"""
        pass

class SlskdDownloader(Downloader):
    """Implémentation de Downloader pour Slskd"""
    
    def __init__(self):
        super().__init__()
        self.client = None
        self.logger = setup_logger('slskd_downloader', 'downloads.log')
        self.ignored_users = []
        self.allowed_filetypes = ["mp3", "flac"]
        self.minimum_match_ratio = 0.5
        
    def configure(self, host_url: str, api_key: str, url_base: str = '/'):
        try:
            self.client = slskd_api.SlskdClient(
                host=host_url,
                api_key=api_key,
                url_base=url_base
            )
            self.logger.info(f"Slskd configuré avec succès sur {host_url}")
        except Exception as e:
            self.logger.error(f"Erreur lors de la configuration de Slskd: {str(e)}")
            raise
            
    def search(self, query: str) -> List[SlskSearchResult]:
        """Effectue une recherche.
        
        Args:
            query: Le texte à rechercher
            
        Returns:
            Liste des résultats de recherche sous forme d'objets SlskSearchResult
        """
        if not self.client:
            raise ValueError("Slskd n'est pas configuré")
            
        search = self.client.searches.search_text(
            searchText=query,
            searchTimeout=5000,
            filterResponses=True,
            maximumPeerQueueLength=50,
            minimumPeerUploadSpeed=0,
            minimumResponseFileCount=1,
            responseLimit=10
        )
        
        # Attendre la fin de la recherche
        while True:
            search_state = self.client.searches.state(search['id'])
            if search_state['state'] != 'InProgress':
                break
            time.sleep(1)
            
        # Convertir les résultats en objets SlskSearchResult
        raw_results = self.client.searches.search_responses(search['id'])
        return [SlskSearchResult.from_response(result) for result in raw_results]
        
    def get_directory_content(self, username: str, directory: str) -> SlskDirectory:
        """Récupère le contenu d'un répertoire.
        
        Returns:
            Une liste de fichiers convertis en objets SlskFile
        """
        self.logger.debug(f"Recherche dans le dossier \"{directory}\" pour le user: {username}")
        response = self.client.users.directory(username=username, directory=directory)
        if not isinstance(response, list):
            self.logger.warning(f"Réponse inattendue de directory(): {type(response)}")
            return []
        if(len(response) == 0):
            return []
        return SlskDirectory.from_response(response[0])

    def start_download(self, username: str, directory: str, files: List[SlskFile]) -> bool:
        """Démarre le téléchargement des fichiers.
        
        Args:
            username: Nom de l'utilisateur source
            files: Liste des fichiers à télécharger (objets SlskFile)
        """
        self.logger.info(f"Démarrage du téléchargement de {len(files)} fichiers de {username}")
        try:
            # Convertir les SlskFile en dictionnaires pour l'API
            files_data = [{'filename': f"{os.path.normpath(directory)}\\{f.filename}", 'size': f.size} for f in files]
            return self.client.transfers.enqueue(username=username, files=files_data)
        except Exception as e:
            self.logger.error(f"Erreur lors du téléchargement: {str(e)}")
            return False
            
    def get_downloads_status(self) -> List[Dict]:
        """Récupère l'état de tous les téléchargements.
        
        Returns:
            Liste des téléchargements avec leurs états actuels.
        """
        return self.client.transfers.get_all_downloads()
        
    def cancel_download(self, username: str, id: str) -> bool:
        """Annule un téléchargement spécifique.
        
        Args:
            username: Nom de l'utilisateur source
            id: Identifiant du téléchargement
        """
        try:
            return self.client.transfers.cancel_download(username=username, id=id)
        except Exception as e:
            self.logger.error(f"Erreur lors de l'annulation: {str(e)}")
            return False
    
    def remove_download(self, username: str, id: str) -> bool:
        """Supprime un téléchargement spécifique.
        
        Args:
            username: Nom de l'utilisateur source
            id: Identifiant du téléchargement
        """
        try:
            return self.client.transfers.cancel_download(username=username, id=id, remove=True)
        except Exception as e:
            self.logger.error(f"Erreur lors de la suppression: {str(e)}")
            return False
            
    def clear_completed_downloads(self) -> bool:
        """Nettoie tous les téléchargements terminés de la file.
        
        Returns:
            bool: True si l'opération a réussi, False sinon
        """
        try:
            return self.client.transfers.remove_completed_downloads()
        except Exception as e:
            self.logger.error(f"Erreur lors du nettoyage des téléchargements terminés: {str(e)}")
            return False
            
    def _get_download_by_directory(self, directory_name: str) -> Dict:
        """Trouve un téléchargement par son nom de dossier.
        
        Args:
            directory_name: Le nom du dossier à chercher
            
        Returns:
            Un tuple (download_info, directory_info) ou (None, None) si non trouvé
        """
        downloads = self.get_downloads_status()
        for download in downloads:
            for directory in download.get('directories', []):
                if directory.get('directory') == directory_name:
                    return download, directory
        return None, None
        
    def get_directory_files_status(self, directory_name: str) -> List[Dict]:
        """Récupère le statut de tous les fichiers d'un répertoire.
        
        Args:
            directory_name: Le nom du dossier à chercher (dernière partie du chemin)
            
        Returns:
            Liste des fichiers avec leur statut, vide si non trouvé
        """
        downloads = self.get_downloads_status()
        self.logger.info(f"Recherche du dossier contenant '{directory_name}' dans les téléchargements")
        self.logger.info(f"Nombre de téléchargements actifs: {len(downloads)}")
        
        # Nettoyer le nom recherché
        clean_search = ''.join(c.lower() for c in directory_name if c.isalnum())
        self.logger.info(f"Nom nettoyé pour la recherche: '{clean_search}'")
        
        for download in downloads:
            self.logger.info(f"Téléchargement de {download.get('username', 'unknown')}:")
            for directory in download.get('directories', []):
                dir_path = directory.get('directory', '')
                self.logger.info(f"  - Dossier trouvé: '{dir_path}'")
                
                # Nettoyer le nom du dossier cible pour la comparaison
                clean_dir = ''.join(c.lower() for c in dir_path if c.isalnum())
                self.logger.info(f"  - Nom nettoyé du dossier: '{clean_dir}'")
                
                # Vérifier si le nom recherché est dans le nom du dossier
                if clean_search in clean_dir:
                    self.logger.info(f"  => Correspondance trouvée! '{dir_path}' contient '{directory_name}'")
                    return directory.get('files', [])
                        
        self.logger.warning(f"Aucun dossier trouvé contenant '{directory_name}'")
        return []