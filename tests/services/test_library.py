import pytest
from app.services.library import LibraryService
from app.database import DownloadStatus

@pytest.fixture
def library_service(test_database):
    return LibraryService(test_database)

def test_library_albums(library_service):
    # Prépare les données de test pour l'artiste et l'album
    artist_id = "test-artist-id"
    album_id = "test-album-id"
    
    # Ajoute un artiste à la base de données
    library_service.db.add_artist(artist_id, "Test Artist")
    
    # Ajoute un album à la base de données
    library_service.db.add_album(
        album_id=album_id,
        artist_id=artist_id,
        title="Test Album",
        release_date="2023",
        cover_url="https://example.com/cover.jpg"
    )
    
    # Ajoute quelques pistes
    library_service.db.add_track(
        track_id="track1",
        album_id=album_id,
        title="Track 1",
        position="1"
    )
    library_service.db.add_track(
        track_id="track2",
        album_id=album_id,
        title="Track 2",
        position="2"
    )

    # Teste la récupération des albums
    albums = library_service.get_all_albums()
    assert len(albums) == 1
    assert albums[0]['title'] == "Test Album"
    assert albums[0]['artist_name'] == "Test Artist"
    assert albums[0]['total_tracks'] == 2

def test_get_artist_albums(library_service):
    # Prépare les données de test
    artist_id = "test-artist-id"
    
    # Ajoute un artiste à la base de données
    library_service.db.add_artist(artist_id, "Test Artist")
    
    # Ajoute deux albums pour l'artiste
    albums = [
        {
            'id': 'album1',
            'title': 'Album 1',
            'release_date': '2023'
        },
        {
            'id': 'album2',
            'title': 'Album 2',
            'release_date': '2024'
        }
    ]

    for album in albums:
        library_service.db.add_album(
            album_id=album['id'],
            artist_id=artist_id,
            title=album['title'],
            release_date=album['release_date']
        )

    # Teste la récupération des albums de l'artiste
    artist_albums = library_service.get_artist_albums(artist_id)
    assert len(artist_albums) == 2
    assert artist_albums[0]['title'] == 'Album 2'  # Le plus récent d'abord
    assert artist_albums[1]['title'] == 'Album 1'