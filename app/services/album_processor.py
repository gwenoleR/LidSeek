import os
from app.utils.logger import setup_logger
from typing import Dict, List
from app.database import DownloadStatus
from app.services.filesystem import FileSystemService
from app.services.download_status_tracker import DownloadStatusTracker
from app.services.tagger import TaggerService

class AlbumProcessor:
    def __init__(self, filesystem: FileSystemService, status_tracker: DownloadStatusTracker):
        self.filesystem = filesystem
        self.status_tracker = status_tracker
        self.logger = setup_logger('album_processor', 'downloads.log')

    def process_completed_album(self, album: dict) -> None:
        """Traite un album téléchargé en organisant ses fichiers."""
        self.logger.info(f"Post-download processing for {album['title']}")
        
        try:
            # Get status and tracks
            tracks = self.status_tracker.get_tracks_status(album['id'])
            if not tracks:
                self.logger.error(f"No track found for album {album['id']}")
                return

            # Create the destination folder
            year = album.get('release_date', '').split('-')[0] if album.get('release_date') else ''
            destination_dir = self.filesystem.create_album_directory(
                album['artist_name'], 
                album['title'], 
                year
            )

            # Move and rename each file
            for track_id, track_info in tracks.items():
                if track_info['status'] != DownloadStatus.COMPLETED.value or not track_info['local_path']:
                    continue

                # Build the new filename
                track_number = str(track_info.get('position', '')).zfill(2)
                track_title = track_info['title']
                ext = os.path.splitext(track_info['local_path'])[1]
                new_filename = f"{track_number} - {track_title}{ext}"

                # Move the file
                moved_path = self.filesystem.move_track_file(track_info['local_path'], destination_dir, new_filename)
                if not moved_path:
                    self.logger.error(f"Failed to move track {track_title}")
                    return
                
                # Not working?
                # # Tag the moved file
                # tags = {
                #     'title': track_title,
                #     'artist': album.get('artist_name'),
                #     'album': album.get('title'),
                #     'track': str(track_info.get('position', '')),
                #     'year': year,
                #     'albumartist': album.get('artist_name'),
                # }
                # try:
                #     # TaggerService.clear_tags(os.path.join(destination_dir, new_filename))
                #     # TaggerService.tag_file(os.path.join(destination_dir, new_filename), tags)
                # except Exception as tag_exc:
                #     self.logger.error(f"Error while tagging track {track_title}: {str(tag_exc)}")

            self.logger.info(f"Processing finished for album {album['title']}")

        except Exception as e:
            self.logger.error(f"Error processing album: {str(e)}")
            self.logger.exception("Full stack trace:")