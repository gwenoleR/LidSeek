import pytest
from app.services.download_manager import DownloadManager
from app.services.downloaders import SlskdDownloader
from app.database import DownloadStatus
from unittest.mock import Mock, MagicMock

@pytest.fixture
def mock_slskd():
    mock = Mock(spec=SlskdDownloader)
    # Configuration des attributs de base
    mock.ignored_users = []
    mock.allowed_filetypes = ["mp3", "flac"]
    mock.minimum_match_ratio = 0.5
    
    # Configuration des méthodes
    mock.search.return_value = [
        {
            'username': 'test_user',
            'files': [
                {
                    'filename': 'Track 1.mp3',
                    'size': 1000000
                }
            ]
        }
    ]
    mock.get_downloads_status.return_value = []
    mock.get_directory_content.return_value = [
        {
            'filename': 'Track 1.mp3',
            'size': 1000000
        }
    ]
    mock.start_download.return_value = True
    
    return mock

@pytest.fixture
def download_manager(test_database, mock_slskd):
    manager = DownloadManager(test_database)
    manager.configure_downloader(mock_slskd)
    return manager

def test_queue_album(download_manager):
    album_info = {
        'id': 'test-album-id',
        'title': 'Test Album',
        'artist_name': 'Test Artist',
        'tracks': [
            {'id': 'track1', 'title': 'Track 1', 'position': '1'},
            {'id': 'track2', 'title': 'Track 2', 'position': '2'}
        ]
    }

    # Test l'ajout d'un album à la file d'attente
    artist_id = 'test-artist-id'
    download_manager.queue_album(album_info['id'], artist_id, album_info)

    # Vérifie que l'album est dans la base de données
    album_status = download_manager.get_album_status(album_info['id'])
    assert album_status is not None
    assert album_status[2] == DownloadStatus.PENDING.value  # Vérifie le statut

def test_start_download(download_manager, mock_slskd):
    album_info = {
        'id': 'test-album-id',
        'title': 'Test Album',
        'artist_name': 'Test Artist',
        'tracks': [{'id': 'track1', 'title': 'Track 1', 'position': '1'}]
    }
    
    # Ajoute d'abord l'album à la file d'attente
    artist_id = 'test-artist-id'
    download_manager.queue_album(album_info['id'], artist_id, album_info)
    
    # Configure le mock pour simuler un téléchargement réussi
    mock_slskd.search.return_value = [
        {
            'username': 'test_user',
            'files': [
                {
                    'filename': 'Track 1.mp3',
                    'size': 1000000
                }
            ]
        }
    ]
    mock_slskd.get_directory_content.return_value = [
        {
            'filename': 'Track 1.mp3',
            'size': 1000000
        }
    ]
    mock_slskd.start_download.return_value = True
    
    # Simule le démarrage du téléchargement
    result = download_manager._search_and_download(album_info)
    
    # Vérifie que le downloader a été appelé correctement
    mock_slskd.search.assert_called_once()
    assert result is True  # Vérifie que le téléchargement a réussi