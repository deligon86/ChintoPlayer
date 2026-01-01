from enum import Enum


class EventType(Enum):
    pass


class PlaybackCommandEvent(EventType):
    PLAYBACK_REQUEST = "playback.request"  # Data: Track Entity
    PLAYBACK_PAUSE = "playback.pause"  # Data: None
    PLAYBACK_RESUME = "playback.resume"  # Data: None
    PLAYBACK_STOP = "playback.stop"  # Data: None
    PLAYBACK_SEEK = "playback.seek"  # Data int seconds


class PlaybackEngineEvent(EventType):
    PLAYBACK_STARTED = "playback.started"  # Data: Track Entity
    PLAYBACK_COMPLETED = "playback.completed"  # Data: str (track_id)
    PLAYBACK_ERROR = "playback.error"  # Data: str (error message)
    PLAYBACK_PROGRESS = "playback.progress"  # Data: dict {"elapsed": float, "total": float}
    PLAYBACK_LOAD_ERROR = "playback.load.error" # Data : str
    PLAYBACK_ENQUEUE_ERROR = "playback.enqueue.error" # Data: str
    KILL = "engine.kill" # Data int exit code


class QueueEvent(EventType):
    QUEUE_UPDATED = "queue.updated"  # BaseItemContainer
    QUEUE_LOADED = "queue.loaded"  # Data: BaseItemContainer
    QUEUE_TRACK_CHANGED = "queue.track_changed"  # Data: TrackItem
    QUEUE_SHUFFLE_TOGGLE = "queue.shuffle_toggled"  # Data: bool
    QUEUE_REPEAT_MODE = "queue.repeat_mode"  # Data: Enum (OFF, ONE, ALL)


class LibraryEvent(EventType):
    LIBRARY_REFRESHED = "library.refreshed"  # Data: list [updated ids]
    LIBRARY_STAT_UPDATED = "library.stat_updated"  # Data: str (track_id)
    LIBRARY_META_CHANGED = "library.meta_changed"  # Data: Track (updated)
    LIBRARY_READY = "library.ready"  # Data : bool True, False


class ThumbnailEvent(EventType):
    THUMBNAIL_REQUEST = "thumbnail.request"  # Data: str (track_id)
    THUMBNAIL_LOADED = "thumbnail.loaded"  # Data: dict {"id": str, "data": bytes}
    THUMBNAIL_UPDATED = "thumbnail.updated"  # Data: str (track_id)
    THUMBNAIL_ERROR = "thumbnail.error"  # Data: str (track_id)


class MediaScannerEvent(EventType):
    SCANNER_START = "scanner.start" # Payload: {mode: 'single|many', 'payload': str|list} scan single directory or many
    SCANNER_STARTED = "scanner.started"  # Payload: str (path)
    SCANNER_PROGRESS = "scanner.progress"  # Payload: dict {"file": str, "count": int}
    SCANNER_FINISHED = "scanner.finished"  # Payload: int (count)
    SCANNER_ERROR = "scanner.error" # Payload Exception object
