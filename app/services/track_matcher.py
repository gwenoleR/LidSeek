import difflib
import re
from typing import List, Dict
from utils.logger import setup_logger
from .slsk_models import SlskDirectory, SlskFile

class TrackMatcher:
    """Classe responsable de la correspondance entre les pistes recherchées et trouvées."""
    
    def __init__(self, minimum_ratio: float = 0.5):
        self.minimum_ratio = minimum_ratio
        self.logger = setup_logger('track_matcher', 'track_matcher.log')

    def compare_track_names(self, name1: str, name2: str) -> float:
        """Compare deux noms de pistes et retourne leur ratio de similarité."""
        # Nettoyer les noms
        clean1 = self._clean_track_name(name1)
        clean2 = self._clean_track_name(name2)
        
        # Calculer le ratio de similarité
        ratio = difflib.SequenceMatcher(None, clean1, clean2).ratio()
        return ratio

    def _clean_track_name(self, name: str) -> str:
        """Nettoie un nom de piste pour la comparaison."""
        # Enlever l'extension
        name = name.rsplit('.', 1)[0]
        
        # Enlever les caractères spéciaux et convertir en minuscules
        name = re.sub(r'[^\w\s]', '', name.lower())
        
        # Enlever les numéros de piste au début (ex: "01 -" ou "1.")
        name = re.sub(r'^\d+[\s.-]+', '', name)
        
        return name.strip()

    def find_matching_tracks(self, wanted_tracks: List[Dict], available_files: SlskDirectory, allowed_extensions: List[str]) -> List[SlskFile]:
        """Trouve les fichiers correspondant aux pistes voulues.
        
        Args:
            wanted_tracks: Liste des pistes recherchées (depuis MusicBrainz par exemple)
            available_files: Liste des fichiers disponibles (objets SlskDirectory)
            allowed_extensions: Liste des extensions de fichier autorisées
        
        Returns:
            Liste des fichiers correspondants
        """
        matching_files: List[SlskFile] = []
        matched_tracks = set()  # Pour éviter les doublons
        
        # Filtrer d'abord par extension
        valid_files = [f for f in available_files.get_audio_files() if f.extension.lower() in [ext.lower().strip('.') for ext in allowed_extensions]]
        self.logger.debug(f"Valid files on folder {available_files.name}: {valid_files}")
        
        for track in wanted_tracks:
            track_title = track.get('title', '')
            if not track_title:
                continue
                
            best_match = None
            best_ratio = self.minimum_ratio
            
            for file in valid_files:
                # Éviter les fichiers déjà matchés
                if file in matching_files:
                    continue
                    
                ratio = self.compare_track_names(file.filename, track_title)
                if ratio > best_ratio:
                    best_ratio = ratio
                    best_match = file
            
            if best_match and best_match not in matching_files:
                self.logger.info(f"Match trouvé: '{track_title}' -> '{best_match.filename}' (ratio: {best_ratio:.2f})")
                matching_files.append(best_match)
                matched_tracks.add(track_title)
        
        # Log des pistes non trouvées
        unmatched = [t.get('title') for t in wanted_tracks if t.get('title') not in matched_tracks]
        if unmatched:
            self.logger.warning(f"Pistes non trouvées: {', '.join(unmatched)}")
            
        return matching_files