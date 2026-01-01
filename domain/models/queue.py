from typing import Optional
from dataclasses import dataclass
from domain.models.song import Track, TrackItem
from domain.models.base import BaseItemContainer
from domain.enums.playback import QueueStatus, RepeatMode


@dataclass
class MusicQueue(BaseItemContainer):
    status: QueueStatus = QueueStatus.STOPPED
    current_position: int = 0
    shuffle: bool = False
    repeat_mode: RepeatMode = RepeatMode.OFF

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
    def current_item(self) -> Optional[TrackItem]:
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
