import os
from kivy.core.window import Window


Window.minimum_width = 600
Window.minimum_height = 500
Window.size = (1100, 600)


from kivymd.app import MDApp
from kivy.clock import Clock
from kivy.lang import Builder
from kivymd_interface.helpers import resource_path
from core.constants.events import PlaybackEngineEvent
from kivymd_interface.app_core.ui_event_bus import UIEventBus
from kivymd_interface.app_core.app_events import ThemeEvent, UIEvent


class ReloMusicPlayerApp(MDApp):

    def __init__(self, context, main_window, **kwargs):
        super().__init__(**kwargs)
        self._context = context
        self.main_window = None
        self.main_window_cls = main_window
        self.app_bus = UIEventBus(debug=True)
        self.app_bus.subscribe(ThemeEvent.THEME_CHANGED, self.handle_theme_change)

        # throw app bus to context
        self._context['app_bus'] = self.app_bus

    @property
    def context(self):
        return self._context

    def handle_theme_change(self, theme):
        self.theme_cls.theme_style = theme

    @staticmethod
    def load_kivy_files(directory):
        for root, dir_, files in os.walk(directory):
            for file in files:
                if file.endswith('.kv'):
                    Builder.load_file(os.path.join(root, file))

    def build(self):
        self.load_kivy_files(resource_path("kivymd_interface/kivy_files"))

        self.main_window = self.main_window_cls(self._context)
        self.app_bus.publish(ThemeEvent.THEME_CHANGED, 'Dark')

        # change screen quickly for debugging the current screen that am modifying
        self.app_bus.publish(UIEvent.SIDEBAR_ACTIVE_VIEW, 'song_view')

        return self.main_window

    def on_start(self):
        """
        :return:
        """
        # give more room for more event subscription
        Clock.schedule_once(self.schedule_events, 3)  # after 10 secs

    def schedule_events(self, *args):
        """
        :param args:
        :return:
        """
        # load library
        self.context.get('library').check_library(2)

    def on_stop(self):
        """
        :return:
        """
        # close all services
        self.context.get('bus').publish(PlaybackEngineEvent.KILL, -2)