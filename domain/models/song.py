from dataclasses import dataclass, field
from typing import Dict, Any
from datetime import datetime


@dataclass
class Track:
    id: str
    title: str
    artist: str
    album: str
    duration: int
    file_path: str
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
            "thumbnail": self.thumbnail,
            "genre": self.genre,
            "year": self.year,
            "metadata": self.metadata
        }


@dataclass
class TrackItem:
    track: Track
    added_at: datetime = field(default_factory=datetime.now)
    played: bool = False
    play_count: int = 0
    is_current: bool = False

    def to_dict(self):
        return {
            "added_at": self.added_at,
            "played": self.played,
            "play_count": self.play_count,
            "is_current": self.is_current
        }
