from kivy.clock import mainthread
from .base import BaseView
from kivymd.uix.card.card import MDCard
from kivy.properties import (
    StringProperty, ObjectProperty,
    NumericProperty
)
from ..helpers import load_kivy_image_from_data
from core.utility.utils import load_default_image


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
            image = load_kivy_image_from_data(data)
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
        print(data[0])
        self.ids.album_list.data = data
        self.ids.album_list.refresh_from_data()
        print("Album RV data: ", len(self.ids.album_list.data))
        print("Album RV LM: ", self.ids.album_list.layout_manager)
        print("Album RV LM children: ", self.ids.album_list.layout_manager.children)
