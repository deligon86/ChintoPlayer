from datetime import datetime
from typing import List
from core import logger
from core.constants.events import PlaybackEngineEvent, MediaScannerEvent, LibraryEvent
from domain.models.song import Track, TrackItem
from domain.models.base import BaseItemContainer
from domain.playlist_manager import PlaylistManager
from domain.songmanager import SongManager


class LibraryManager:
    def __init__(self, repo, bus):
        self.repo = repo
        self.bus = bus

        self._songs = SongManager(repo)
        self._playlists = PlaylistManager(repo)

        self._last_play_time = {}
        self._available = False

        self.bus.subscribe(PlaybackEngineEvent.PLAYBACK_COMPLETED, self._on_track_finished)
        self.bus.subscribe(MediaScannerEvent.SCANNER_FINISHED, self._on_scan_finished)

    @property
    def library_available(self):
        return self._available

    def _on_scan_finished(self, tracks: List[Track]):
        """
        Processes the batch of tracks found by the scanner.
        :param tracks:
        """
        if not tracks:
            return

        #self.bus.publish(LibraryEvent.LIBRARY_READY, False)
        logger.info(f"[Library Manager] Adding files to library")
        # Convert Track objects to dictionaries as the repo uses the UPSERT logic
        # track_dicts = [t.__dict__ for t in tracks]
        updated_ids = [t.id for t in tracks]
        self.repo.save_tracks(tracks)

        # Trigger UI refresh
        self.bus.publish(LibraryEvent.LIBRARY_READY, True)
        self.bus.publish(LibraryEvent.LIBRARY_REFRESHED, tracks)

    def _on_track_finished(self, track_id: str):
        """
        Handles the '30-second rule' and increments stats.
        :param track_id:
        """
        now = datetime.now()

        # Prevent duplicate increments for the same song in a short window
        if track_id in self._last_play_time:
            delta = (now - self._last_play_time[track_id]).total_seconds()
            if delta < 30:
                return

        # Update Persistence
        self.repo.increment_play_count(track_id)
        self._last_play_time[track_id] = now

        # Publish specific stat update for the UI 'Plays' column
        self.bus.publish(LibraryEvent.LIBRARY_STAT_UPDATED, track_id)

    def get_albums(self):
        return self.repo.get_albums()

    def get_tracks_by_album(self, album, artist):
        return self.repo.get_tracks_by_album(album, artist)

    def get_queue_manager_context(self) -> BaseItemContainer:
        """
        Creates the 'All Songs' context for the QueueManager
        :return:
        """
        all_songs = self._songs.get_all_songs()
        items = [TrackItem(track=t) for t in all_songs]

        return BaseItemContainer(
            id="all_songs",
            name="All Songs",
            items=items
        )

    def check_library(self, refresh=False, limit=None):
        """
        Check if library is active
        :param limit:
        :param refresh: Whether to send the updated library
        :return:
        """
        library = self._songs.get_all_songs(limit)
        if library:
            self._available = True
            self.bus.publish(LibraryEvent.LIBRARY_READY, True)
            if refresh:
                self.bus.publish(LibraryEvent.LIBRARY_REFRESHED, library)
        else:
            self.bus.publish(MediaScannerEvent.SCANNER_START)

    def load_library(self, limit=None):
        return self._songs.get_all_songs(limit)

    # playlist orchestration
    def create_playlist(self, name: str, tracks: List[Track] = None):
        """
        Create a new playlist
        :param name:
        :param tracks:
        :return:
        """
        playlist = self._playlists.create_playlist(name, tracks)
        if not isinstance(playlist, str):
            self.bus.publish(LibraryEvent.PLAYLIST_CREATED, {'id': playlist.id, 'name': playlist.name})
        else:
            self.bus.publish(LibraryEvent.PLAYLIST_CREATE_ERROR, playlist)  # publish the error message

    def get_all_playlists(self):
        return self._playlists.get_playlists()
