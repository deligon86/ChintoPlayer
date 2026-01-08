import os
from kivy.core.window import Window

from core.constants.events import LibraryEvent

Window.minimum_width = 600
Window.minimum_height = 500


from kivy.lang import Builder
from kivymd.app import MDApp
from .app_core.app_events import ThemeEvent, UIEvent
from .helpers import resource_path
from kivy.clock import Clock


class ReloMusicPlayerApp(MDApp):

    def __init__(self, context, main_window, **kwargs):
        super().__init__(**kwargs)
        self._context = context
        self.main_window = None
        self.main_window_cls = main_window
        self.context.get('bus').subscribe(ThemeEvent.THEME_CHANGED, self.handle_theme_change)

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
        self.context.get('bus').emit(ThemeEvent.THEME_CHANGED, 'Dark')

        return self.main_window

    def on_start(self):
        # give more room for more event subscription
        Clock.schedule_once(self.schedule_events, 10)  # after 10 secs

    def schedule_events(self, *args):
        self.context.get('bus').emit(UIEvent.APP_READY, True)
        # load library
        self.context.get('library').check_library()
