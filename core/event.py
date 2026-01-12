import inspect
import time
import bisect
import weakref
import threading
from typing import Callable

from core import logger
from threading import Timer


class DefaultEvent:
    def __init__(self):
        self._slots = []
        self._lock = threading.RLock()

    def connect(self, slot, priority=0):
        """
        Connect slots with priority with higher being executed earlier
        :param slot:
        :param priority:
        :return:
        """
        with self._lock:
            if hasattr(slot, "__self__") and slot.__self__ is not None:
                ref = weakref.WeakMethod(slot, self._on_dead_reference)
            else:
                ref = weakref.ref(slot, self._on_dead_reference)

            entry = (-priority, ref)
            bisect.insort(self._slots, entry, key=lambda x: x[0])

    def _on_dead_reference(self, ref):
        # clean all matching deaf ref
        with self._lock:
            self._slots = [s for s in self._slots if s[1] != ref]

    def emit(self, *args, **kwargs):
        with self._lock:
            current_slots = []
            for _, ref in self._slots:
                slot = ref()
                if slot is not None:
                    current_slots.append(slot)

        for slot in current_slots:
            try:
                slot(*args, **kwargs)
            except Exception as e:
                logger.warning(f"Priority Slot Error: {e}")


class ThrottledDefaultEvent(DefaultEvent):

    def __init__(self, interval_sec=0.1):
        super().__init__()
        self.interval_sec = interval_sec
        self.last_emit_time = 0
        self._trailing_timer = None

    def emit(self, *args, **kwargs):
        with self._lock:
            now = time.monotonic()
            elapsed = now - self.last_emit_time

            if elapsed >= self.interval_sec:
                # Cancel any pending trailing emission
                if self._trailing_timer:
                    self._trailing_timer.cancel()

                self._perform_emit(*args, **kwargs)
                self.last_emit_time = now
            else:
                if self._trailing_timer:
                    self._trailing_timer.cancel()

                self._trailing_timer = Timer(
                    self.interval_sec - elapsed,
                    self._perform_emit,
                    args=args, kwargs=kwargs
                )
                self._trailing_timer.start()

    def _perform_emit(self, *args, **kwargs):
        super().emit(*args, **kwargs)


class Event(ThrottledDefaultEvent):
    def __init__(self, *arg_types, interval_sec=0.1):
        super().__init__(interval_sec=interval_sec)
        self._arg_types = arg_types

    def _validate_types(self, args):
        """
        Checks if provided args match the defined schema
        :param args:
        :return:
        """
        if len(args) != len(self._arg_types):
            raise TypeError(
                f"Signal expected {len(self._arg_types)} arguments, got {len(args)}"
            )

        for i, (val, expected_type) in enumerate(zip(args, self._arg_types)):
            if not isinstance(val, expected_type):
                raise TypeError(
                    f"Argument {i} expected {expected_type.__name__}, got {type(val).__name__}"
                )

    def emit(self, *args, **kwargs):
        self._validate_types(args)
        super().emit(*args, **kwargs)
