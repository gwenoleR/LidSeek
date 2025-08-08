from dataclasses import dataclass
from typing import List, Optional
from datetime import datetime

@dataclass
class SlskAttribute:
    """Représente un attribut de fichier Soulseek."""
    type: str
    value: int

    @classmethod
    def from_response(cls, response: dict) -> 'SlskAttribute':
        """Crée une instance à partir d'une réponse Soulseek."""
        return cls(
            type=response['type'],
            value=response['value']
        )

    def __str__(self) -> str:
        """Retourne une représentation lisible de l'attribut."""
        return f"{self.type}: {self.value}"

@dataclass
class SlskFile:
    filename: str
    size: int
    extension: str
    attributes: List[SlskAttribute]
    speed: int
    queue_length: int
    slots_free: bool
    code: int = 1
    bit_rate: Optional[int] = None
    is_variable_bit_rate: bool = False
    length: Optional[int] = None  # Duration in seconds
    
    @property
    def size_mb(self) -> float:
        """Retourne la taille du fichier en MB."""
        return self.size / (1024 * 1024)
    
    @property
    def duration_str(self) -> str:
        """Retourne la durée formatée en MM:SS."""
        if self.length is None:
            return "N/A"
        minutes = self.length // 60
        seconds = self.length % 60
        return f"{minutes:02d}:{seconds:02d}"
    
    @classmethod
    def from_response(cls, response: dict) -> 'SlskFile':
        """Crée une instance à partir d'une réponse Soulseek."""
        attributes = [SlskAttribute.from_response(attr) for attr in response.get('attributes', [])]
        extension = response.get('extension')
        if not extension or len(extension) == 0:
            extension = response['filename'].split('.')[-1].lower() if '.' in response['filename'] else ''

        return cls(
            filename=response['filename'],
            size=response['size'],
            extension=extension,
            attributes=attributes,
            speed=response.get('speed', 0),
            queue_length=response.get('queue_length', 0),
            slots_free=response.get('slots_free', False),
            code=response.get('code', 1),
            bit_rate=response.get('bitRate'),
            is_variable_bit_rate=response.get('isVariableBitRate', False),
            length=response.get('length')
        )

    def get_dir_name(self) -> str:
        return "\\".join(self.filename.split("\\")[:-1])

    def __str__(self) -> str:
        """Retourne une représentation lisible du fichier."""
        info = f"{self.filename} ({self.size_mb:.1f}MB)"
        if self.bit_rate:
            info += f" {self.bit_rate}kbps"
        if self.length:
            info += f" {self.duration_str}"
        return info

@dataclass
class SlskDirectory:
    """Représente un dossier Soulseek avec ses fichiers."""
    name: str
    file_count: int
    files: List[SlskFile]
    
    @classmethod
    def from_response(cls, response: dict) -> 'SlskDirectory':
        """Crée une instance à partir d'une réponse Soulseek."""
        files = [SlskFile.from_response(f) for f in response.get('files', [])]
        return cls(
            name=response['name'],
            file_count=response.get('fileCount', len(files)),
            files=files
        )
    
    def filter_by_extension(self, extensions: List[str]) -> List[SlskFile]:
        """Filtre les fichiers par extension."""
        return [f for f in self.files if f.extension.lower() in [ext.lower().strip('.') for ext in extensions]]
    
    def filter_by_size(self, min_size_mb: float = None, max_size_mb: float = None) -> List[SlskFile]:
        """Filtre les fichiers par taille (en MB)."""
        files = self.files
        if min_size_mb is not None:
            files = [f for f in files if f.size_mb >= min_size_mb]
        if max_size_mb is not None:
            files = [f for f in files if f.size_mb <= max_size_mb]
        return files
    
    def get_audio_files(self) -> List[SlskFile]:
        """Retourne uniquement les fichiers audio (mp3, flac, etc.)."""
        audio_extensions = ['mp3', 'flac', 'wav', 'm4a', 'ogg', 'wma']
        return self.filter_by_extension(audio_extensions)
    
    def get_image_files(self) -> List[SlskFile]:
        """Retourne uniquement les fichiers image (jpg, png, etc.)."""
        image_extensions = ['jpg', 'jpeg', 'png', 'gif', 'bmp']
        return self.filter_by_extension(image_extensions)
    
    def __str__(self) -> str:
        """Retourne une représentation lisible du dossier."""
        audio_files = self.get_audio_files()
        total_size_mb = sum(f.size_mb for f in self.files)
        total_duration = sum(f.length or 0 for f in audio_files)
        minutes = total_duration // 60
        seconds = total_duration % 60
        
        return (f"Directory: {self.name}\n"
                f"Files: {self.file_count} ({total_size_mb:.1f}MB)\n"
                f"Audio files: {len(audio_files)} ({minutes}:{seconds:02d})")
    
    def __repr__(self) -> str:
        """Retourne une représentation détaillée du dossier."""
        return f"SlskDirectory(name='{self.name}', file_count={self.file_count}, files_count={len(self.files)})"

@dataclass
class SlskSearchResult:
    username: str
    files: List[SlskFile]
    free_upload_slots: bool
    upload_speed: int
    queue_length: int
    has_slots: bool
    
    @classmethod
    def from_response(cls, response: dict) -> 'SlskSearchResult':
        """Crée une instance à partir d'une réponse Soulseek."""
        files = [SlskFile.from_response(f) for f in response.get('files', [])]
        return cls(
            username=response['username'],
            files=files,
            free_upload_slots=response.get('slots_free', False),
            upload_speed=response.get('speed', 0),
            queue_length=response.get('queue_length', 0),
            has_slots=response.get('has_slots', False)
        )
    
    def filter_by_extension(self, extensions: List[str]) -> List[SlskFile]:
        """Filtre les fichiers par extension."""
        return [f for f in self.files if f.extension.lower() in [ext.lower().strip('.') for ext in extensions]]
    
    def filter_by_size(self, min_size_mb: float = None, max_size_mb: float = None) -> List[SlskFile]:
        """Filtre les fichiers par taille (en MB)."""
        files = self.files
        if min_size_mb is not None:
            files = [f for f in files if f.size_mb >= min_size_mb]
        if max_size_mb is not None:
            files = [f for f in files if f.size_mb <= max_size_mb]
        return files
    
    def get_best_quality_files(self) -> List[SlskFile]:
        """Retourne les fichiers avec la meilleure qualité basée sur la taille."""
        if not self.files:
            return []
            
        # Group files by name (without extension)
        grouped = {}
        for file in self.files:
            base_name = '.'.join(file.filename.split('.')[:-1])
            if base_name not in grouped:
                grouped[base_name] = []
            grouped[base_name].append(file)
        
        # For each group, select the file with the largest size
        best_files = []
        for files in grouped.values():
            best_file = max(files, key=lambda x: x.size)
            best_files.append(best_file)
            
        return best_files

    def __str__(self) -> str:
        """Retourne une représentation lisible du résultat."""
        file_count = len(self.files)
        return f"User: {self.username} ({file_count} files, Speed: {self.upload_speed}KB/s, Queue: {self.queue_length})"
    
    def __repr__(self) -> str:
        """Retourne une représentation détaillée du résultat."""
        return (f"SlskSearchResult(username='{self.username}', files_count={len(self.files)}, "
                f"free_upload_slots={self.free_upload_slots}, upload_speed={self.upload_speed}, "
                f"queue_length={self.queue_length}, has_slots={self.has_slots})")