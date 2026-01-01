import random
from typing import List, Optional, Deque
from collections import deque
from domain.models.base import BaseItemContainer
from domain.models.song import Track, TrackItem
from domain.enums.playback import RepeatMode
from core.event_bus import EventBus
from core.constants.events import QueueEvent, PlaybackCommandEvent


class QueueManager:
    def __init__(self, event_bus: EventBus):
        self._bus = event_bus

        # State
        self._active_container: Optional[BaseItemContainer] = None
        self._current_index: int = -1
        self._shuffle_indices: List[int] = []
        self._history: Deque[int] = deque(maxlen=50)  # Stores previous indices

        # Settings
        self.repeat_mode = RepeatMode.OFF
        self.is_shuffle = False

    #Loading and enqueuing
    def load_container(self, container: BaseItemContainer, start_index: int = 0):
        """
        Replaces the current queue with a new Album, Playlist, or Artist.
        :param container:
        :param start_index:
        :return:
        """
        self._active_container = container
        self._current_index = start_index
        self._history.clear()

        if self.is_shuffle:
            self._generate_shuffle_map()

        self._emit_current_track()

    def add_to_queue(self, track: Track):
        """
        Adds a track to the end of the *current* active container in memory
        :param track:
        :return:
        """
        if self._active_container:
            item = TrackItem(track=track)
            self._active_container.items.append(item)
            if self.is_shuffle:
                insert_pos = random.randint(1, len(self._shuffle_indices))
                self._shuffle_indices.insert(insert_pos, len(self._active_container.items) - 1)
            self._bus.publish(QueueEvent.QUEUE_UPDATED, self._active_container)

    def remove_track_from_queue(self, track: Track):
        """
        Removes all instances of a specific Track from the queue
        and updates mapping pointers.
        :param track:
        :return:
        """
        if not self._active_container:
            return

        target_indices = [
            i for i, item in enumerate(self._active_container.items)
            if item.track.id == track.id
        ]

        if not target_indices:
            return

        #removal and pointer repair
        for index in reversed(target_indices):
            is_removing_current = (index == self._current_index)
            self._active_container.items.pop(index)

            # remove the index and decrement all pointers > index
            new_shuffle = []
            for s_idx in self._shuffle_indices:
                if s_idx == index:
                    continue
                new_shuffle.append(s_idx - 1 if s_idx > index else s_idx)
            self._shuffle_indices = new_shuffle

            # Repair history
            new_history = deque(maxlen=self._history.maxlen)
            for h_idx in self._history:
                if h_idx == index:
                    continue
                new_history.append(h_idx - 1 if h_idx > index else h_idx)
            self._history = new_history

            # Adjust current index pointer
            if is_removing_current:
                # handle if the playing song was deleted
                self.next()
            elif index < self._current_index:
                self._current_index -= 1

        self._bus.publish(QueueEvent.QUEUE_UPDATED, self._active_container)

    def remove_from_queue(self, index: int):
        """
        Removes an item from the active container and repairs index mappings.
        :param index:
        :return:
        """
        if not self._active_container or index < 0 or index >= len(self._active_container.items):
            return

        is_removing_current = (index == self._current_index)
        self._active_container.items.pop(index)

        #Update shuffle map and current index
        new_shuffle = []
        for i in self._shuffle_indices:
            if i == index:
                continue
            elif i > index:
                new_shuffle.append(i - 1)
            else:
                new_shuffle.append(i)
        self._shuffle_indices = new_shuffle

        # Update current index pointer
        if is_removing_current:
            self.next()
        elif index < self._current_index:
            self._current_index -= 1

        # cleanup history
        updated_history = deque(maxlen=self._history.maxlen)
        for h_idx in self._history:
            if h_idx == index:
                continue
            updated_history.append(h_idx - 1 if h_idx > index else h_idx)
        self._history = updated_history

        self._bus.publish(QueueEvent.QUEUE_UPDATED, self._active_container)

    # Navigation logic
    def next(self):
        """
        Calculates the next index based on Repeat/Shuffle modes
        :return:
        """
        if not self._active_container: return

        self._history.append(self._current_index)
        if self.repeat_mode == RepeatMode.ONE:
            pass

        elif self.is_shuffle:
            # Find position in the shuffle map
            try:
                current_shuffle_pos = self._shuffle_indices.index(self._current_index)
                if current_shuffle_pos < len(self._shuffle_indices) - 1:
                    self._current_index = self._shuffle_indices[current_shuffle_pos + 1]
                elif self.repeat_mode == RepeatMode.ALL:
                    self._generate_shuffle_map()
                    self._current_index = self._shuffle_indices[0]
                else:
                    return  # End of queue
            except ValueError:
                # Fallback if state is desynced
                self._generate_shuffle_map()
                self._current_index = self._shuffle_indices[0]

        else:  # Linear playback
            if self._current_index < len(self._active_container.items) - 1:
                self._current_index += 1
            elif self.repeat_mode == RepeatMode.ALL:
                self._current_index = 0
            else:
                return  # End of queue

        self._emit_current_track()

    def previous(self):
        """
        Goes back to the history or restarts the song.
        :return:
        """
        if not self._active_container: return

        if self._history:
            self._current_index = self._history.pop()
        else:
            self._current_index = 0

        self._emit_current_track()

    # Toggles
    def toggle_shuffle(self):
        """
        :return:
        """
        self.is_shuffle = not self.is_shuffle
        if self.is_shuffle:
            self._generate_shuffle_map()
        else:
            self._shuffle_indices.clear()

        self._bus.publish(QueueEvent.QUEUE_SHUFFLE_TOGGLE, self.is_shuffle)

    def set_repeat_mode(self, mode: RepeatMode):
        """
        :param mode:
        :return:
        """
        self.repeat_mode = mode
        self._bus.publish(QueueEvent.QUEUE_REPEAT_MODE, mode)

    # Helpers
    def _generate_shuffle_map(self):
        if not self._active_container: return
        indices = list(range(len(self._active_container.items)))
        if self._current_index in indices:
            indices.remove(self._current_index)
            random.shuffle(indices)
            self._shuffle_indices = [self._current_index] + indices
        else:
            random.shuffle(indices)
            self._shuffle_indices = indices

    def _emit_current_track(self):
        """
        Updates internal state and notifies the Audio service
        :return:
        """
        if not self._active_container or self._current_index == -1: return
        for i, item in enumerate(self._active_container.items):
            item.is_current = (i == self._current_index)
        self._bus.publish(PlaybackCommandEvent.PLAYBACK_REQUEST,
                          self._active_container.items[self._current_index].track)
