from kivymd.uix.label import MDLabel

from core import logger
from .base import BaseView
from kivy.metrics import dp
from kivy.clock import mainthread, Clock
# import to register to factory, it's weired I still get FactoryException even after registering in the
# playlistview_widgets module
from kivymd_interface.views.widgets.playlistview_widgets import (
    PlaylistButton, PlaylistContainer, PlaylistCreateButton,
    PlaylistCreateDialogContent, PlaylistRenameContent
)
from .widgets.common import create_dialog, create_alert_dialog
from ..app_core.actions import SongAction, PlaylistAction


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
        self.view_model.playlist_tracks_data.connect(self.on_playlist_load)
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

    def create_song_actions(self, song_id: str):
        """
        :param song_id:
        :return:
        """
        actions = [
            SongAction(label="Show tags", callback=self.show_tags, callback_args=(song_id,)),
            SongAction(label="Remove", callback=self.remove_from_playlist, callback_args=(song_id, ))
        ]
        return actions

    def create_playlist_actions(self, playlist_id: str, playlist_name: str) -> list:
        """
        :param playlist_id:
        :param playlist_name:
        :return:
        """
        actions = [
            PlaylistAction(label="Rename", callback=self.rename_playlist, callback_args=(playlist_id, playlist_name)),
            PlaylistAction(label="Remove", callback=self.remove_playlist, callback_args=(playlist_id, playlist_name))
        ]

        return actions

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
                                    md_bg_color=self.ids.playlist_container.md_bg_color,
                                    actions=self.create_playlist_actions(playlist_id=playlist.get('id'),
                                                                         playlist_name=playlist.get('name')))
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
                                md_bg_color=self.ids.playlist_container.md_bg_color,
                                actions=self.create_playlist_actions(playlist_id=payload.get('id'),
                                                                     playlist_name=payload.get('name')))
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

    @mainthread
    def on_playlist_load(self, tracks):
        """
        :param tracks:
        :return:
        """
        if tracks:
            for track in tracks:
                track['actions'] = self.create_song_actions(track.get('song_id'))
            self.ids.playlist_content.data = tracks
            logger.info("[PlaylistView] Loaded playlist tracks")
        else:
            create_alert_dialog(
                icon="playlist-music", title="Playlist",
                description="This action was triggered by playlist loading",
                message="The playlist you chose is empty! Add songs to get started"
            ).open()

    def playlist_open_callback(self, playlist_name, playlist_id):
        """
        :param playlist_name:
        :param playlist_id:
        :return:
        """
        self.view_model.load_playlist(playlist_id)

    # playlist rename
    def rename_playlist(self, playlist_id: str, playlist_name: str):
        """
        :param playlist_id:
        :param playlist_name:
        :return:
        """
        # open a new dialog and save playlist
        rename_content_cls = PlaylistRenameContent(size_hint_y=None, height=dp(100))
        rename_dialog = create_dialog(
            icon="playlist-edit", title="Rename playlist",
            description=f"This action will rename the playlist: {playlist_name}!",
            accept_text="Rename", decline_text="Cancel",
            accept_callback=lambda _: self.on_rename_playlist(playlist_id, rename_content_cls)
        )
        rename_dialog.open()

    def on_rename_playlist(self, playlist_id: str, content_cls: PlaylistRenameContent):
        """
        Do rename
        :param playlist_id:
        :param content_cls:
        :return:
        """
        if content_cls.text:
            self.view_model.rename_playlist(playlist_id, content_cls.text)
        else:
            # no name provided, cannot do a rename with an empty string
            create_alert_dialog(
                icon="playlist-edit", title="Rename playlist",
                description="An error occurred while renaming the playlist",
                message="The playlist name cannot be empty, provide a name to continue."
            ).open()

    # remove playlist
    def remove_playlist(self, playlist_id: str, playlist_name: str):
        """
        :param playlist_id:
        :param playlist_name:
        :return:
        """
        # create a confirmation for deletion as the action may be accidental
        confirm_dialog = create_dialog(
            icon="playlist-edit", title="Delete Playlist",
            description=f"This action will delete the playlist below!",
            custom_cls=MDLabel(text=playlist_name, halign="center", adaptive_height=True),
            accept_text="Delete", decline_text="Cancel",
            accept_callback=lambda _: self.on_remove_playlist(playlist_id)
        )
        confirm_dialog.open()

    def on_remove_playlist(self, playlist_id: str):
        """
        :param playlist_id:
        :return:
        """
        # user has confirmed delete, so delete
        self.view_model.remove_playlist(playlist_id)

    # remove track from playlist
    def remove_from_playlist(self, song_id: str):
        """
        :param song_id:
        :return:
        """
        self.view_model.remove_track_from_playlist(song_id)
