from enum import Enum


class AudioEngineError(Enum):
    CHANNEL_QUEUE_ERROR = "channel.queue_file.error"
    CHANNEL_LOAD_ERROR = "channel.load_file.error"
    PLAYBACK_ERROR = "engine.play.error"
