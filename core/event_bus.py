import threading
from typing import Callable, Dict
from core.constants.events import (
    PlaybackEngineEvent, MediaScannerEvent,
    EventType, PlaybackCommandEvent
)
from core.event import DefaultEvent, Event


class EventBus:
    def __init__(self):
        self._lock = threading.RLock()
        # Registry mapping EventType to your custom Event objects
        self._registry: Dict[EventType, DefaultEvent] = {}

        # Pre-initialize known high-frequency events with throttling
        self._setup_default_events()

        # set event debugger
        self._event_debugger = None

    def add_event_debugger(self, debugger):
        self._event_debugger = debugger

    def _setup_default_events(self):
        """
        Configure specific events with custom throttling intervals or type schemas
        :return:
        """
        # Progress updates: Throttled to 100ms
        self._registry[PlaybackEngineEvent.PLAYBACK_PROGRESS] = Event(dict, interval_sec=0.2)
        self._registry[MediaScannerEvent.SCANNER_PROGRESS] = Event(dict, interval_sec=1)

        # command events will have not throttle
        self._registry[PlaybackCommandEvent.PLAYBACK_REQUEST] = DefaultEvent()
        self._registry[PlaybackEngineEvent.PLAYBACK_COMPLETED] = DefaultEvent()

    def _get_event(self, event_type: EventType) -> DefaultEvent:
        """
        Lazy loading of events not pre-configured
        :param event_type
        :return:
        """
        with self._lock:
            if event_type not in self._registry:
                self._registry[event_type] = DefaultEvent()
            return self._registry[event_type]

    def subscribe(self, event_type: EventType, callback: Callable, priority: int = 0):
        """
        Connects a callback
        :param event_type:
        :param callback:
        :param priority:
        :return:
        """
        event = self._get_event(event_type)
        event.connect(callback, priority=priority)
        if self._event_debugger:
            self._event_debugger.print_event_log("Subscribe", event_type, callback)

    def publish(self, event_type: EventType, *args, **kwargs):
        """
        Emits the data
        :param event_type
        :param args:
        :param kwargs
        :return:
        """
        event = self._get_event(event_type)
        event.emit(*args, **kwargs)
        # if debugger present
        if self._event_debugger:
            self._event_debugger.print_event_log("Publish", event_type, *args, **kwargs)

    def emit(self, event_type: EventType, *args, **kwargs):
        """
        Wraps 'publish' method for backward compatibility
        :param event_type:
        :param args:
        :param kwargs:
        :return:
        """
        self.publish(event_type, *args, **kwargs)

    def get_all_events(self):
        return self._registry
