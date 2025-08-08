import threading
import time
from app.services.download_manager import DownloadManager
from app.utils.logger import setup_logger

class BackgroundTaskManager:
    def __init__(self):
        self.threads = []
        self.stop_event = threading.Event()
        self.processing_lock = threading.Lock()
        self.logger = setup_logger('background_tasks', 'background_tasks.log')

    def start_download_monitor(self, download_manager: DownloadManager, interval=5):
        """Démarre la surveillance des téléchargements en arrière-plan."""
        def monitor_downloads():
            self.logger.info("Starting download monitoring")
            while not self.stop_event.is_set():
                try:
                    # Utiliser un verrou pour éviter les vérifications simultanées
                    if self.processing_lock.acquire(blocking=False):
                        try:
                            # Vérifier uniquement les albums en cours de téléchargement
                            downloading_albums = download_manager.status_tracker.get_downloading_albums()
                            if downloading_albums:
                                self.logger.info(f"Checking {len(downloading_albums)} active downloads")
                                for album in downloading_albums:
                                    download_manager._check_download_status(album)
                            else:
                                self.logger.debug("No active downloads to check")
                        finally:
                            self.processing_lock.release()
                except Exception as e:
                    self.logger.error(f"Error during download monitoring: {str(e)}")
                    self.logger.exception(e)
                time.sleep(interval)

        thread = threading.Thread(target=monitor_downloads, daemon=True)
        thread.start()
        self.threads.append(thread)
        self.logger.info("Download monitoring thread started")

    def stop_all(self):
        """Arrête toutes les tâches d'arrière-plan."""
        self.logger.info("Stopping background tasks...")
        self.stop_event.set()
        
        for thread in self.threads:
            thread.join()
        
        self.threads.clear()
        self.logger.info("All tasks stopped")