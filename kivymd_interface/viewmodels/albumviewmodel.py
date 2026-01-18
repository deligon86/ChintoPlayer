import threading
from core.event import Event
from core.constants.events import LibraryEvent, ThumbnailEvent
from kivymd_interface.app_core.app_events import UIEvent
from kivymd_interface.helpers import format_duration


class AlbumViewModel:

    album_data_event = Event(list)
    album_tracks_event = Event(dict)

    def __init__(self, context):
        self._context = context
        self._context.get('bus').subscribe(LibraryEvent.LIBRARY_READY, self.on_library_ready)

    def add_song_to_playlist(self, song_id: str, playlist_id: str):
        """
        :param song_id:
        :param playlist_id:
        :return:
        """
        self._context.get('playlist_manager').add_track_to_playlist(playlist_id=playlist_id, track=song_id)

    def register_load_albums(self, func):
        """
        Register the function to emit albums to
        :param func:
        :return:
        """
        self.album_data_event.connect(func)

    def request_playlists(self):
        return self._context.get('playlist_manager').get_playlists()

    def on_library_ready(self, ready):
        """
        :param ready:
        :return:
        """
        if ready:
            # pull and process data
            albums = self._context.get('library').get_albums()
            threading.Thread(target=self._prepare_albums, args=(albums, ), daemon=True).start()

    def _prepare_albums(self, album_data:list):
        """
        :return:
        """
        # add view class
        #for item in album_data:
        #    item['viewclass'] = "AlbumsItem"
        self.album_data_event.emit(album_data)

    def get_album(self, name, artist):
        """
        :param name:
        :param artist:
        :return:
        """
        tracks = self._context.get('library').get_tracks_by_album(name, artist)
        threading.Thread(target=self._prepare_album_track, args=(tracks, name), daemon=True).start()

    def _prepare_album_track(self, album_tracks, name):
        """
        :param album_tracks:
        :return:
        """
        tracks = []
        duration = 0
        for track in album_tracks:
            track_data = track.to_dict()  # domain.song.Track
            track_data['viewclass'] = 'SongTrackItem'
            track_data['song_id'] = track.id
            tracks.append(track_data)
            duration += track.duration

        payload = {'data': tracks, 'count': len(album_tracks),
                   'duration': format_duration(duration), 'name': name,
                   'thumbnail': album_tracks[0].thumbnail # get thumbnail from first item
                   }
        self.album_tracks_event.emit(payload)
