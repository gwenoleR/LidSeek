import json
import requests

class MusicBrainzService:
    BASE_URL = "https://musicbrainz.org/ws/2"
    
    def __init__(self, user_agent, redis_client, cache_expiration):
        self.headers = {'User-Agent': user_agent}
        self.redis_client = redis_client
        self.cache_expiration = cache_expiration

    def get_artist_mbid(self, artist_name, force_refresh=False):
        cache_key = f"artist_id:{artist_name}"
        cached_id = None if force_refresh else self.redis_client.get(cache_key)
        if cached_id:
            return cached_id

        url = f"{self.BASE_URL}/artist/"
        params = {'query': f'artist:{artist_name}', 'fmt': 'json'}
        response = requests.get(url, headers=self.headers, params=params)
        response.raise_for_status()
        results = response.json()
        
        if results['artists']:
            artist_id = results['artists'][0]['id']
            self.redis_client.setex(cache_key, self.cache_expiration, artist_id)
            return artist_id
        raise ValueError("Artiste non trouvé.")

    def get_albums_for_artist(self, mbid, limit=100, force_refresh=False):
        cache_key = f"albums:{mbid}"
        cached_albums = None if force_refresh else self.redis_client.get(cache_key)
        if cached_albums:
            return json.loads(cached_albums)

        albums_dict = {}
        offset = 0

        while True:
            url = f"{self.BASE_URL}/release-group"
            params = {
                'artist': mbid,
                'type': 'album|ep',
                'fmt': 'json',
                'limit': limit,
                'offset': offset
            }
            response = requests.get(url, headers=self.headers, params=params)
            response.raise_for_status()
            data = response.json()
            release_groups = data.get('release-groups', [])
            
            if not release_groups:
                break
                
            for group in release_groups:
                secondary_types = group.get('secondary-types', [])
                if not any(t in ['Compilation', 'Soundtrack', 'Live', 'Interview', 'Demo', 'Remix'] for t in secondary_types):
                    album_id = group['id']
                    if album_id not in albums_dict:
                        albums_dict[album_id] = {
                            'id': album_id,
                            'title': group['title'],
                            'date': group.get('first-release-date'),
                            'secondary_types': secondary_types,
                            'primary_type': group.get('primary-type', 'Unknown')
                        }
                        
            if len(release_groups) < limit:
                break
            offset += limit

        albums = list(albums_dict.values())
        sorted_albums = sorted(albums, key=lambda x: x['date'] or "9999")
        
        self.redis_client.setex(cache_key, self.cache_expiration, json.dumps(sorted_albums))
        return sorted_albums

    def get_album_tracks(self, album_id, force_refresh=False):
        cache_key = f"tracks:{album_id}"
        cached_tracks = None if force_refresh else self.redis_client.get(cache_key)
        if cached_tracks:
            return json.loads(cached_tracks)

        # Obtenir d'abord les informations du release-group
        url = f"{self.BASE_URL}/release-group/{album_id}"
        params = {
            'fmt': 'json'
        }
        response = requests.get(url, headers=self.headers, params=params)
        response.raise_for_status()
        release_group_data = response.json()

        # Rechercher tous les releases de ce release-group
        url = f"{self.BASE_URL}/release"
        params = {
            'release-group': album_id,
            'fmt': 'json',
            'inc': 'recordings artist-credits'
        }
        response = requests.get(url, headers=self.headers, params=params)
        response.raise_for_status()
        releases_data = response.json()

        if not releases_data.get('releases'):
            return []

        # Prendre le release avec le plus de pistes
        release = max(releases_data['releases'], 
                     key=lambda x: sum(medium.get('track-count', 0) for medium in x.get('media', [])))

        album_info = {
            'id': album_id,
            'title': release_group_data.get('title', ''),
            'cover_url': self._get_cover_url(release['id']),
            'tracks': []
        }

        for medium in release.get('media', []):
            for track in medium.get('tracks', []):
                recording = track.get('recording', {})
                # Générer un ID unique basé sur l'album et la position si aucun ID n'est disponible
                track_id = (track.get('id') or 
                          recording.get('id') or 
                          f"{album_id}-{medium.get('position', '0')}-{track.get('number', '0')}")
                
                track_info = {
                    'id': track_id,
                    'position': track.get('number', ''),
                    'title': track.get('title', ''),
                    'length': track.get('length', 0),
                    'artists': [artist['name'] for artist in track.get('artist-credit', [])]
                }
                album_info['tracks'].append(track_info)

        # Trier les pistes par position
        album_info['tracks'].sort(key=lambda x: x['position'])
        
        self.redis_client.setex(cache_key, self.cache_expiration, json.dumps(album_info))
        return album_info

    def _get_cover_url(self, release_id):
        """Récupère l'URL de la couverture d'un album depuis Cover Art Archive."""
        try:
            response = requests.get(f"https://coverartarchive.org/release/{release_id}")
            if response.status_code == 200:
                cover_data = response.json()
                front_covers = [image for image in cover_data['images'] if image.get('front', False)]
                if front_covers:
                    return front_covers[0]['image']
        except:
            pass
        return None