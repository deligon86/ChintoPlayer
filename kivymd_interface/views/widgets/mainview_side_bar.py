from kivy.uix.widget import WidgetException
from kivymd.uix.boxlayout import MDBoxLayout
from kivymd.uix.card import MDCard
from kivy.properties import StringProperty
from kivymd.uix.scrollview import MDScrollView


class MainViewSideBar(MDCard):
    pass


class MainViewSideBarItem(MDCard):
    icon = StringProperty()
    text = StringProperty()

    def mark(self, color):
        self.ids.marker.md_bg_color = color

    def unmark(self):
        self.ids.md_bg_color = self.md_bg_color
