from core.constants.events import LibraryEvent
from core.event import Event
from kivymd_interface.helpers import clean_string


class PlaylistViewModel:

    playlist_create_event = Event(dict)  # this will emit the payload
    playlist_create_error_event = Event(str)
    playlists_load_event = Event(list)

    def __init__(self, context):
        """
        :param context: core context
        """
        self._context = context
        self._context.get('bus').subscribe(LibraryEvent.PLAYLIST_CREATED, self.playlist_created_handle)
        self._context.get('bus').subscribe(LibraryEvent.PLAYLIST_CREATE_ERROR, self.playlist_create_error_handle)

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
