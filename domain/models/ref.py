from enum import Enum
from datetime import datetime
from dataclasses import dataclass, field
from typing import (
    Optional, Any, List, Dict
)


class QueueStatus(Enum):
    ACTIVE = "active"
    PAUSED = "paused"
    COMPLETED = "completed"
    STOPPED = "stopped"


class RepeatMode(Enum):
    ONE = "one"
    OFF = "off"
    ALL = "all"
    ONCE = "once"


@dataclass
class Track:
    id: str
    title: str
    artist: str
    album: str
    duration: int
    file_path: str
    stream_url: str | None
    thumbnail: str | None
    genre: str
    year: str
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self):
        return {
            "id": self.id,
            "title": self.title,
            "artist": self.artist,
            "album": self.album,
            "duration": self.duration,
            "file_path": self.file_path,
            "stream_url": self.stream_url,
            "thumbnail": self.thumbnail,
            "genre": self.genre,
            "year": self.year,
            "metadata": self.metadata
        }

    @classmethod
    def from_recycle_view_data(cls, recycle_data: Dict[str, Any]):
        return cls(
            id=recycle_data['song_id'],
            title=recycle_data['title'],
            artist=recycle_data['artist'],
            album=recycle_data['album'],
            duration=recycle_data['file_length'],
            file_path=recycle_data['path'],
            thumbnail=recycle_data['image'],
            genre=recycle_data['genre'],
            year=recycle_data['year']
        )


@dataclass
class QueueItem:
    track: Track
    added_at: datetime = field(default_factory=datetime.now)
    played: bool = False
    play_count: int = 0
    user_rating: int | None = None
    is_current: bool = False

    def to_dict(self):
        return {
            "added_at": self.added_at,
            "played": self.played,
            "play_count": self.play_count,
            "user_rating": self.user_rating,
            "is_current": self.is_current
        }


@dataclass
class MusicQueue:
    id: str
    name: str
    items: List[QueueItem] = field(default_factory=list)
    created_at: datetime = field(default_factory=datetime.now)
    status: QueueStatus = QueueStatus.STOPPED
    current_position: int = 0
    shuffle: bool = False
    repeat_mode: RepeatMode = RepeatMode.OFF
    metadata: Dict[str, Any] = field(default_factory=dict)

    @property
    def total_duration(self):
        return sum(item.track.duration for item in self.items)

    @property
    def remaining_duration(self):
        unplayed = self.items[self.current_position]
        return sum(item.track.duration for item in unplayed)

    @property
    def current_track(self) -> Optional[Track]:
        if self.items and 0 <= self.current_position < len(self.items):
            return self.items[self.current_position].track
        return None

    @property
    def current_item(self) -> Optional[QueueItem]:
        if self.items and 0 <= self.current_position < len(self.items):
            return self.items[self.current_position]
        return None

    def get_stats(self):
        return {
            "name": self.name,
            "total_tracks": len(self.items),
            "played_tracks": sum(1 for item in self.items if item.played),
            "total_duration": self.total_duration,
            "current_position": self.current_position,
            "shuffle": self.shuffle,
            "repeat_mode": self.repeat_mode,
            "status": self.status.value
        }


import uuid
import random
from kivy.clock import Clock
from kivy.event import EventDispatcher
from kivy.properties import (
    StringProperty, NumericProperty,
    BooleanProperty, ListProperty,
    ObjectProperty
)
from model.queue_model import (
    QueueItem, MusicQueue, Track,
    QueueStatus, RepeatMode
)
from typing import (
    List, Dict, Optional,
    Any
)


class QueueEvent(EventDispatcher):
    queue_created = StringProperty()  # queue id
    queue_deleted = StringProperty()  # queue name
    queue_updated = StringProperty()  # queue id
    queue_activated = StringProperty()  # queue id
    queue_item_added = ListProperty()  # queue name, queue item
    queue_item_removed = ListProperty()  # queue name, queue item
    current_track_changed = StringProperty()  # queue id
    shuffle_changed = BooleanProperty()
    repeat_mode_changed = StringProperty()

    def __init__(self, **kwargs):
        super().__init__(**kwargs)


