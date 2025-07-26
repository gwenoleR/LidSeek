from flask import Blueprint, request, jsonify

download_routes = Blueprint('download_routes', __name__)

def init_routes(musicbrainz_service, download_manager):
    @download_routes.route('/download/album/<album_id>', methods=['POST'])
    def queue_album_download(album_id):
        try:
            album_info = musicbrainz_service.get_album_tracks(album_id)
            artist_id = request.form.get('artist_id')
            
            # Ajouter l'album à la file de téléchargement
            download_manager.queue_album(album_id, artist_id, album_info)
            return jsonify({'status': 'success', 'message': 'Album ajouté à la file de téléchargement'})

        except Exception as e:
            return jsonify({'error': str(e)}), 500

    @download_routes.route('/cancel/album/<album_id>', methods=['POST'])
    def cancel_album_download(album_id):
        try:
            download_manager.cancel_album(album_id)
            return jsonify({'status': 'success', 'message': 'Téléchargement annulé'})
        except Exception as e:
            return jsonify({'error': str(e)}), 500

    return download_routes