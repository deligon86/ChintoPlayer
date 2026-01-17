from kivy.clock import mainthread
from kivy.metrics import dp
from .base import BaseView
from kivymd.uix.card.card import MDCard
from kivy.properties import (
    StringProperty, ObjectProperty,
    NumericProperty
)
from kivy.factory import Factory
from ..helpers import load_kivy_image_from_data
from core.utility.utils import load_default_image, convert_to_jpeg


class AlbumsItem(MDCard):
    album = StringProperty()
    artist = StringProperty()
    thumbnail = ObjectProperty()
    track_count = NumericProperty()

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.bind(thumbnail=self.on_thumbnail)
        self._open_callback = None

    def on_release(self, *args) -> None:
        if self._open_callback:
            self._open_callback(self.album, self.artist)

    def on_thumbnail(self, _, data):
        """
        :param _:
        :param data:
        :return:
        """
        if data:
            image = load_kivy_image_from_data(convert_to_jpeg(data), ext="jpeg")
            self.ids.image.texture = image.texture
        else:
            # load default image
            image = load_kivy_image_from_data(load_default_image())
            self.ids.image.texture = image.texture

    def register_open_callback(self, func):
        """
        :param func:
        :return:
        """
        self._open_callback = func


class AlbumView(BaseView):

    def __init__(self, view_model, context, **kwargs):
        super().__init__(context, **kwargs)
        self._view_model = view_model
        self._view_model.album_tracks_event.connect(self.on_open_album)
        self._view_model.register_load_albums(self._load_albums)

    @mainthread
    def _load_albums(self, data: list):
        """
        Load albums to view
        :param data:
        :return:
        """
        for item in data:
            thumbnail = item.pop('thumbnail')
            width = self.ids.album_grid.standard_card_width
            item['size'] = [width, width + dp(20)]
            album_item = AlbumsItem(**item)
            album_item.register_open_callback(self.open_album)
            self.ids.album_grid.add_widget(album_item)
            album_item.thumbnail = thumbnail

    def open_album(self, album_name, album_artist):
        """
        :param album_name:
        :param album_artist:
        :return:
        """
        if album_name:
            self._view_model.get_album(album_name, album_artist)

            # change view
            self.ids.view_mgr.current = 'album'

    @mainthread
    def on_open_album(self, payload):
        """
        :param payload:
        :return:
        """
        self.ids.album_content.data = payload.get('data')
        self.ids.album_name.text = f"Album: {payload.get('name')}"
        self.ids.album_songs_count.text = f"Total songs: {payload.get('count')}"
        self.ids.album_duration.text = f"Duration: {payload.get('duration')}"
        thumb_data = payload.get('thumbnail')
        if thumb_data:
            image = load_kivy_image_from_data(thumb_data)
        else:
            image = load_default_image(downsample=True)
            # print("Default image texture: ", image.texture)

        self.ids.album_cover.texture = image.texture


Factory.register("AlbumsItem", cls=AlbumsItem)
