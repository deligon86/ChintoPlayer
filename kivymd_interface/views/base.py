from kivymd.uix.screen import MDScreen


class BaseView(MDScreen):

    def __init__(self, context, **kwargs):
        super().__init__(**kwargs)
        self.context = context

