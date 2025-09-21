from flask import Blueprint, request, jsonify

download_routes = Blueprint('download_routes', __name__)

def init_routes(musicbrainz_service, download_manager):
    @download_routes.route('/download/album/<album_id>', methods=['POST'])
    def queue_album_download(album_id):
        try:
            album_info = musicbrainz_service.get_album_tracks(album_id)
            artist_id = request.form.get('artist_id')
            
            # Add album to download queue
            download_manager.queue_album(album_id, artist_id, album_info)
            
            # Immediately start the download process
            download_manager.process_pending_downloads()
            
            return jsonify({'status': 'success', 'message': 'Album ajouté à la file de téléchargement'})

        except Exception as e:
            print(f"Error on queue download")
            return jsonify({'error': str(e)}), 500

    @download_routes.route('/cancel/album/<album_id>', methods=['POST'])
    def cancel_album_download(album_id):
        try:
            download_manager.cancel_album(album_id)
            return jsonify({'status': 'success', 'message': 'Téléchargement annulé'})
        except Exception as e:
            return jsonify({'error': str(e)}), 500

    @download_routes.route('/retry/album/<album_id>', methods=['POST'])
    def retry_album_download(album_id):
        try:
            album_info = musicbrainz_service.get_album_tracks(album_id)
            artist_id = request.form.get('artist_id')

            

            # Re-add album to download queue
            download_manager.queue_album(album_id, artist_id, album_info)
            download_manager.process_pending_downloads()
            return jsonify({'status': 'success', 'message': 'Nouvelle tentative de téléchargement lancée'})
        except Exception as e:
            return jsonify({'error': str(e)}), 500

    return download_routes