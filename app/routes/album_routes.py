from flask import Blueprint, request, jsonify, render_template, redirect, url_for
from app.services.album_processor import AlbumProcessor
from app.services.filesystem import FileSystemService
from app.database import DownloadStatus
from app.config.settings import Config

album_routes = Blueprint('album_routes', __name__)

def init_routes(musicbrainz_service, download_manager):

    # Initialisation des services nécessaires pour le process
    status_tracker = download_manager.status_tracker if hasattr(download_manager, 'status_tracker') else download_manager
    filesystem = FileSystemService("/downloads", Config.FORMATTED_SONGS_DIR)
    album_processor = AlbumProcessor(filesystem, status_tracker)

    @album_routes.route('/albums', methods=['GET'])
    def albums():
        artist_name = request.args.get('artist')
        primary_types = request.args.getlist('primary_type')
        secondary_types = request.args.getlist('secondary_type')
        if not artist_name:
            return jsonify({'error': 'Paramètre "artist" requis'}), 400

        try:
            mbid = musicbrainz_service.get_artist_mbid(artist_name)
            album_list = musicbrainz_service.get_albums_for_artist(
                mbid,
                primary_types=primary_types,
                secondary_types=secondary_types
            )

            # Get download status for each album
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
            
            # Get album status
            status = download_manager.get_album_status(album_id)
            if status:
                album_info['download_status'] = status[2]
                album_info['total_tracks'] = status[3]
                album_info['completed_tracks'] = status[4]
            else:
                album_info['download_status'] = None

            # Get status for each track
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
        artist_id = request.args.get('artist_id')
        
        if not artist_name and not artist_id:
            return jsonify({'error': 'Paramètre "artist" ou "artist_id" requis'}), 400

        try:
            # If we have the artist ID, use it directly
            if artist_id:
                mbid = artist_id
            else:
                # Otherwise, search by name (fallback case)
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
            # Get global album status
            status = download_manager.get_album_status(album_id)
            # Get detailed track status
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
        

    @album_routes.route('/album/<album_id>/mark_complete', methods=['POST'])
    def mark_album_complete(album_id):
        try:
            # Récupérer les infos de l'album
            album_info = musicbrainz_service.get_album_tracks(album_id)
            tracks_status = status_tracker.get_tracks_status(album_id)
            updated = 0
            # Marquer toutes les pistes téléchargées ou existantes comme terminées
            for track_id, track_info in tracks_status.items():
                if track_info['status'] != DownloadStatus.COMPLETED.value:
                    # Si le fichier existe localement, on le considère comme terminé
                    if track_info['local_path']:
                        status_tracker.update_track_status(track_id, DownloadStatus.COMPLETED, local_path=track_info['local_path'], slsk_id=track_info.get('slsk_id'))
                        updated += 1
            # Mettre le statut de l'album à terminé
            status_tracker.update_album_status(album_id, DownloadStatus.COMPLETED)
            # Lancer le process de l'album (organisation des fichiers)
            album_processor.process_completed_album(album_info)

            # Suppression des téléchargements Slsk terminés
            downloader = getattr(download_manager, 'downloader', None)
            if downloader:
                # On récupère les fichiers Slsk associés à l'album
                files_status = downloader.get_directory_files_status(album_info['title'])
                for file in files_status:
                    if file.get('state') == 'Completed, Succeeded':
                        downloader.remove_download(file.get('username'), file.get('id'))

            return jsonify({'success': True, 'updated_tracks': updated})
        except Exception as e:
            return jsonify({'success': False, 'error': str(e)}), 500
        
    return album_routes