from .base import BaseView
from kivy.metrics import dp
from kivy.clock import mainthread, Clock
# import to register to factory, it's weired I still get FactoryException even after registering in the
# playlistview_widgets module
from kivymd_interface.views.widgets.playlistview_widgets import (
    PlaylistButton, PlaylistContainer, PlaylistCreateButton,
    PlaylistCreateDialogContent
)
from .widgets.common import create_dialog, create_alert_dialog


class PlaylistView(BaseView):

    def __init__(self, view_model, context, **kwargs):
        """
        :param view_model:
        :param context:
        :param kwargs:
        """
        super().__init__(context, **kwargs)
        self.view_model = view_model
        self.view_model.playlist_create_event.connect(self.on_playlist_created)
        self.view_model.playlists_load_event.connect(self.on_playlists_load)
        self.view_model.playlist_create_error_event.connect(self.on_playlist_create_error)
        self.create_playlist_dialog = None

        # delay the loading
        Clock.schedule_once(self.view_model.load_playlists, 3)

    def open_create_playlist_dialog(self):
        """
        :return:
        """
        if self.create_playlist_dialog:
            self.create_playlist_dialog.open()
            return

        self.create_playlist_dialog = create_dialog(
            icon="playlist-music", title="Create new playlist",
            description="This action will create a new playlist",
            accept_text="Create", decline_text="Cancel",
            custom_cls=PlaylistCreateDialogContent(),
            accept_callback=self.view_model.create_playlist
        )
        self.create_playlist_dialog.height = dp(270)
        self.create_playlist_dialog.radius = [dp(10)] * 4
        self.create_playlist_dialog.open()

    @mainthread
    def on_playlists_load(self, playlists):
        """
        :param playlists: List[ dict {'name': playlist name, 'id': playlist id}]
        :return:
        """
        self.ids.playlist_container.clear_playlists()
        for playlist in playlists:
            button = PlaylistButton(text=playlist.get('name'),
                                    playlist_id=playlist.get('id'),
                                    theme_bg_color="Custom",
                                    md_bg_color=self.ids.playlist_container.md_bg_color)
            button.register_callback(self.ids.playlist_container.on_playlist_press)
            self.ids.playlist_container.add_playlist_button(button)

    @mainthread
    def on_playlist_created(self, payload: dict):
        """
        :param payload:
        :return:
        """
        # create the playlist button here
        button = PlaylistButton(text=payload.get('name'),
                                playlist_id=payload.get('id'),
                                theme_bg_color="Custom",
                                md_bg_color=self.ids.playlist_container.md_bg_color)
        button.register_callback(self.ids.playlist_container.on_playlist_press)
        self.ids.playlist_container.add_playlist_button(button)

    @mainthread
    def on_playlist_create_error(self, error_str):
        """
        :param error_str:
        :return:
        """
        dialog = create_alert_dialog(
            icon="playlist-music", title="Create new playlist",
            description="Unexpected event occurred while creating playlist",
            message=str(error_str)
        )
        dialog.height = dp(250)
        dialog.radius = [dp(10)] * 4
        dialog.auto_dismiss = False
        dialog.open()

    def playlist_callback(self, playlist_name, playlist_id):
        """
        :param playlist_name:
        :param playlist_id:
        :return:
        """
        print("Playlist: ", playlist_name)
