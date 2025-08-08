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

    def get_albums_for_artist(self, mbid, limit=100, force_refresh=False, primary_types=None, secondary_types=None):
        # Build a unique cache key based on filters
        cache_key = f"albums:{mbid}:{'-'.join(primary_types or ['all'])}:{'-'.join(secondary_types or ['all'])}"
        cached_albums = None if force_refresh else self.redis_client.get(cache_key)
        if cached_albums:
            return json.loads(cached_albums)

        albums_dict = {}
        offset = 0

        # Prepare the 'type' parameter for the MusicBrainz API
        type_param = None
        if primary_types:
            # 'type' accepts a | separated list
            type_param = '|'.join([t for t in primary_types if t != 'other'])
        if not type_param:
            type_param = 'album|ep'

        while True:
            url = f"{self.BASE_URL}/release-group"
            params = {
                'artist': mbid,
                'fmt': 'json',
                'limit': limit,
                'offset': offset
            }
            if type_param:
                params['type'] = type_param
            response = requests.get(url, headers=self.headers, params=params)
            response.raise_for_status()
            data = response.json()
            release_groups = data.get('release-groups', [])
            if not release_groups:
                break
            for group in release_groups:
                secondary_types_group = [t.lower() for t in group.get('secondary-types', [])]
                primary_type_group = group.get('primary-type', 'Unknown').lower()
                # Filter primary_type 'other'
                if primary_types and 'other' in primary_types:
                    if primary_type_group in ['album', 'ep', 'single', 'broadcast']:
                        continue
                # Secondary filtering
                if secondary_types is not None:
                    if len(secondary_types) == 0:
                        # If no secondary_type selected, only keep those without secondary type
                        if len(secondary_types_group) > 0:
                            continue
                    else:
                        if not any(st in secondary_types_group for st in [s.lower() for s in secondary_types]):
                            continue
                album_id = group['id']
                if album_id not in albums_dict:
                    albums_dict[album_id] = {
                        'id': album_id,
                        'title': group['title'],
                        'date': group.get('first-release-date'),
                        'secondary_types': group.get('secondary-types', []),
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

        # Get release-group info first
        url = f"{self.BASE_URL}/release-group/{album_id}"
        params = {
            'fmt': 'json',
            'inc': 'artist-credits'  # Include artist credits
        }
        response = requests.get(url, headers=self.headers, params=params)
        response.raise_for_status()
        release_group_data = response.json()

        # Search all releases for this release-group
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

        releases = releases_data['releases']
        # Priority: CD high > CD > high > others
        def is_cd_release(release):
            for medium in release.get('media', []):
                fmt = medium.get('format')
                if fmt and fmt.upper() == 'CD':
                    return True
            return False
       
        high_quality_cd_releases = [r for r in releases if r.get('quality') == 'high' and is_cd_release(r)]
        cd_releases = [r for r in releases if is_cd_release(r)]
        high_quality_releases = [r for r in releases if r.get('quality') == 'high']
        if high_quality_cd_releases:
            releases_to_consider = high_quality_cd_releases
        elif cd_releases:
            releases_to_consider = cd_releases
        elif high_quality_releases:
            releases_to_consider = high_quality_releases
        else:
            releases_to_consider = releases

        # Only keep releases in CD or Digital Media format, and without special edition
        def is_standard_release(release):
            # Accepted formats
            valid_formats = {"CD", "DIGITAL MEDIA"}
            # Keywords to exclude in the title
            exclude_keywords = [
                "deluxe", "extended", "remaster", "bonus", "special", "anniversary", "edition", "expanded", "collector", "reissue", "superior", "definitive", "ultimate", "tour", "live"
            ]
            # Check format
            has_valid_format = any(
                (medium.get('format') or '').strip().upper() in valid_formats
                for medium in release.get('media', [])
            )
            if not has_valid_format:
                return False
            # Check keywords in the title
            title = release.get('title', '').lower()
            if any(kw in title for kw in exclude_keywords):
                return False
            # Check secondary-types
            for t in release.get('secondary-types', []):
                if any(kw in t.lower() for kw in exclude_keywords):
                    return False
            return True

        standard_releases = [r for r in releases if is_standard_release(r)]
        if standard_releases:
            # Sort by quality: high > normal > low > None
            def quality_sort_key(r):
                q = r.get('quality')
                if q == 'high':
                    return 0
                elif q == 'normal':
                    return 1
                elif q == 'low':
                    return 2
                return 3
            standard_releases.sort(key=quality_sort_key)
            releases_to_consider = standard_releases
        else:
            releases_to_consider = releases  # fallback if nothing found

        # Take the first release from the sorted list
        release = releases_to_consider[0]

        album_info = {
            'id': album_id,
            'title': release_group_data.get('title', ''),
            'cover_url': self._get_cover_url(release['id']),
            'artist_name': release_group_data.get('artist-credit', [{}])[0].get('name', 'Artiste Inconnu'),
            'release_date': release_group_data.get('first-release-date'),
            'tracks': []
        }

        for medium in release.get('media', []):
            disc_number = medium.get('position', 1)
            if disc_number != 1:
                continue  # Only take CD1
            for track in medium.get('tracks', []):
                recording = track.get('recording', {})
                track_id = (
                    track.get('id') or 
                    recording.get('id') or 
                    f"{album_id}-{disc_number}-{track.get('number', '0')}"
                )
                track_info = {
                    'id': track_id,
                    'disc_number': disc_number,
                    'position': track.get('number', ''),
                    'title': track.get('title', ''),
                    'length': track.get('length', 0),
                    'artists': [artist['name'] for artist in track.get('artist-credit', [])]
                }
                album_info['tracks'].append(track_info)

        # Sort tracks by track number only (CD1 only)
        def track_sort_key(x):
            try:
                pos = int(x['position'])
            except (ValueError, TypeError):
                pos = 0
            return pos
        album_info['tracks'].sort(key=track_sort_key)
        
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