from kivy.properties import ObjectProperty

from core import logger
from kivymd_interface.views.base import BaseView
from kivymd_interface.views.songview import SongView
from kivymd_interface.views.homeview import HomeView
from kivymd_interface.views.albumview import AlbumView
from kivymd_interface.views.playlistview import PlaylistView
from kivymd_interface.views.settingsview import SettingsView
from kivymd_interface.app_core.app_events import UIEvent
from kivymd_interface.viewmodels.songviewmodel import SongViewModel
from kivymd_interface.viewmodels.albumviewmodel import AlbumViewModel
from kivymd_interface.viewmodels.playlistviewmodel import PlaylistViewModel
# register to factory
from kivymd_interface.views.widgets.mainview_side_bar import (
    MainViewSideBar, MainViewSideBarItem
)

class MainView(BaseView):
    song_view = ObjectProperty(SongView)
    album_view = ObjectProperty(AlbumView)
    home_view = ObjectProperty(HomeView)
    playlist_view = ObjectProperty(PlaylistView)
    settings_view = ObjectProperty(SettingsView)

    def __init__(self, context, **kwargs):
        super().__init__(context, **kwargs)

        self.initialize_views()
        self.context.get('app_bus').subscribe(UIEvent.SIDEBAR_ACTIVE_VIEW, self.change_screen)

    def initialize_views(self):
        """
        Call once to set views
        :return:
        """
        self.song_view = SongView(name="song_view", context=self.context,
                                  view_model=SongViewModel(context=self.context))
        self.album_view = AlbumView(name="album_view", context=self.context,
                                    view_model=AlbumViewModel(context=self.context))
        self.playlist_view = PlaylistView(name="playlist_view", context=self.context,
                                          view_model=PlaylistViewModel(context=self.context))
        self.settings_view = SettingsView(name="settings_view", context=self.context)
        self.home_view = HomeView(name="home_view", context=self.context)
        views = [self.song_view, self.album_view, self.playlist_view, self.settings_view,
                 self.home_view]

        children = self.ids.mgr.children
        for view in views:
            if view and view not in children:
                self.ids.mgr.add_widget(view)

    def change_screen(self, name: str):
        """
        Change the view name
        :param name:
        :return:
        """

        try:
            self.ids.mgr.current = name
        except:
            logger.warning(f"[Navigation] Error setting view, invalid view: {name}")

