import threading
from typing import List

from core.constants.events import LibraryEvent
from core.event import Event
from domain.models.song import TrackItem
from kivymd_interface.helpers import clean_string


class PlaylistViewModel:

    playlist_create_event = Event(dict)  # this will emit the payload
    playlist_create_error_event = Event(str)
    playlists_load_event = Event(list)
    playlist_tracks_data = Event(list)

    def __init__(self, context):
        """
        :param context: core context
        """
        self._context = context
        self._context.get('bus').subscribe(LibraryEvent.PLAYLIST_CREATED, self.playlist_created_handle)
        self._context.get('bus').subscribe(LibraryEvent.PLAYLIST_CREATE_ERROR, self.playlist_create_error_handle)

        self.active_playlist = None

    def create_playlist(self, playlist_dialog_container):
        """
        :param playlist_dialog_container: PlaylistCreateDialogContainer
        :return:
        """
        self._context.get('library').create_playlist(clean_string(playlist_dialog_container.name))
        playlist_dialog_container.clear_field()

    def playlist_created_handle(self, payload: dict):
        """
        When playlist has been created successfully
        :param payload: Dict {'id': playlist id, 'name': playlist name}
        :return:
        """
        self.playlist_create_event.emit(payload)

    def playlist_create_error_handle(self, error):
        """
        :param error:
        :return:
        """
        self.playlist_create_error_event.emit(error)

    def load_playlists(self, *args):
        """
        :return:
        """
        playlists = self._context.get('library').get_all_playlists()
        if playlists:
            self.playlists_load_event.emit(playlists)

    def load_playlist(self, playlist_id):
        """
        :param playlist_id:
        :return:
        """
        playlist = self._context.get('playlist_manager').get_playlist(playlist_id)
        if playlist:
            self.active_playlist = playlist

            threading.Thread(target=self._prepare_playlist_tracks, args=(playlist.items, ), daemon=True).start()
        else:
            self.playlist_tracks_data.emit([])

    def _prepare_playlist_tracks(self, tracks: List[TrackItem]):
        """
        :param tracks:
        :return:
        """
        data = []
        for track in tracks:
            track_data = track.track.to_dict()
            track_data['viewclass'] = 'SongTrackItem'
            track_data['song_id'] = track_data['id']
            track_data['metadata'] = track.to_dict()
            data.append(track_data)
        self.playlist_tracks_data.emit(data)

    def remove_track_from_playlist(self, song_id: str):
        """
        :param song_id:
        :return:
        """
        self._context.get('playlist_manager').remove_track_from_playlist(self.active_playlist.id, song_id)
        # refresh
        self.load_playlist(self.active_playlist.id)

    # playlist rename
    def rename_playlist(self, playlist_id: str, new_name: str):
        """
        Updates the playlist name
        :param playlist_id:
        :param new_name:
        :return:
        """

        self._context.get('playlist_manager').rename_playlist(playlist_id, new_name)

    def remove_playlist(self, playlist_id: str):
        """
        Remove playlist
        :param playlist_id:
        :return:
        """
        self._context.get('playlist_manager').delete_playlist(playlist_id)
