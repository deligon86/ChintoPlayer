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


class AlbumView(BaseView):

    def __init__(self, view_model, context, **kwargs):
        super().__init__(context, **kwargs)
        self._view_model = view_model
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
            self.ids.album_grid.add_widget(album_item)
            album_item.thumbnail = thumbnail

Factory.register("AlbumsItem", cls=AlbumsItem)
