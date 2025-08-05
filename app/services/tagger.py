import music_tag
from typing import Optional, Dict

class TaggerService:
    @staticmethod
    def tag_file(
        file_path: str,
        tags: Dict[str, Optional[str]]
    ) -> None:
        """
        Tag a music file with the provided metadata using music-tag.
        tags: dict with keys like 'title', 'artist', 'album', 'track', 'disc', 'year', etc.
        """
        f = music_tag.load_file(file_path)
        if 'title' in tags and tags['title']:
            f['title'] = tags['title']
        if 'artist' in tags and tags['artist']:
            f['artist'] = tags['artist']
        if 'album' in tags and tags['album']:
            f['album'] = tags['album']
        if 'track' in tags and tags['track']:
            f['tracknumber'] = tags['track']
        if 'disc' in tags and tags['disc']:
            f['discnumber'] = tags['disc']
        if 'year' in tags and tags['year']:
            f['year'] = tags['year']
        if 'albumartist' in tags and tags['albumartist']:
            f['albumartist'] = tags['albumartist']
        # Ajoute d'autres tags si besoin
        f.save()

    @staticmethod
    def clear_tags(file_path: str) -> None:
        """
        Supprime tous les tags d'un fichier audio en utilisant music-tag.
        """
        f = music_tag.load_file(file_path)
        f.clear()
        f.save()
