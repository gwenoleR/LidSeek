from flask import Blueprint, request, jsonify, render_template, redirect, url_for

album_routes = Blueprint('album_routes', __name__)

def init_routes(musicbrainz_service, download_manager):
    @album_routes.route('/albums', methods=['GET'])
    def albums():
        artist_name = request.args.get('artist')
        if not artist_name:
            return jsonify({'error': 'Paramètre "artist" requis'}), 400

        try:
            mbid = musicbrainz_service.get_artist_mbid(artist_name)
            album_list = musicbrainz_service.get_albums_for_artist(mbid)

            # Récupérer le statut de téléchargement pour chaque album
            for album in album_list:
                status = download_manager.get_album_status(album['id'])
                if status:
                    album['download_status'] = status[2]
                    album['total_tracks'] = status[3]
                    album['completed_tracks'] = status[4]
                else:
                    album['download_status'] = None

            if 'text/html' in request.headers.get('Accept', ''):
                return render_template('index.html', results={
                    'artist': artist_name,
                    'mbid': mbid,
                    'albums': album_list
                })

            return jsonify({
                'artist': artist_name,
                'mbid': mbid,
                'albums': album_list
            })

        except Exception as e:
            if 'text/html' in request.headers.get('Accept', ''):
                return render_template('index.html', error=str(e))
            return jsonify({'error': str(e)}), 500

    @album_routes.route('/album/<album_id>', methods=['GET'])
    def album_details(album_id):
        try:
            album_info = musicbrainz_service.get_album_tracks(album_id)
            artist_id = request.args.get('artist_id')
            
            # Récupérer le statut de l'album
            status = download_manager.get_album_status(album_id)
            if status:
                album_info['download_status'] = status[2]
                album_info['total_tracks'] = status[3]
                album_info['completed_tracks'] = status[4]
            else:
                album_info['download_status'] = None

            # Récupérer le statut de chaque piste
            tracks_status = download_manager.get_tracks_status(album_id)
            for track in album_info['tracks']:
                if track['id'] in tracks_status:
                    track['download_status'] = tracks_status[track['id']]['status']
                    track['local_path'] = tracks_status[track['id']]['local_path']
                else:
                    track['download_status'] = None
                    track['local_path'] = None
            
            album_info['artist_id'] = artist_id

            if 'text/html' in request.headers.get('Accept', ''):
                return render_template('album.html', album=album_info)
            return jsonify(album_info)

        except Exception as e:
            error_msg = str(e)
            if 'text/html' in request.headers.get('Accept', ''):
                empty_album = {
                    'id': album_id,
                    'title': 'Erreur',
                    'tracks': [],
                    'error': error_msg
                }
                return render_template('album.html', album=empty_album)
            return jsonify({'error': error_msg}), 500

    @album_routes.route('/refresh/albums', methods=['GET'])
    def refresh_albums():
        artist_name = request.args.get('artist')
        artist_id = request.args.get('artist_id')  # Ajout du paramètre artist_id
        
        if not artist_name and not artist_id:
            return jsonify({'error': 'Paramètre "artist" ou "artist_id" requis'}), 400

        try:
            # Si on a l'ID de l'artiste, on l'utilise directement
            if artist_id:
                mbid = artist_id
            else:
                # Sinon on cherche par le nom (cas de fallback)
                mbid = musicbrainz_service.get_artist_mbid(artist_name, force_refresh=True)
            
            album_list = musicbrainz_service.get_albums_for_artist(mbid, force_refresh=True)
            return redirect(url_for('album_routes.albums', artist=artist_name))
            
        except Exception as e:
            return jsonify({'error': str(e)}), 500

    @album_routes.route('/refresh/album/<album_id>', methods=['GET'])
    def refresh_album(album_id):
        try:
            artist_id = request.args.get('artist_id')
            musicbrainz_service.get_album_tracks(album_id, force_refresh=True)
            return redirect(url_for('album_routes.album_details', album_id=album_id, artist_id=artist_id))
        except Exception as e:
            return jsonify({'error': str(e)}), 500

    @album_routes.route('/album/<album_id>/status', methods=['GET'])
    def album_status(album_id):
        try:
            # Récupérer le statut global de l'album
            status = download_manager.get_album_status(album_id)
            # Récupérer le statut détaillé des pistes
            tracks_status = download_manager.get_tracks_status(album_id)
            
            if status:
                return jsonify({
                    'status': status[2],
                    'total_tracks': status[3],
                    'completed_tracks': status[4],
                    'tracks': tracks_status
                })
            else:
                return jsonify({'error': 'Album non trouvé'}), 404

        except Exception as e:
            return jsonify({'error': str(e)}), 500

    return album_routes