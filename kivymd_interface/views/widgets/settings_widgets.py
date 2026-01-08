from kivy.properties import (
    BooleanProperty, StringProperty,
    ObjectProperty
)
from kivymd.uix.boxlayout import MDBoxLayout
from kivymd.uix.selectioncontrol.selectioncontrol import MDCheckbox


class ThemeSelection(MDBoxLayout):
    theme = StringProperty()
    group = StringProperty('')
    select_callback = ObjectProperty()
    active = BooleanProperty(False)

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.bind(active=self.on_active)

    def on_active(self, _, active):
        """
        :param _:
        :param active:
        :return:
        """
        if active and self.select_callback:
            self.select_callback(self.theme)

