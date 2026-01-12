from kivy.metrics import dp
from kivymd.uix.boxlayout import MDBoxLayout
from kivymd.uix.card.card import MDCard
from kivy.properties import StringProperty, NumericProperty, ObjectProperty
from kivy.animation import Animation

from kivymd_interface.views.widgets.common import BaseDialogContent


class PlaylistCreateButton(MDCard):
    text = StringProperty()
    icon = StringProperty()


class PlaylistButton(MDCard):
    text = StringProperty()
    playlist_id = StringProperty()

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self._button_callback = None

    def on_release(self, *args) -> None:
        """
        Dispatch the callback
        :param args:
        :return:
        """
        if self._button_callback:
            self._button_callback(self)

    def mark(self):
        """
        Mark this widget
        :return:
        """
        self.theme_bg_color = "Primary"
        Animation(opacity=1, width=dp(4), height=dp(self.height * .55), radius=[dp(2)]*4,
                  duration=.15, md_bg_color=self.theme_cls.tertiaryColor).start(self.ids.marker)

    def clear_mark(self):
        """
        Remove marker
        :return:
        """
        self.theme_bg_color = "Custom"
        self.md_bg_color = self.parent.md_bg_color
        self.ids.marker.opacity = 0
        self.ids.marker.width = 0
        self.ids.marker.height = 0

    def register_callback(self, callback):
        """
        :param callback: Callable
        :return:
        """
        self._button_callback = callback

class PlaylistContainer(MDBoxLayout):
    animation_mark_duration = NumericProperty(.13)
    playlist_callback = ObjectProperty()

    def add_playlist_button(self, item: PlaylistButton):
        """
        :param item:
        :return:
        """
        self.ids.container.add_widget(item)

    def clear_playlists(self):
        """
        :return:
        """
        self.ids.container.clear_widgets()

    def on_playlist_press(self, item: PlaylistButton):
        """
        :param item:
        :return:
        """
        # Mark active item
        for child in self.ids.container.children:
            child.clear_mark()

        item.mark()

        # extract playlist name and id, and execute callback if any
        if self.playlist_callback:
            self.playlist_callback(item.text, item.playlist_id)


# content class for the playlist creation dialog
class PlaylistCreateDialogContent(BaseDialogContent):
    _name = StringProperty()

    @property
    def name(self):
        """
        Gets the field text
        :return:
        """
        return self._name if self._name else self.ids.field.text

    def on_field_input(self, text):
        """
        :param text:
        :return:
        """
        if text:
            self._name = text

    def clear_field(self):
        """
        :return:
        """
        self.ids.field.text = ""
        self._name = ""
