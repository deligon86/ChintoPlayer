import os
from kivy.core.window import Window

Window.minimum_width = 600
Window.minimum_height = 500

from kivy.lang import Builder
from kivymd.app import MDApp
from .app_core.app_events import ThemeEvent
from .helpers import resource_path


class ReloMusicPlayerApp(MDApp):

    def __init__(self, context, main_window, **kwargs):
        super().__init__(**kwargs)
        self.context = context
        self.main_window = None
        self.main_window_cls = main_window
        self.context.get('bus').subscribe(ThemeEvent.THEME_CHANGED, self.handle_theme_change)

    def handle_theme_change(self, theme):
        self.theme_cls.theme_style = theme

    @staticmethod
    def load_kivy_files(directory):
        for root, dir_, files in os.walk(directory):
            for file in files:
                if file.endswith('.kv'):
                    print("KV: ", file)
                    Builder.load_file(os.path.join(root, file))

    def build(self):
        self.load_kivy_files(resource_path("kivymd_interface/kivy_files"))
        self.main_window = self.main_window_cls(self.context)
        self.main_window.add_song_view()
        self.main_window.set_views()
        self.context.get('bus').emit(ThemeEvent.THEME_CHANGED, 'Dark')

        return self.main_window
