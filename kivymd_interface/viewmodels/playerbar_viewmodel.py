from adapters.audio_engine_service import AudioServiceState
from core.constants.events import PlaybackCommandEvent, PlaybackEngineEvent, ThumbnailEvent
from core.event import DefaultEvent
from core.utility.utils import load_default_image
from kivymd_interface.helpers import load_kivy_image_from_data


class PlayerBarViewModel:
    duration = DefaultEvent()  # float
    progress = DefaultEvent()  # dict: elapsed, total
    thumbnail = DefaultEvent()  # Kivy.core.Image
    track = DefaultEvent()  # domain.song.track

    def __init__(self, context):
        self._context = context
        self._context.get('bus').subscribe(PlaybackEngineEvent.PLAYBACK_STARTED, self.on_playback)
        self._context.get('bus').subscribe(PlaybackEngineEvent.PLAYBACK_PROGRESS, self.on_progress)
        # self._context.get('bus').subscribe(ThumbnailEvent.THUMBNAIL_LOADED, self.on_thumbnail)

    def set_volume(self, value):
        """
        :param value:
        :return:
        """
        self._context.get('bus').publish(PlaybackEngineEvent.PLAYBACK_ENGINE_VOLUME, value)

    def skip(self, mode="previous"):
        """
        :param mode:
        :return:
        """
        match mode.lower():
            case "previous":
                pass
            case "next":
                pass

    def play(self):
        """
        Play pause
        :return:
        """
        service = self._context.get('audio_service')
        bus = self._context.get('bus')
        state = service.get_state()
        if state == AudioServiceState.ACTIVE:
            # we have to pause
            bus.publish(PlaybackCommandEvent.PLAYBACK_PAUSE)
        else:
            bus.publish(PlaybackCommandEvent.PLAYBACK_RESUME)

    def on_playback(self, track):
        """
        :param track:
        :return:
        """
        self.duration.emit(track.duration)
        # For some reason thumbnail service cannot publish thumbnail data, will opt for direct method now
        #self._context.get('thumbnail_service').request_thumbnail(track.id)
        self.thumbnail.emit(track.thumbnail)
        self.track.emit(track)

    def on_progress(self, payload: dict):
        """
        :param payload:
        :return:
        """
        self.progress.emit(payload.get('elapsed') or 0)

    def on_thumbnail(self, payload: dict):
        """
        :param payload:
        :return:
        """
        data = payload.get('data')
        print("Setting thumbnail")
        if data:
            thumbnail = load_default_image()
        else:
            thumbnail = load_kivy_image_from_data(data)
        self.thumbnail.emit(thumbnail)
