from flask import Blueprint, render_template, jsonify, request

library_routes = Blueprint('library_routes', __name__)

def init_routes(library_service):
    @library_routes.route('/library', methods=['GET'])
    def library():
        try:
            albums = library_service.get_all_albums()
            # Regrouper les albums par artiste
            artists_dict = {}
            for album in albums:
                artist_id = album['artist_id']
                artist_name = album['artist_name']
                if artist_id not in artists_dict:
                    artists_dict[artist_id] = {
                        'id': artist_id,
                        'name': artist_name,
                        'albums': []
                    }
                artists_dict[artist_id]['albums'].append(album)
            artists = list(artists_dict.values())
            if 'text/html' in request.headers.get('Accept', ''):
                return render_template('library.html', artists=artists)
            return jsonify(artists)
        except Exception as e:
            if 'text/html' in request.headers.get('Accept', ''):
                return render_template('library.html', error=str(e))
            return jsonify({'error': str(e)}), 500

    @library_routes.route('/library/artist/<artist_id>', methods=['GET'])
    def artist_library(artist_id):
        try:
            albums = library_service.get_artist_albums(artist_id)
            
            if 'text/html' in request.headers.get('Accept', ''):
                return render_template('library.html', albums=albums, artist_id=artist_id)
            return jsonify(albums)
        except Exception as e:
            if 'text/html' in request.headers.get('Accept', ''):
                return render_template('library.html', error=str(e))
            return jsonify({'error': str(e)}), 500

    return library_routes