class QueueManager:
    event = QueueEvent()

    def __init__(self):
        self._queues: Dict[str, MusicQueue] = {}
        self._active_queue_id = None
        self._history = []
        self._shuffled_indices: Dict[str, List[int]] = {}

    def create_queue(self, name: str, items: List[Track] = None, shuffle: bool = False,
                     repeat_mode: RepeatMode = RepeatMode.OFF,
                     metadata: Dict[str, Any] = None, make_active: bool = False):
        queue_id = str(uuid.uuid4())
        queue_items = [QueueItem(track=track) for track in (items or [])]
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

        Clock.schedule_once(lambda dt: self.event.dispatch('queue_created', queue_id))
        return queue

    def create_queue_from_recycle_view(self, name: str, data: List[Dict[str, Any]], shuffle: bool = False,
                                       repeat_mode: RepeatMode = RepeatMode.OFF, make_active: bool = False):
        """
        Create queue from kivymd recycle view
        :param name:
        :param data:
        :return:
        """
        items = []
        for item_data in data:
            # format only the required
            items.append(Track.from_recycle_view_data(item_data))

        self.create_queue(name=name, items=items, shuffle=shuffle, repeat_mode=repeat_mode, make_active=make_active)

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

            Clock.schedule_once(lambda dt: self.event.dispatch('queue_deleted', self.get_queue_name(queue_id)))
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

            Clock.schedule_once(lambda dt: self.event.dispatch('queue_activated', queue_id))
            if old_active:
                Clock.schedule_once(lambda dt: self.event.dispatch('queue_updated', old_active))

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
                item = QueueItem(track=track)
                if position is not None and 0 <= position <= len(queue.items):
                    queue.items.insert(position, item)
                else:
                    queue.items.append(item)
                position = position + 1 if position is not None else None

            if queue.shuffle:
                self._generate_shuffle_order(queue_id)

            Clock.schedule_once(lambda dt: self.event.dispatch('queue_item_added', queue_id))
            Clock.schedule_once(lambda dt: self.event.dipatch('queue_update', queue_id))

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

            Clock.schedule_once(lambda dt: self.event.dispatch('queue_item_removed', [queue_id, queue_item]))
            Clock.schedule_once(lambda dt: self.event.dispatch('queue_updated', queue_id))
            if any(idx == queue.current_position for idx in indices):
                Clock.schedule_once(lambda dt: self.event.dispatch('current_track_changed', queue_id))

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

            Clock.schedule_once(lambda dt: self.event.dispatch('queue_updated', queue_id))
            return queue
        return None

    def clear_queue(self, queue_id: str) -> bool:
        queue = self.get_queue(queue_id)
        if queue:
            queue.items.clear()
            queue.current_position = 0
            if queue.shuffle:
                self._shuffled_indices[queue_id] = []

            Clock.schedule_once(lambda dt: self.event.dispatch('queue_updated', queue_id))
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

        if queue.repeat_mode == RepeatMode.ALL and current_idx >= len(queue.items) - 1:
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

        if queue.repeat_mode == RepeatMode.ALL and current_idx == len(queue.items) - 1:
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

            Clock.schedule_once(lambda dt: self.event.dispatch('current_track_changed', queue_id))
            Clock.schedule_once(lambda dt: self.event.dispatch('queue_updated', queue_id))

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

            Clock.schedule_once(lambda dt: self.event.dispatch('shuffle_changed', True))
            Clock.schedule_once(lambda dt: self.event.dispatch('queue_updated', queue_id))

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
            queue.repeat_mode = mode.value()
            Clock.schedule_once(lambda dt: self.event.dispatch('repeat_mode_changed', mode.value()))
            Clock.schedule_once(lambda dt: self.event.dispatch('queue_updated', queue_id))
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
