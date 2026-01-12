
from core import logger
from kivy.metrics import dp
from typing import Callable
from kivy.properties import (
    StringProperty, OptionProperty, NumericProperty, BooleanProperty, DictProperty
)
from kivymd.uix.card import MDCard
from kivy.uix.widget import Widget
from kivy.clock import mainthread, Clock
from kivymd.uix.divider import MDDivider
from kivymd.uix.label.label import MDLabel
from kivymd.uix.boxlayout import MDBoxLayout
from kivymd.uix.gridlayout import MDGridLayout
from kivymd.uix.recycleview import MDRecycleView
from kivymd_interface.app_core import running_app
from kivymd.uix.button import MDButtonText, MDButton
from kivymd.uix.recycleboxlayout import MDRecycleBoxLayout
from kivymd.uix.recyclegridlayout import MDRecycleGridLayout
from kivymd_interface.app_core.app_events import ThemeEvent
from kivy.factory import Factory
from kivymd.uix.dialog.dialog import (
    MDDialog, MDDialogIcon,
    MDDialogHeadlineText,
    MDDialogSupportingText,
    MDDialogContentContainer,
    MDDialogButtonContainer
)


class CommonLabel(MDLabel):

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self._app_bus = running_app().context['bus']  # get only the event bus

        self._app_bus.subscribe(ThemeEvent.THEME_FONT_SIZE, self._change_font_size)

    @mainthread
    def _change_font_size(self, size):
        self.font_size = size


class ResponsiveGrid(MDGridLayout):
    standard_card_width = NumericProperty(dp(180))

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.bind(size=self._recalc)

    def _recalc(self, *args):
        available_width = self.width - (self.padding[0] + self.padding[2])
        cols = int(max(1, available_width // self.standard_card_width))
        if cols != self.cols:
            self.cols = cols


# Recycler components
class ResponsiveRecyclerGridLayout(MDRecycleGridLayout):
    pass


class RecyclerView(MDRecycleView):
    recycler_type = OptionProperty(None, options=['boxlayout', 'gridlayout', None])
    standard_card_width = NumericProperty(dp(120))

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.active_layout = None
        self.grid_size_bound = False

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
                    widget.height = widget.minimum_height
            if widget:
                self.add_widget(widget)
                self.active_layout = widget

            else:
                logger.critical(f"[RecyclerView] Error, couldn't create a recycler container of type: {rtype}")

    def _init_cols(self, dt):
        if not self.grid_size_bound:
            self.bind(size=self._recalc_cols)
            self.grid_size_bound = True
        self._recalc_cols()

    def _on_data(self, _, data):
        """
        Data is set, manually trigger the gridlayout
        :param _:
        :param data:
        :return:
        """
        if data:
            if isinstance(self.layout_manager, ResponsiveRecyclerGridLayout):
                # trigger columns
                Clock.schedule_once(self._init_cols, 1)
                logger.info("[RecyclerView] Triggered layout columns")

    def _recalc_cols(self, *args):
        lm = self.layout_manager
        if not isinstance(lm, ResponsiveRecyclerGridLayout):
            return

        if self.width <= 1:
            return

        available_width = self.width - (lm.padding[0] + lm.padding[2])
        new_cols = max(1, available_width // self.standard_card_width)
        if lm.cols != new_cols:
            lm.cols = new_cols


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


# dialog creation

class BaseDialogContent(MDBoxLayout):
    pass


def create_dialog(icon: str, title: str, description: str, accept_text: str = "", decline_text: str = "",
                  accept_callback: Callable = None, decline_callback: Callable = None,
                  custom_cls: BaseDialogContent = None):
    """
    Create a new dialog
    :param icon:
    :param title:
    :param description:
    :param accept_text:
    :param decline_text:
    :param accept_callback:
    :param decline_callback:
    :param custom_cls: Whether the dialog has a custom class
    :return:
    """
    dialog = MDDialog(
        # icon, title and description
        MDDialogIcon(icon=icon),
        MDDialogHeadlineText(text=title),
        MDDialogSupportingText(text=description),
        # content
        MDDialogContentContainer(
            MDDivider(),
            custom_cls,  # important to hold the dialog content
            spacing=dp(8),
            orientation='vertical'
        ),
        # buttons
        MDDialogButtonContainer(
            Widget(),
            MDButton(
                MDButtonText(
                    text=decline_text
                ),
                style='text',
                on_release=lambda _: decline_callback(custom_cls) if decline_callback else dialog.dismiss()
            ),
            MDButton(
                MDButtonText(
                    text=accept_text
                ),
                style='text',
                on_release=lambda _: accept_callback(custom_cls)
            ),
            spacing='8dp'
        ),
        auto_dismiss=False
    )

    return dialog


def create_alert_dialog(icon:str, title: str, description: str, message: str):
    """
    Create an informational dialog
    :param icon:
    :param title:
    :param description:
    :param message:
    :return:
    """
    dialog = None
    dialog = MDDialog(
        MDDialogIcon(
            icon=icon
        ),
        MDDialogHeadlineText(
            text=title
        ),
        MDDialogSupportingText(
            text=description
        ),
        # content
        MDDialogContentContainer(
            MDDivider(),
            MDLabel(
                text=message,
                adaptive_height=True,
                halign="center"
            ),
            spacing=dp(8),
            orientation="vertical"
        ),
        MDDialogButtonContainer(
            Widget(),
            MDButton(
                MDButtonText(
                    text="Ok"
                ),
                style='text',
                on_release=lambda _: dialog.dismiss()
            ),
            spacing="8dp"
        ),
        radius=[5, 5, 5, 5]
    )
    dialog.radius = [5, 5, 5, 5]

    return dialog


# register to factory
Factory.register("CommonLabel", cls=CommonLabel)
Factory.register("SongTrackItem", cls=SongTrackItem)
Factory.register("RecyclerView", cls=RecyclerView)
Factory.register("ResponsiveRecyclerGridLayout", cls=ResponsiveRecyclerGridLayout)
Factory.register("ResponsiveGrid", cls=ResponsiveGrid)
