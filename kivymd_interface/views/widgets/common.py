from kivymd.uix.label.label import MDLabel
from kivymd_interface.app_core import running_app
from kivymd_interface.app_core.app_events import ThemeEvent
from kivy.clock import mainthread


class CommonLabel(MDLabel):

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self._app_bus = running_app().context['bus']  # get only the event bus

        self._app_bus.subscribe(ThemeEvent.THEME_FONT_SIZE, self._change_font_size)

    @mainthread
    def _change_font_size(self, size):
        self.font_size = size
