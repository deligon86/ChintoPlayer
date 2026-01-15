from kivy.core.window import Window
from kivy.properties import StringProperty
from kivymd.uix.boxlayout import MDBoxLayout
from kivymd.uix.screen import MDScreen
from kivymd_interface.views.widgets.common import BaseDialogContent, create_alert_dialog


class TagItem(MDBoxLayout):
    tag_name = StringProperty()
    tag_value = StringProperty()


class SongTagDialogContent(BaseDialogContent):

    @staticmethod
    def _format_name_tags(tag_name: str):
        """
        :return:
        """
        tag_name = tag_name.capitalize()
        tag_name_split = tag_name.split("_")
        return " ".join(tag_name_split)

    def render_tags(self, tag_data):
        """
        :param tag_data:
        :return:
        """
        thumbnail_data = tag_data.get('thumbnail')
        tag_data['thumbnail'] = "Embedded" if thumbnail_data else "No thumbnail"
        tag_data.pop('id')  # not necessary
        for name, value in tag_data.items():
            if 'metadata' in name:
                new_value = ""
                for k, v in value.items():
                    new_value += f"\n{self._format_name_tags(k)}   :  {v}"
                value = new_value if new_value else "Empty"

            tag = TagItem(tag_name=self._format_name_tags(name), tag_value=str(value))
            self.ids.container.add_widget(tag)

        return self


class BaseView(MDScreen):

    def __init__(self, context, **kwargs):
        super().__init__(**kwargs)
        self.context = context

    def create_song_actions(self, song_id: str):
        """
        :param song_id:
        :return:
        """

    def show_tags(self, song_id: str):
        """
        :param song_id:
        :return:
        """
        track = self.context.get('library').get_song_by_id(song_id)
        # get thumbnail
        thumbnail = self.context.get('library').get_thumbnail(song_id)
        track_data = track.to_dict()
        track_data['thumbnail'] = thumbnail
        content_cls = SongTagDialogContent(
            size_hint_y=None, height=Window.height * .5
        ).render_tags(track_data)
        dialog = create_alert_dialog(
            icon="information", title="Song tags",
            description="See beneath the title",
            cls=content_cls
        )
        dialog.open()
