import os
import json
import redis
import requests
from flask import Flask, request, jsonify, render_template
from dotenv import load_dotenv
from database import Database, DownloadStatus

load_dotenv()

class MusicBrainzFetcher:
    BASE_URL = "https://musicbrainz.org/ws/2"
    
    def __init__(self, user_agent, redis_client, cache_expiration):
        self.headers = {'User-Agent': user_agent}
        self.redis_client = redis_client
        self.cache_expiration = cache_expiration

    def get_artist_mbid(self, artist_name):
        cache_key = f"artist_id:{artist_name}"
        cached_id = self.redis_client.get(cache_key)
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

    def get_albums_for_artist(self, mbid, limit=100):
        cache_key = f"albums:{mbid}"
        cached_albums = self.redis_client.get(cache_key)
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

    def get_album_tracks(self, album_id):
        cache_key = f"tracks:{album_id}"
        cached_tracks = self.redis_client.get(cache_key)
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

        # Récupérer la couverture depuis Cover Art Archive
        cover_url = None
        try:
            cover_response = requests.get(f"https://coverartarchive.org/release/{release['id']}")
            if cover_response.status_code == 200:
                cover_data = cover_response.json()
                front_covers = [image for image in cover_data['images'] if image.get('front', False)]
                if front_covers:
                    cover_url = front_covers[0]['image']
        except:
            pass

        album_info = {
            'id': album_id,
            'title': release_group_data.get('title', ''),
            'cover_url': cover_url,
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

USER_AGENT = f"{os.getenv('USER_AGENT_NAME')}/{os.getenv('USER_AGENT_VERSION')} ({os.getenv('USER_AGENT_EMAIL')})"
CACHE_EXPIRATION = 24 * 60 * 60  # 24 heures en secondes

app = Flask(__name__)
redis_client = redis.Redis(host='redis', port=6379, decode_responses=True)
mb_fetcher = MusicBrainzFetcher(USER_AGENT, redis_client, CACHE_EXPIRATION)
db = Database()

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/albums', methods=['GET'])
def albums():
    artist_name = request.args.get('artist')
    if not artist_name:
        return jsonify({'error': 'Paramètre "artist" requis'}), 400

    try:
        mbid = mb_fetcher.get_artist_mbid(artist_name)
        album_list = mb_fetcher.get_albums_for_artist(mbid)

        # Ajouter l'artiste à la base de données
        db.add_artist(mbid, artist_name)

        # Récupérer le statut de téléchargement pour chaque album
        for album in album_list:
            status = db.get_album_status(album['id'])
            if status:
                album['download_status'] = status[2]  # status from db
                album['total_tracks'] = status[3]
                album['completed_tracks'] = status[4]
            else:
                album['download_status'] = None

        if 'text/html' in request.headers.get('Accept', ''):
            return render_template('index.html', results={'artist': artist_name, 'mbid': mbid, 'albums': album_list})

        return jsonify({
            'artist': artist_name,
            'mbid': mbid,
            'albums': album_list
        })

    except Exception as e:
        if 'text/html' in request.headers.get('Accept', ''):
            return render_template('index.html', error=str(e))
        return jsonify({'error': str(e)}), 500

@app.route('/album/<album_id>', methods=['GET'])
def album_details(album_id):
    try:
        album_info = mb_fetcher.get_album_tracks(album_id)
        artist_id = request.args.get('artist_id')
        
        # Récupérer le statut de l'album
        status = db.get_album_status(album_id)
        if status:
            album_info['download_status'] = status[2]
            album_info['total_tracks'] = status[3]
            album_info['completed_tracks'] = status[4]
        else:
            album_info['download_status'] = None

        # Récupérer le statut de chaque piste
        tracks_status = db.get_tracks_status(album_id)
        for track in album_info['tracks']:
            if track['id'] in tracks_status:
                track['download_status'] = tracks_status[track['id']]['status']
                track['local_path'] = tracks_status[track['id']]['local_path']
            else:
                track['download_status'] = None
                track['local_path'] = None
            
        album_info['artist_id'] = artist_id
        album_info['id'] = album_id

        if 'text/html' in request.headers.get('Accept', ''):
            return render_template('album.html', album=album_info)
        return jsonify(album_info)

    except Exception as e:
        error_msg = str(e)
        if 'text/html' in request.headers.get('Accept', ''):
            # Créer un album vide avec juste l'erreur pour le template
            empty_album = {
                'id': album_id,
                'title': 'Erreur',
                'tracks': [],
                'error': error_msg
            }
            return render_template('album.html', album=empty_album)
        return jsonify({'error': error_msg}), 500

@app.route('/download/album/<album_id>', methods=['POST'])
def queue_album_download(album_id):
    try:
        album_info = mb_fetcher.get_album_tracks(album_id)
        
        # Ajouter l'album à la file de téléchargement
        db.add_album(
            album_id,
            request.form.get('artist_id'),
            album_info['title'],
            request.form.get('release_date'),
            album_info.get('cover_url')
        )

        # Ajouter toutes les pistes
        for track in album_info['tracks']:
            if track.get('id'):  # Vérifier que la piste a un ID valide
                db.add_track(
                    track['id'],
                    album_id,
                    track['title'],
                    track['position'],
                    track['length']
                )
            else:
                # Si une piste n'a pas d'ID, on log l'erreur mais on continue
                print(f"Warning: Track {track['title']} has no valid ID")

        return jsonify({'status': 'success', 'message': 'Album ajouté à la file de téléchargement'})

    except Exception as e:
        return jsonify({'error': str(e)}), 500

if __name__ == "__main__":
    app.run(host='0.0.0.0', port=8081)
