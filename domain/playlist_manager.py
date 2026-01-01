import uuid
from typing import List, Optional
from datetime import datetime
from domain.models.playlist import Playlist
from domain.models.song import TrackItem, Track
from adapters.music_repository import MusicRepository


class PlaylistManager:
    def __init__(self, repo: MusicRepository):
        self._repo = repo

    def create_playlist(self, name: str, tracks: List[Track] = None) -> Playlist:
        """
        Creates a new persistent playlist with unique ID.
        :param name:
        :param tracks:
        :return:
        """
        playlist_id = str(uuid.uuid4())
        created_at = datetime.now()

        # Wrap tracks in TrackItem with metadata
        items = [TrackItem(track=t, added_at=created_at) for t in (tracks or [])]

        # 1. Save Header
        self._repo.save_playlist_metadata(playlist_id, name)

        # 2. Save Items (if any)
        if items:
            self._repo.add_tracks_to_playlist(playlist_id, items)

        return Playlist(
            id=playlist_id,
            name=name,
            items=items,
            created_at=created_at
        )

    def get_playlist(self, playlist_id: str, light: bool = True) -> Playlist:
        """
        Reconstructs the Playlist.
        :param playlist_id:
        :param light: If True, uses the optimized fetch without thumbnails.
        """
        name = self._repo.get_playlist_name(playlist_id)

        # 'light' pattern to keep UI snappy
        if light:
            items = self._repo.get_tracks_by_container_light(playlist_id)
        else:
            items = self._repo.get_tracks_by_container(playlist_id)

        return Playlist(id=playlist_id, name=name, items=items)

    def add_track_to_playlist(self, playlist_id: str, track: Track):
        """
        Adds a track to the end of the playlist.
        :param playlist_id:
        :param track:
        :return:
        """
        item = TrackItem(track=track, added_at=datetime.now())
        self._repo.add_tracks_to_playlist(playlist_id, [item])

    def remove_track_from_playlist(self, playlist_id: str, track_id: str, position: Optional[int] = None):
        """
        Removes a track.
        SUGGESTION: Use 'position' to differentiate if the same track is in the playlist twice.
        :param playlist_id:
        :param track_id:
        :param position:
        :return:
        """
        self._repo.remove_track_from_container(playlist_id, track_id, position)
