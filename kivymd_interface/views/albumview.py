from kivy.clock import mainthread
from kivy.core.window import Window
from kivy.metrics import dp
from .base import BaseView
from kivymd.uix.card.card import MDCard
from kivy.properties import (
    StringProperty, ObjectProperty,
    NumericProperty
)
from kivy.factory import Factory

from .widgets.common import create_dialog, create_alert_dialog
from .widgets.playlistview_widgets import PlaylistSelectionDialogContent
from ..app_core.actions import SongAction
from ..helpers import load_kivy_image_from_data
from core.utility.utils import load_default_image, convert_to_jpeg
from ..viewmodels.albumviewmodel import AlbumViewModel


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
            image = load_kivy_image_from_data(data)
            self.ids.image.texture = image.texture
        else:
            # load default image
            image = load_default_image()
            self.ids.image.texture = image.texture

    def register_open_callback(self, func):
        """
        :param func:
        :return:
        """
        self._open_callback = func


class AlbumView(BaseView):

    def __init__(self, view_model: AlbumViewModel, context, **kwargs):
        super().__init__(context, **kwargs)
        self._view_model = view_model
        self._view_model.album_tracks_event.connect(self.on_open_album)
        self._view_model.register_load_albums(self._load_albums)

    def add_to_playlist(self, song_id: str):
        """
        :param song_id:
        :return:
        """
        playlists = self._view_model.request_playlists()
        if playlists:
            playlist_selection_cls = PlaylistSelectionDialogContent(size_hint_y=None, height=Window.height * .2)
            for playlist in playlists:
                playlist_selection_cls.add_playlist(playlist_name=playlist.get('name'),
                                                    playlist_id=playlist.get('id'))

            create_dialog(icon="playlist-music", title="Select Playlist",
                          description="This action will select the playlist to add to",
                          accept_text="Add", decline_text="Cancel", custom_cls=playlist_selection_cls,
                          accept_callback=lambda _: self.on_add_to_playlist(song_id, playlist_selection_cls)
            ).open()

    def create_song_actions(self, song_id: str):
        actions = [
            SongAction(label="Add to playlist", callback=self.add_to_playlist, callback_args=(song_id, )),
            SongAction(label="Show tags", callback=self.show_tags, callback_args=(song_id, ))
        ]
        return actions

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

    def on_add_to_playlist(self, song_id: str, content_cls):
        """
        :param song_id:
        :param content_cls:
        :return:
        """
        playlist_id = content_cls.selected_item.get('id')
        if playlist_id:
            self._view_model.add_song_to_playlist(song_id=song_id, playlist_id=playlist_id)
        else:
            create_alert_dialog(
                icon="playlist-music", title="Add to playlist",
                description="An unexpected error occurred while adding track to playlist",
                message="You can't do that! Select the playlist to continue!"
            ).open()

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
        data = payload.get('data')
        for item in data:
            item['actions'] = self.create_song_actions(item.get('song_id'))

        self.ids.album_content.data = data
        self.ids.album_name.text = payload.get('name')
        self.ids.album_songs_count.text = f"[b]Total songs[/b]: {payload.get('count')}"
        self.ids.album_duration.text = f"[b]Duration[/b]: {payload.get('duration')}"
        thumb_data = payload.get('thumbnail')
        if thumb_data:
            image = load_kivy_image_from_data(thumb_data)
        else:
            image = load_default_image(downsample=True)
            # print("Default image texture: ", image.texture)
        #print("Texture: ", image.texture)
        self.ids.album_cover.texture = image.texture


Factory.register("AlbumsItem", cls=AlbumsItem)
