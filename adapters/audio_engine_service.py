from enum import Enum
from core import logger
from core.event_bus import EventBus
from domain.models.song import Track
from .audio_engine.core.engine import CoreEngine
from adapters.audio_engine.errors import AudioEngineError
from core.constants.events import PlaybackEngineEvent, PlaybackCommandEvent


class AudioServiceState(Enum):
    ACTIVE = "active"
    DORMANT = "dormant"


class AudioEngineService:

    def __init__(self, event_bus: EventBus, buffer_size=4096, samplerate=44100):
        """
        :param event_bus:
        :param buffer_size:
        :param samplerate:
        """
        self.__engine = CoreEngine(buffer_size=buffer_size, sample_rate=samplerate)
        self.__engine.register_end_event(self.handle_song_end_event)
        self.__engine.register_playback_event(self.handle_playback_events)
        self.__engine.register_position_event(self.receive_playback_pos)
        self.__engine.register_error_event(self.handle_error_event)

        self.bus = event_bus
        self._current_track: Track | None = None

        # register for bus events to receive request
        # Listen for requests from the QueueManager or UI
        self.bus.subscribe(PlaybackCommandEvent.PLAYBACK_REQUEST, self.receive_track_request, priority=5)
        self.bus.subscribe(PlaybackCommandEvent.PLAYBACK_PAUSE, lambda _: self.__engine.pause())
        self.bus.subscribe(PlaybackCommandEvent.PLAYBACK_RESUME, lambda _: self.__engine.resume())
        self.bus.subscribe(PlaybackCommandEvent.PLAYBACK_STOP, lambda _: self.__engine.stop())
        self.bus.subscribe(PlaybackEngineEvent.KILL, self.receive_engine_termination)

    @property
    def state(self):
        return AudioServiceState.ACTIVE if self.__engine.is_playing() else AudioServiceState.DORMANT

    def handle_error_event(self, error: list):
        """
        Handle errors
        :param error: [AudioEngineError, error string]
        :return:
        """
        error_type = error[0]
        match error_type:
            case AudioEngineError.PLAYBACK_ERROR:
                self.bus.publish(PlaybackEngineEvent.PLAYBACK_ERROR, error[1])
            case AudioEngineError.CHANNEL_LOAD_ERROR:
                self.bus.publish(PlaybackEngineEvent.PLAYBACK_LOAD_ERROR, error[1])
            case AudioEngineError.CHANNEL_QUEUE_ERROR:
                self.bus.publish(PlaybackEngineEvent.PLAYBACK_ENQUEUE_ERROR, error[1])

    def handle_song_end_event(self, event: bool):
        """
        :param event:
        :return:
        """
        self.bus.publish(PlaybackEngineEvent.PLAYBACK_COMPLETED, self._current_track)

    def handle_playback_events(self, event:str):
        """
        :param event:
        :return:
        """
        match event.lower():
            case "stop":
                self.bus.publish(PlaybackCommandEvent.PLAYBACK_STOP)
            case "play":
                self.bus.publish(PlaybackEngineEvent.PLAYBACK_STARTED, self._current_track)
            case "pause":
                self.bus.publish(PlaybackCommandEvent.PLAYBACK_PAUSE)

    def receive_playback_pos(self, elapsed, total):
        """
        :param elapsed:
        :param total:
        :return:
        """
        self.bus.publish(PlaybackEngineEvent.PLAYBACK_PROGRESS, {
            'elapsed': elapsed,
            'total': total,
            'track_id': self._current_track.id if self._current_track else None
        })

    def receive_track_request(self, track: Track):
        """
        :param track:
        :return:
        """
        self._current_track = track
        # will save the track to current track and feed it to the engine for playback
        self.__engine.load_file(track.file_path)
        # start playback
        self.__engine.play()
        if self.__engine.is_playing():
            self.bus.publish(PlaybackEngineEvent.PLAYBACK_STARTED, track)
        # events will update automatically
        logger.info(f"[AudioService] Start playback")

    def receive_engine_termination(self, exit_code):
        """
        :param exit_code:
        :return:
        """
        logger.info(f"[AudioService] Terminating service with code: {exit_code}")
        self.__engine.stop(shutdown=True)
