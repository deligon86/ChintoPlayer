from typing import List, Optional
from domain.models.song import Track
from adapters.music_repository import MusicRepository


class SongManager:
    def __init__(self, repo: MusicRepository):
        self._repo = repo

    def get_all_songs(self) -> List[Track]:
        """
        Returns full library without thumbnails
        :return
        """
        return self._repo.get_all_tracks_no_blobs()

    def get_all_tracks_light(self) -> List[Track]:
        """
        Returns full library WITHOUT thumbnails.
        Use this for the main list view to save memory.
        """
        return self._repo.get_all_tracks_no_blobs()

    def get_song(self, song_id: str) -> Optional[Track]:
        """
        Fetch a single track details (e.g., for metadata editing)
        :param song_id:
        :return:
        """
        tracks = self._repo.get_tracks_by_ids([song_id])
        return tracks[0] if tracks else None

    def search(self, query: str) -> List[Track]:
        """
        Real-time search. Moved to Repository-level filtering to avoid
        loading the whole library into memory.
        """
        if not query or len(query) < 2:
            return []

        # We delegate search to the Repo to use SQL optimization
        return self._repo.search_tracks(query)

    def get_recently_added(self, limit: int = 50) -> List[Track]:
        """
        Fetches the most recently added songs directly from the DB
        :param limit
        :return:
        """
        return self._repo.get_recent_tracks(limit)

    def hydrate_thumbnail(self, track: Track) -> Optional[bytes]:
        """
        On-demand loading of a thumbnail.
        Call this when a track row actually becomes visible in the UI.
        :param track:
        :return:
        """
        if not track.thumbnail:
            track.thumbnail = self._repo.get_thumbnail_blob(track.id)
        return track.thumbnail
