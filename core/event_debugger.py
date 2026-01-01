from core import logger
from core.constants.events import MediaScannerEvent, PlaybackEngineEvent


class EventDebugger:
    _skip = [MediaScannerEvent.SCANNER_PROGRESS, MediaScannerEvent.SCANNER_FINISHED,
             PlaybackEngineEvent.PLAYBACK_PROGRESS]

    def print_event_log(self, event, event_type, *args, **kwargs):
        if event_type not in self._skip:
            msg = f"[Event Debug] Context: {event} Event type: {event_type.value}"
            logger.info(msg)
            print(msg)

