from threading import RLock
from typing import Callable
from core.event import DefaultEvent
from kivymd_interface.app_core.app_events import AppEvent


class UIEventBus:

    def __init__(self, debug=False):
        self.debug = debug

        self._registry = {}
        self.lock = RLock()

    def _get_event(self, event_type: AppEvent):
        """
        :param event_type:
        :return:
        """
        with self.lock:
            if event_type not in self._registry:
                self._registry[event_type] = DefaultEvent()
            return self._registry[event_type]

    def subscribe(self, event_type: AppEvent, callback: Callable, priority: int = 0):
        """
        :param event_type:
        :param callback:
        :param priority:
        :return:
        """
        event = self._get_event(event_type)
        event.connect(callback, priority=priority)
        if self.debug:
            print(f"[UIEventBus] Subscribe to {event_type}")

    def publish(self, event_type: AppEvent, *args, **kwargs):
        """
        Emits the signal
        :param event_type:
        :param args:
        :param kwargs:
        :return:
        """
        event = self._get_event(event_type)
        event.emit(*args, **kwargs)
        if self.debug:
            print(f"[UIEventBus] Publish from {event_type}")
