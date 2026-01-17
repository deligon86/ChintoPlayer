from kivy.clock import mainthread
from kivy.core.window import Window
from kivy.metrics import dp
from kivymd_interface.app_core.actions import SongAction
from kivymd_interface.views.base import BaseView
from kivymd_interface.views.widgets.common import SongTrackItem, create_dialog, create_alert_dialog
from kivymd_interface.views.widgets.playlistview_widgets import PlaylistSelectionDialogContent


class SongView(BaseView):

    def __init__(self, view_model, context, **kwargs):
        super().__init__(context, **kwargs)
        self._view_model = view_model
        self._view_model.register_load_songs(self._load_song_library)

    def add_to_playlist(self, song_id):
        """
        :param song_id:
        :return:
        """
        # show playlist selection, on press do add to playlist
        playlists = self._view_model.request_playlists()
        if playlists:
            playlist_selection_content = PlaylistSelectionDialogContent(
                size_hint_y=None, height=Window.height * .2
            )

            for playlist in playlists:
                playlist_selection_content.add_playlist(playlist_name=playlist.get('name'),
                                                        playlist_id=playlist.get('id'))

            dialog = create_dialog(icon="playlist-music", title="Select playlist",
                                   description="This action will select the playlist to add to",
                                   accept_text="Add", decline_text="Cancel",
                                   custom_cls=playlist_selection_content,
                                   accept_callback=lambda _: self.on_add_to_playlist(song_id, playlist_selection_content)
                                   )
            dialog.open()
        else:
            create_alert_dialog(
                icon="playlist-music", title="Select playlist",
                description="This seems like nothing to me!",
                message="You haven't created any playlist!"
            ).open()

    def on_add_to_playlist(self, song_id, container: PlaylistSelectionDialogContent):
        """
        :param song_id:
        :param container:
        :return:
        """
        print("[+] Selected playlist: ", container.selected_item.get('name'))
        # wire to view model
        self._view_model.add_song_to_playlist(song_id, container.selected_item.get('id'))

    def create_song_actions(self, song_id) -> list:
        actions = [
            SongAction(label="Add to playlist", callback=self.add_to_playlist, callback_args=(song_id, )),
            SongAction(label="Show tags", callback=self.show_tags, callback_args=(song_id, ))
        ]
        return actions

    @mainthread
    def _load_song_library(self, song_data):
        """
        load library in kivy main thread
        :param song_data:
        :return:
        """
        for item in song_data:
            item['md_bg_color'] = self.md_bg_color
            item['actions'] = self.create_song_actions(item.get('song_id'))

        self.ids.song_container.data.extend(song_data)
        self.ids.song_container.refresh_from_data()
