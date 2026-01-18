import threading
from core.event import Event
from core.constants.events import LibraryEvent, PlaybackCommandEvent


class SongViewModel:

    song_data_event = Event(list)

    def __init__(self, context):
        self._context = context
        self._context.get('bus').subscribe(LibraryEvent.LIBRARY_READY, self.on_library_ready)

    def add_song_to_playlist(self, song_id, playlist_id):
        """
        :param song_id:
        :param playlist_id:
        :return:
        """
        self._context.get('playlist_manager').add_track_to_playlist(playlist_id=playlist_id, track=song_id)

    def register_load_songs(self, func):
        """
        Register function to transfer songs to
        :param func:
        :return:
        """
        self.song_data_event.connect(func)

    def request_playlists(self):
        return self._context.get('playlist_manager').get_playlists()

    def on_library_refresh(self, refreshed_data: list):
        """
        :param refreshed_data:
        :return:
        """
        threading.Thread(target=self._prepare_data, args=(refreshed_data, ), daemon=True).start()

    def on_library_ready(self, ready):
        """
        :param ready:
        :return:
        """
        if ready:
            # pull and process data
            songs = self._context.get('library').load_library()
            threading.Thread(target=self._prepare_data, args=(songs, ), daemon=True).start()

    def _prepare_data(self, song_data:list):
        data = []
        for item in song_data:
            item_data = item.to_dict()
            item_data['viewclass'] = 'SongTrackItem'
            item_data['song_id'] = item.id
            data.append(item_data)
        self.song_data_event.emit(data)

    def start_playback(self, song_id):
        """
        Start playback
        :param song_id:
        :return:
        """
        # Create a playback queue container
        track = self._context.get('library').get_song_by_id(song_id)
        container = self._context.get('library').get_queue_manager_context()
        self._context.get('queue_manager').load_continer(container=container, start_index=container.get_index(track))

