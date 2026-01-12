from .base import BaseView
from kivymd_interface.app_core.app_events import ThemeEvent
from .widgets.settings_widgets import ThemeSelection


class SettingsView(BaseView):

    def set_theme(self, theme):
        self.context.get('app_bus').publish(ThemeEvent.THEME_CHANGED, theme)

