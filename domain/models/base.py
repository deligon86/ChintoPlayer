from dataclasses import dataclass, field
from datetime import datetime
from domain.models.song import TrackItem
from typing import List, Dict, Any


@dataclass
class BaseItemContainer:
    id: str
    name: str
    items: List[TrackItem] = field(default_factory=list)
    created_at: datetime = field(default_factory=datetime.now)
    metadata: Dict[str, Any] = field(default_factory=dict)
