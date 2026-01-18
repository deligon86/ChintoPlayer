from kivy.clock import mainthread
from kivy.metrics import dp
from kivymd.uix.card import MDCard
from kivymd.uix.boxlayout import MDBoxLayout

from core.utility.utils import load_default_image
from kivymd_interface.helpers import load_kivy_image_from_data

BAR_DEFINATION = {
    'default': 90,
}  #style : height


class BasePlayerBar(MDCard):
    radius = [dp(5)] * 4
    focus_behavior = False

    def __init__(self, bar_view_model, **kwargs):
        self._view_model = bar_view_model
        super().__init__(**kwargs)

    def dispatch_command(self, command: dict):
        """
        :param command: cmd:, args:, instance
        :return:
        """
        cmd = command.get('cmd')
        match cmd.lower():
            case 'skip-previous':
                self._view_model.skip('previous')
            case 'skip-next':
                self._view_model.skip('next')
            case 'play':
                self._view_model.play()

    def volume_press(self, icon_button):
        """
        When the volume icon is pressed
        :param icon_button:
        :return:
        """

    def on_volume(self, slider, value):
        """
        :param slider:
        :param value:
        :return:
        """
        self._view_model.set_volume(value)


class PlayerBarContainer(MDBoxLayout):

    def set_height(self, height):
        """
        :param height:
        :return:
        """
        self.height = height

    def set_bar(self, bar: BasePlayerBar, height=120):
        """
        :param bar:
        :param height:
        :return:
        """
        self.clear_widgets()
        self.add_widget(bar)
        self.height = height
        self.height = dp(height)


class DefaultPlayerBar(BasePlayerBar):

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._view_model.duration.connect(self.on_duration)
        self._view_model.progress.connect(self.on_playback_progress)
        self._view_model.thumbnail.connect(self.on_thumbnail)
        self._view_model.track.connect(self.on_track)

    @mainthread
    def on_playback_progress(self, progress: float | int):
        """
        :param progress:
        :return:
        """
        self.ids.progress.value = progress

    @mainthread
    def on_thumbnail(self, thumbnail):
        """
        :param thumbnail:
        :return:
        """
        if thumbnail:
            thumbnail = load_kivy_image_from_data(thumbnail)
        else:
            thumbnail = load_default_image()

        self.ids.art.texture = thumbnail.texture

    @mainthread
    def on_track(self, track):
        """
        :param track:
        :return:
        """
        self.ids.song_name.text = track.title
        self.ids.artist_name.text = track.artist
        self.ids.play_button.icon = "pause-circle"

    @mainthread
    def on_duration(self, duration):
        """
        :param duration:
        :return:
        """
        self.ids.progress.max = duration
