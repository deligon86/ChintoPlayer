from kivy.uix.recyclegridlayout import RecycleGridLayout
from kivymd.uix.fitimage import FitImage

from core import logger
from kivy.metrics import dp
from kivy.properties import (
    StringProperty, OptionProperty, NumericProperty, BooleanProperty, DictProperty
)
from kivy.clock import mainthread, Clock
from kivymd.uix.card import MDCard
from kivymd.uix.label.label import MDLabel
from kivymd.uix.recycleview import MDRecycleView
from kivymd_interface.app_core import running_app
from kivymd.uix.recycleboxlayout import MDRecycleBoxLayout
from kivymd.uix.recyclegridlayout import MDRecycleGridLayout
from kivymd_interface.app_core.app_events import ThemeEvent


class CommonLabel(MDLabel):

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self._app_bus = running_app().context['bus']  # get only the event bus

        self._app_bus.subscribe(ThemeEvent.THEME_FONT_SIZE, self._change_font_size)

    @mainthread
    def _change_font_size(self, size):
        self.font_size = size


# Recycler components
class ResponsiveRecyclerGridLayout(RecycleGridLayout):
    standard_card_width = NumericProperty(dp(120))

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        Clock.schedule_once(self._initial_setup, 1)
        self.bind(width=self._calculate_columns)

    def _initial_setup(self, dt):
        self._calculate_columns()

    def _calculate_columns(self, *args):
        if not hasattr(self, '_lf') or self._lf is None:
            return

        if self.width <= 1:
            return

        available_width = self.width - (self.padding[0] + self.padding[2])
        new_cols = max(1, int(available_width // (self.standard_card_width + self.spacing[0])))

        if self.cols != new_cols:
            self.cols = new_cols


class RecyclerView(MDRecycleView):
    recycler_type = OptionProperty(None, options=['boxlayout', 'gridlayout', None])

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        #self.bind(recycler_type=self.on_recycler_type)
        self.active_layout = None

    def on_recycler_type(self, _, rtype: str | None):
        """
        Set recycler type
        :param _:
        :param rtype:
        :return:
        """
        if rtype:
            widget = None
            match rtype:
                case 'boxlayout':
                    widget = MDRecycleBoxLayout(
                        # use vertical orientation for now
                        orientation='vertical',
                        size_hint_y=None,
                        default_size=[None, dp(56)],
                        default_size_hint=[1, None]
                    )
                    widget.height = widget.minimum_height

                case 'gridlayout':
                    widget = ResponsiveRecyclerGridLayout(
                        size_hint_x=None,
                        default_size=[None, dp(120)],
                        default_size_hint=[1, None]
                    )
                    widget.width = widget.minimum_width
            print("RecyclerType: ", type)
            print("Init recyclelayout: ", widget)
            if widget:
                self.add_widget(widget)
                self.active_layout = widget

            else:
                logger.critical(f"[RecyclerView] Error, couldn't create a recycler container of type: {rtype}")


# Track item
class SongTrackItem(MDCard):
    song_id = StringProperty()
    title = StringProperty()
    artist = StringProperty()
    file_path = StringProperty()
    duration = NumericProperty()
    duration_formated = StringProperty()
    is_current = BooleanProperty()
    metadata = DictProperty()
    theme_bg_color = "Custom"

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.bind(duration=self._format_duration)

    def _format_duration(self, _, length):
        """
        :param _:
        :param length:
        :return:
        """
        if length > 0:
            mins, secs = divmod(length, 60)
            self.duration_formated = f"{int(mins)}:{int(secs)}"
        else:
            self.duration_formated = "--:--"
