

import uuid
import random
from domain.models.queue import QueueStatus, MusicQueue
from domain.models.song import Track, TrackItem
from typing import (
    List, Dict, Optional,
    Any
)
from core.event import Event
from enums.playback import RepeatMode


class QueueEvents:
    queue_created = Event(str)  # queue id
    queue_deleted = Event(str)  # queue name
    queue_updated = Event(str)  # queue id
    queue_activated = Event(str)  # queue id
    queue_item_added = Event(list)  # queue name, queue item
    queue_item_removed = Event(list)  # queue name, queue item
    current_track_changed = Event(str)  # queue id
    shuffle_changed = Event(bool)
    repeat_mode_changed = Event(str)


class QueueManager:
    event = QueueEvents()

    def __init__(self):
        self._queues: Dict[str, MusicQueue] = {}
        self._active_queue_id = None
        self._history = []
        self._shuffled_indices: Dict[str, List[int]] = {}

    def create_queue(self, name: str, items: List[Track] = None, shuffle: bool = False,
                     repeat_mode: RepeatMode = RepeatMode.OFF,
                     metadata: Dict[str, Any] = None, make_active: bool = False):
        queue_id = str(uuid.uuid4())
        queue_items = [TrackItem(track=track) for track in (items or [])]
        queue = MusicQueue(
            id=queue_id,
            name=name,
            items=queue_items,
            shuffle=shuffle,
            repeat_mode=repeat_mode,
            metadata=metadata or {}
        )

        self._queues[queue_id] = queue
        if shuffle:
            self._generate_shuffle_order(queue_id)

        if make_active:
            self.set_active_queue(queue_id)

        self.event.queue_created.emit(queue_id)
        return queue

    def is_queue(self, name: str):
        return True if self.get_queue_by_name(name) else False

    def get_queue(self, queue_id: str) -> Optional[MusicQueue]:
        return self._queues.get(queue_id)

    def get_queue_by_name(self, name: str) -> Optional[MusicQueue]:
        for queue in self._queues.values():
            if queue.name.lower() == name.lower():
                return queue

        return None

    def get_queue_name(self, queue_id: str):
        queue = self.get_queue(queue_id)
        if queue:
            return queue.name
        return None

    def get_all_queues(self) -> List[MusicQueue]:
        return list(self._queues.values())

    def delete_queue(self, queue_id: str) -> bool:
        if queue_id in self._queues:
            if self._active_queue_id == queue_id:
                self.clear_active_queue()

            if queue_id in self._shuffled_indices:
                del self._shuffled_indices[queue_id]

            del self._queues[queue_id]

            self.event.queue_deleted.emit(self.get_queue_name(queue_id))
            return True
        return False

    # Region: active queue management
    def set_active_queue(self, queue_id):
        queue = self.get_queue(queue_id)
        if queue:
            old_active = self._active_queue_id
            self._active_queue_id = queue_id

            if old_active and old_active != queue_id:
                self._history.append(old_active)
                # keep only last 10 in history
                self._history = self._history[-10:]

            queue.status = QueueStatus.ACTIVE

            self.event.queue_activated.emit(queue_id)
            if old_active:
                self.event.queue_updated.emit(old_active)

            return queue

        return None

    def get_active_queue(self) -> Optional[MusicQueue]:
        if self._active_queue_id:
            return self.get_queue(self._active_queue_id)
        return None

    def clear_active_queue(self):
        active = self.get_active_queue()
        if active:
            active.status = QueueStatus.STOPPED
        self._active_queue_id = None

    def get_previous_queue(self) -> Optional[MusicQueue]:
        if self._history:
            prev_queue_id = self._history.pop()
            return self.set_active_queue(prev_queue_id)
        return None

    # EndRegion

    # Region QueueItem operations
    def add_to_queue(self, queue_id: str, tracks: List[Track], position: int | None = None) -> Optional[MusicQueue]:
        queue = self.get_queue(queue_id)
        if queue:
            for track in tracks:
                item = TrackItem(track=track)
                if position is not None and 0 <= position <= len(queue.items):
                    queue.items.insert(position, item)
                else:
                    queue.items.append(item)
                position = position + 1 if position is not None else None

            if queue.shuffle:
                self._generate_shuffle_order(queue_id)

            self.event.queue_item_added.emit(queue_id)
            self.event.queue_updated.emit(queue_id)

            return queue
        return None

    def add_to_active_queue(self, tracks: List[Track], position: int | None = None) -> Optional[MusicQueue]:
        if self._active_queue_id:
            return self.add_to_queue(self._active_queue_id, tracks, position)
        return None

    def remove_from_queue(self, queue_id: str, indices: List[int]) -> Optional[MusicQueue]:
        queue = self.get_queue(queue_id)
        if queue:
            queue_item = None
            for idx in sorted(indices, reverse=True):
                if 0 <= idx < len(queue.items):
                    if idx < queue.current_position:
                        queue.current_position -= 1
                    elif idx == queue.current_position:
                        # move to next or reset
                        if queue.current_position < len(queue.items) - 1:
                            pass
                        else:
                            queue.current_position = max(0, queue.current_position - 1)
                    queue_item = queue.items.pop(idx)

            if queue.shuffle:
                self._generate_shuffle_order(queue_id)

            self.event.queue_item_removed.emit([queue_id, queue_item])
            self.event.queue_updated.emit(queue_id)
            if any(idx == queue.current_position for idx in indices):
                self.event.current_track_changed.emit(queue_id)

            return queue

        return None

    def move_queue_item(self, queue_id: str, from_index: int, to_index: int) -> Optional[MusicQueue]:
        queue = self.get_queue(queue_id)
        if queue and 0 <= from_index < len(queue.items) and 0 <= to_index < len(queue.items):
            item = queue.items.pop(from_index)
            queue.items.insert(to_index, item)

            # adjust position and update shuffle indices
            if queue.current_position == from_index:
                queue.current_position = to_index
            elif from_index < queue.current_position <= to_index:
                queue.current_position -= 1
            elif to_index <= queue.current_position < from_index:
                queue.current_position += 1

            if queue.shuffle:
                self._generate_shuffle_order(queue_id)

            self.event.queue_updated.emit('queue_updated', queue_id)
            return queue
        return None

    def clear_queue(self, queue_id: str) -> bool:
        queue = self.get_queue(queue_id)
        if queue:
            queue.items.clear()
            queue.current_position = 0
            if queue.shuffle:
                self._shuffled_indices[queue_id] = []

            self.event.queue_updated.emit(queue_id)
            return True
        return False

    # EndRegion

    # Region playback navigation
    def get_next_track_index(self, queue_id: str) -> Optional[int]:
        queue = self.get_queue(queue_id)
        if not queue or not queue.items:
            return None

        current_idx = queue.current_position
        if queue.repeat_mode == RepeatMode.ONE:
            return current_idx
        if queue.shuffle:
            return self._get_next_shuffled_index(queue_id)

        if queue.repeat_mode.value == RepeatMode.ALL and current_idx >= len(queue.items) - 1:
            return 0
        elif current_idx < len(queue.items) - 1:
            return current_idx + 1

        return None

    def get_previous_track_index(self, queue_id: str) -> Optional[int]:
        queue = self.get_queue(queue_id)
        if not queue or not queue.items:
            return None

        current_idx = queue.current_position
        if queue.repeat_mode == RepeatMode.ONE:
            return current_idx
        if queue.shuffle:
            return self._get_next_shuffled_index(queue_id)

        if queue.repeat_mode.value == RepeatMode.ALL and current_idx == len(queue.items) - 1:
            return len(queue.items) - 1
        elif current_idx > 0:
            return current_idx - 1

        return None

    def set_current_track(self, queue_id: str, index: int) -> bool:
        queue = self.get_queue(queue_id)
        if queue and 0 <= index < len(queue.items):
            queue.current_position = index

            if queue.current_item:
                queue.current_item.played = True
                queue.current_item.play_count += 1

            self.event.current_track_changed.emit(queue_id)
            self.event.queue_updated.emit(queue_id)

            return True
        return False

    # EndRegion

    # Region shuffle management
    def toggle_shuffle(self, queue_id: str) -> Optional[MusicQueue]:
        queue = self.get_queue(queue_id)
        if queue:
            queue.shuffle = not queue.shuffle
            if queue.shuffle:
                self._generate_shuffle_order(queue_id)
            else:
                if queue_id in self._shuffled_indices:
                    del self._shuffled_indices[queue_id]

            self.event.shuffle_changed.emit(True)
            self.event.queue_updated.emit(queue_id)

            return queue
        return None

    def _generate_shuffle_order(self, queue_id):
        queue = self.get_queue(queue_id)
        if not queue:
            return

        indices = list(range(len(queue.items)))
        current_index = queue.current_position
        if 0 <= current_index < len(queue.items):
            indices.pop(current_index)

        random.shuffle(indices)

        if 0 <= current_index < len(queue.items):
            # insert current index at the beginning
            indices.insert(0, current_index)

        self._shuffled_indices[queue_id] = indices

    def _get_next_shuffled_index(self, queue_id):
        if queue_id not in self._shuffled_indices:
            self._generate_shuffle_order(queue_id)

        shuffled = self._shuffled_indices[queue_id]
        queue = self.get_queue(queue_id)

        if not shuffled or not queue:
            return None

        current_index = queue.current_position
        try:
            current_pos_in_shuffle = shuffled.index(current_index)
        except ValueError:
            return None

        if queue.repeat_mode == RepeatMode.ALL and current_pos_in_shuffle >= len(shuffled) - 1:
            # regen shuffle
            self._generate_shuffle_order(queue_id)
            shuffled = self._shuffled_indices[queue_id]
            return shuffled[0] if shuffled else None
        elif current_pos_in_shuffle < len(shuffled) - 1:
            return shuffled[current_pos_in_shuffle + 1]

        return None

    def _get_previous_shuffled_index(self, queue_id):
        if queue_id not in self._shuffled_indices:
            self._generate_shuffle_order(queue_id)

        shuffled = self._shuffled_indices[queue_id]
        queue = self.get_queue(queue_id)

        if not shuffled or not queue:
            return None

        current_index = queue.current_position
        try:
            current_pos_in_shuffle = shuffled.index(current_index)
        except ValueError:
            return None

        if queue.repeat_mode == RepeatMode.ALL and current_pos_in_shuffle == 0:
            # regen shuffle
            self._generate_shuffle_order(queue_id)
            shuffled = self._shuffled_indices[queue_id]
            return shuffled[-1] if shuffled else None
        elif current_pos_in_shuffle > 0:
            return shuffled[current_pos_in_shuffle - 1]

        return None

    # EndRegion

    # Region repeat
    def set_repeat_mode(self, queue_id: str, mode: RepeatMode) -> Optional[MusicQueue]:
        queue = self.get_queue(queue_id)
        if queue:
            queue.repeat_mode.value = mode.value()
            self.event.repeat_mode_changed.emit(mode.value)
            self.event.queue_updated.emit(queue_id)
            return queue
        return None

    # EndRegion

    # Region search and filter
    def search_in_queue(self, queue_id: str, query) -> List[Dict[str, Any]]:
        queue = self.get_queue(queue_id)
        if not queue:
            return []

        query_lower = query.lower()
        results = []

        for idx, item in enumerate(queue.items):
            track = item.track
            if (query_lower in track.title.lower() or query_lower in track.artist.lower() or
                    query_lower in track.album.lower() or query_lower in track.genre.lower()):
                result = item.to_dict()
                result['queue_index'] = idx
                result['is_current'] = (idx == queue.current_position)
                results.append(result)

        return results

    def filter_queue_by_artist(self, queue_id: str, artist: str):
        queue = self.get_queue(queue_id)
        if not queue:
            return []

        results = []
        for idx, item in enumerate(queue.items):
            if item.track.artist.lower() == artist.lower():
                result = item.to_dict()
                result['queue_index'] = idx
                result['is_current'] = (idx == queue.current_position)
                results.append(result)

        return results

    # EndRegion

    # Region statistcs
    def get_queue_stats(self, queue_id: str) -> Dict[str, Any]:
        queue = self.get_queue(queue_id)
        if not queue: return {}

        return queue.get_stats()

    def get_overall_stats(self) -> Dict[str, Any]:
        total_tracks = 0
        total_played = 0
        total_duration = 0
        total_play_count = 0

        for queue in self._queues.values():
            total_tracks += len(queue.items)
            total_played += sum(1 for item in queue.items if item.played)
            total_duration += sum(item.track.duration for item in queue.items)
            total_play_count += sum(item.play_count for item in queue.items)

        return {
            "total_queues": len(self._queues),
            "total_tracks": total_tracks,
            "total_played": total_played,
            "total_duration": total_duration,
            "total_play_count": total_play_count
        }

    # EndRegion
