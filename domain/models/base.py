from dataclasses import dataclass, field
from datetime import datetime
from domain.models.song import TrackItem, Track
from typing import List, Dict, Any


@dataclass
class BaseItemContainer:
    id: str
    name: str
    items: List[TrackItem] = field(default_factory=list)
    created_at: datetime = field(default_factory=datetime.now)
    metadata: Dict[str, Any] = field(default_factory=dict)

    def get_index(self, track: Track):
        """
        Get index of this track
        :param track:
        :return:
        """
        index = 0
        for idx, item in enumerate(self.items):
            if item.track.id == track.id:
                index = idx
                break
        return index
