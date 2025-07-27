import pytest
import responses
import json
from app.services.musicbrainz import MusicBrainzService

@pytest.fixture
def mock_redis(mocker):
    redis_mock = mocker.Mock()
    redis_mock.get.return_value = None
    return redis_mock

@pytest.fixture
def music_brainz_service(mock_redis):
    return MusicBrainzService(
        user_agent="TestApp/1.0 (test@example.com)",
        redis_client=mock_redis,
        cache_expiration=3600
    )

@responses.activate
def test_get_artist_mbid(music_brainz_service):
    # Configuration du mock pour la requête API
    artist_name = "Tash Sultana"
    expected_id = "a93ff590-4f73-4c19-8371-f1df572e0f51"
    responses.add(
        responses.GET,
        f"{MusicBrainzService.BASE_URL}/artist/",
        json={
            "artists": [{
                "id": expected_id,
                "name": artist_name
            }]
        },
        status=200
    )

    # Test de la fonction
    artist_id = music_brainz_service.get_artist_mbid(artist_name)
    assert artist_id == expected_id

@responses.activate
def test_get_albums_for_artist(music_brainz_service):
    # Configuration du mock pour la requête API
    artist_id = "test-artist-id"
    responses.add(
        responses.GET,
        f"{MusicBrainzService.BASE_URL}/release-group",
        json={
            "release-groups": [
                {
                    "id": "album1",
                    "title": "Album 1",
                    "first-release-date": "2020",
                    "primary-type": "Album"
                },
                {
                    "id": "album2",
                    "title": "Album 2",
                    "first-release-date": "2021",
                    "primary-type": "Album"
                },
                {
                    "id": "Unknown",
                    "title": "Not an album",
                    "first-release-date": "2021",
                    "primary-type": "Album",
                    "secondary-types": ["Compilation"]
                }
            ]
        },
        status=200
    )

    # Test de la fonction
    albums = music_brainz_service.get_albums_for_artist(artist_id)
    assert len(albums) == 2
    assert albums[0]["title"] == "Album 1"
    assert albums[1]["title"] == "Album 2"

@responses.activate
def test_get_album_tracks(music_brainz_service):
    album_id = "test-album-id"
    release_id = "test-release-id"
    
    # Mock pour les informations du release-group
    responses.add(
        responses.GET,
        f"{MusicBrainzService.BASE_URL}/release-group/{album_id}",
        json={
            "id": album_id,
            "title": "Test Album",
            "artist-credit": [{"name": "Test Artist"}]
        },
        status=200
    )
    
    # Mock pour la recherche des releases
    responses.add(
        responses.GET,
        f"{MusicBrainzService.BASE_URL}/release",
        json={
            "releases": [{
                "id": release_id,
                "media": [{
                    "tracks": [
                        {
                            "id": "track1",
                            "number": "1",
                            "title": "Track 1",
                            "length": 180000
                        },
                        {
                            "id": "track2",
                            "number": "2",
                            "title": "Track 2",
                            "length": 200000
                        }
                    ]
                }]
            }]
        },
        status=200
    )
    
    # Mock pour la couverture d'album
    responses.add(
        responses.GET,
        f"https://coverartarchive.org/release/{release_id}",
        json={
            "images": [
                {
                    "front": True,
                    "image": "https://example.com/cover.jpg"
                }
            ]
        },
        status=200
    )

    # Test de la fonction
    album_info = music_brainz_service.get_album_tracks(album_id)
    assert album_info["title"] == "Test Album"
    assert len(album_info["tracks"]) == 2
    assert album_info["tracks"][0]["title"] == "Track 1"
    assert album_info["tracks"][1]["title"] == "Track 2"
    assert album_info["cover_url"] == "https://example.com/cover.jpg"

def test_redis_caching(music_brainz_service, mock_redis):
    # Test du cache Redis pour get_artist_mbid
    cached_artist_id = "cached-artist-id"
    mock_redis.get.return_value = cached_artist_id
    
    artist_id = music_brainz_service.get_artist_mbid("Test Artist")
    assert artist_id == cached_artist_id
    mock_redis.get.assert_called_once()