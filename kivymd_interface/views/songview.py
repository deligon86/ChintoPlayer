from .base import BaseView
from kivy.clock import mainthread
from .widgets.common import SongTrackItem


class SongView(BaseView):

    def __init__(self, view_model, context, **kwargs):
        super().__init__(context, **kwargs)
        self._view_model = view_model
        self._view_model.register_load_songs(self._load_song_library)

    @mainthread
    def _load_song_library(self, song_data):
        """
        load library in kivy main thread
        :param song_data:
        :return:
        """
        for item in song_data:
            item['md_bg_color'] = self.md_bg_color

        self.ids.song_container.data.extend(song_data)
        self.ids.song_container.refresh_from_data()
