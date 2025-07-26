from abc import ABC, abstractmethod
from typing import Dict, List
import slskd_api
import time
import difflib
from utils.logger import setup_logger

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
    def search(self, query: str) -> Dict:
        """Effectue une recherche"""
        pass
        
    @abstractmethod
    def get_directory_content(self, username: str, directory: str) -> Dict:
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
            
    def search(self, query: str) -> Dict:
        if not self.client:
            raise ValueError("Slskd n'est pas configuré")
            
        search = self.client.searches.search_text(
            searchText=query,
            searchTimeout=5000,
            filterResponses=True,
            maximumPeerQueueLength=50,
            minimumPeerUploadSpeed=0
        )
        
        while True:
            if self.client.searches.state(search['id'])['state'] != 'InProgress':
                break
            time.sleep(1)
            
        return self.client.searches.search_responses(search['id'])
        
    def get_directory_content(self, username: str, directory: str) -> Dict:
        return self.client.users.directory(username=username, directory=directory)
        
    def start_download(self, username: str, files: List[Dict]) -> bool:
        self.logger.info(f"Démarrage du téléchargement pour {username} avec les fichiers: {files}")
        try:
            self.client.transfers.enqueue(username=username, files=files)
            return True
        except Exception as e:
            self.logger.error(f"Erreur lors du téléchargement: {str(e)}")
            return False
            
    def get_downloads_status(self) -> List[Dict]:
        return self.client.transfers.get_all_downloads()
        
    def cancel_download(self, username: str, files: List[Dict]) -> None:
        for file in files:
            self.client.transfers.cancel_download(username=username, id=file['id'])