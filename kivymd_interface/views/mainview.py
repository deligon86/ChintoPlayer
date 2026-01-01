from kivy.properties import ObjectProperty

from kivymd_interface.views.base import BaseView
# imports to avoid kivy factory exception
from kivymd_interface.views.widgets.common import CommonLabel
from kivymd_interface.views.widgets.mainview_side_bar import (
    MainViewSideBar, MainViewSideBarItem
)
from .songview import SongView


class MainView(BaseView):
    song_view = ObjectProperty(SongView)

    def add_song_view(self):
        self.song_view = SongView(self.context)

    def set_views(self):
        """
        Call once to set views
        :return:
        """
        views = [self.song_view]
        children = self.ids.mgr.children
        for view in views:
            if view and view not in children:
                self.ids.mgr.add_widget(view)

