import threading
from core.event import Event
from core.constants.events import LibraryEvent
from kivymd_interface.app_core.app_events import UIEvent


class AlbumViewModel:

    album_data_event = Event(list)

    def __init__(self, context):
        self._context = context
        self._context.get('bus').subscribe(LibraryEvent.LIBRARY_READY, self.on_library_ready)

    def register_load_albums(self, func):
        """
        Register the function to emit albums to
        :param func:
        :return:
        """
        self.album_data_event.connect(func)

    def on_library_ready(self, ready):
        """
        :param ready:
        :return:
        """
        if ready:
            # pull and process data
            albums = self._context.get('library').get_albums()
            threading.Thread(target=self._prepare_data, args=(albums, ), daemon=True).start()

    def _prepare_data(self, album_data:list):
        """
        :return:
        """
        # add view class
        for item in album_data:
            item['viewclass'] = "AlbumItem"

        self.album_data_event.emit(album_data)
