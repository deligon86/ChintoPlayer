from kivy.metrics import dp
from kivymd.uix.card import MDCard
from kivy.animation import Animation
from kivymd_interface.app_core import running_app
from kivy.properties import (
    StringProperty, ObjectProperty,
    BooleanProperty, NumericProperty, OptionProperty
)
from kivymd_interface.app_core.app_events import UIEvent
from kivy.factory import Factory


class MainViewSideBarItem(MDCard):
    icon = StringProperty()
    text = StringProperty()
    ripple_behavior = True
    bar = ObjectProperty()

    def mark(self, color):
        Animation(md_bg_color=color, width=dp(4), height=self.height * .8, opacity=1,
                  duration=.2).start(self.ids.marker)

    def unmark(self):
        self.ids.marker.opacity = 0
        self.ids.marker.width = 0
        self.ids.marker.height = 0
        self.ids.marker.md_bg_color = self.md_bg_color

    def collapse(self):
        """
        Icon only
        :return:
        """
        self.ids.label.opacity = 0
        self.ids.label.text = ''
        self.ids.size_hint_x = None

    def expand(self):
        """
        Icon and text
        :return:
        """
        self.ids.label.size_hint_x = 1
        self.ids.label.text = self.text
        self.ids.label.opacity = 1

    def on_release(self, *args) -> None:
        if self.bar:
            self.bar.on_item_release(self)


class MainViewSideBar(MDCard):
    focus_behavior = False
    open_state = OptionProperty(None, options=['open', 'close', None])
    open_duration = NumericProperty(.15)
    close_duration = NumericProperty(.12)
    bar_width = NumericProperty(62)
    width_mult = NumericProperty(4)

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self._bus_context = None
        self.bind(open_state=self._on_open_state)

    def on_item_release(self, item: MainViewSideBarItem):
        """
        :param item:
        :return:
        """

        def get_view_name(item_text: str):
            match item_text.lower():
                case "home":
                    return "home_view"
                case "songs":
                    return "song_view"
                case "albums":
                    return "album_view"
                case "playlists":
                    return "playlist_view"
                case "settings":
                    return "settings_view"
                case _:
                    return ""

        for child in self.ids.container.children:
            child.unmark()

        item.mark(running_app().theme_cls.tertiaryColor)

        # send to bus
        if not self._bus_context:
            self._bus_context = running_app().context.get('app_bus')

        self._bus_context.publish(UIEvent.SIDEBAR_ACTIVE_VIEW, get_view_name(item.text))

    def set_state(self):
        """
        :return:
        """
        match self.open_state:
            case None:
                self.open_state = "open"
            case "open":
                self.open_state = "close"
            case "close":
                self.open_state = "open"

    def _on_open_state(self, _, state):
        """
        Open or collapse sidebar
        :param _:
        :param state:
        :return:
        """

        if state:
            if state == "open":
                if self.ids:
                    for item in self.ids.container.children:
                        item.expand()
                # expand bar
                Animation(width=dp(self.bar_width * self.width_mult), duration=self.open_duration).start(self)
            else:
                if self.ids:
                    for item in self.ids.container.children:
                        item.collapse()
                # collapse
                Animation(width=dp(self.bar_width), duration=self.close_duration).start(self)

