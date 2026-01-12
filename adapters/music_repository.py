import sqlite3
import json
from typing import List, Optional, Dict, Tuple
from datetime import datetime
from core import logger
from domain.models.song import Track, TrackItem


class MusicRepository:
    def __init__(self, db_path: str):
        self.db_path = db_path
        self._init_db()

    def _get_connection(self):
        conn = sqlite3.connect(self.db_path, check_same_thread=False)
        conn.row_factory = sqlite3.Row
        return conn

    def _init_db(self):
        with self._get_connection() as conn:
            conn.execute("PRAGMA journal_mode=WAL;")
            conn.executescript("""
                CREATE TABLE IF NOT EXISTS tracks (
                    id TEXT PRIMARY KEY,
                    title TEXT, artist TEXT, album TEXT,
                    duration INTEGER, file_path TEXT UNIQUE, thumbnail BLOB,
                    genre TEXT, year TEXT, 
                    play_count INTEGER DEFAULT 0,
                    metadata TEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                );

                -- INDEXES for O(log n) search and sort speed
                CREATE INDEX IF NOT EXISTS idx_track_search ON tracks(title, artist, album);
                CREATE INDEX IF NOT EXISTS idx_track_date ON tracks(created_at);

                CREATE TABLE IF NOT EXISTS containers (
                    id TEXT PRIMARY KEY, name TEXT UNIQUE, type TEXT, created_at TEXT
                );

                CREATE TABLE IF NOT EXISTS container_items (
                    container_id TEXT, track_id TEXT, position INTEGER,
                    added_at TEXT, play_count INTEGER DEFAULT 0,
                    FOREIGN KEY(container_id) REFERENCES containers(id) ON DELETE CASCADE,
                    FOREIGN KEY(track_id) REFERENCES tracks(id) ON DELETE CASCADE
                );
            """)

    # read
    def get_all_tracks_no_blobs(self, limit=None) -> List[Track]:
        """
        Fetch library metadata without the heavy thumbnail BLOBs.
        :return: 
        """
        query = """
            SELECT id, title, artist, album, duration, file_path, 
                   genre, year, play_count, metadata 
            FROM tracks LIMIT ?
        """
        query_2 =  """
            SELECT id, title, artist, album, duration, file_path, 
                   genre, year, play_count, metadata 
            FROM tracks
        """
        with self._get_connection() as conn:
            if limit:
                cursor = conn.execute(query, (limit, ))
            else:
                cursor = conn.execute(query_2)

            return [self._map_row_to_track(row) for row in cursor.fetchall()]

    def search_tracks(self, query: str) -> List[Track]:
        """
        SQL-based search
        :param query: 
        :return: 
        """
        sql = """
            SELECT id, title, artist, album, duration, file_path, 
                   genre, year, play_count, metadata 
            FROM tracks 
            WHERE title LIKE ? OR artist LIKE ? OR album LIKE ?
            LIMIT 100
        """
        pattern = f"%{query}%"
        with self._get_connection() as conn:
            cursor = conn.execute(sql, (pattern, pattern, pattern))
            return [self._map_row_to_track(row) for row in cursor.fetchall()]

    def get_recent_tracks(self, limit: int) -> List[Track]:
        """
        Efficiently fetch only the latest entries
        :param limit: 
        :return: 
        """
        query = """
            SELECT id, title, artist, album, duration, file_path, 
                   genre, year, play_count, metadata 
            FROM tracks ORDER BY created_at DESC LIMIT ?
        """
        with self._get_connection() as conn:
            cursor = conn.execute(query, (limit,))
            return [self._map_row_to_track(row) for row in cursor.fetchall()]

    def get_tracks_by_ids(self, track_ids: List[str]) -> List[Track]:
        """
        Efficiently fetches a batch of tracks. Used for loading queue items
        or reconstructing a playlist view.
        :param track_ids:
        :return:
        """
        if not track_ids:
            return []

        placeholders = ', '.join(['?'] * len(track_ids))
        query = f"SELECT * FROM tracks WHERE id IN ({placeholders})"

        with self._get_connection() as conn:
            cursor = conn.execute(query, track_ids)
            return [self._map_row_to_track(row) for row in cursor.fetchall()]

    def get_albums(self) -> List[Dict]:
        """
        Retrieves a list of albums with artist info, track count,
        and a representative thumbnail for the grid view.
        """
        query = """
            SELECT 
                album, 
                artist, 
                COUNT(id) as track_count,
                thumbnail
            FROM tracks 
            WHERE album IS NOT NULL AND album != ''
            GROUP BY album, artist
            ORDER BY album ASC
        """
        with self._get_connection() as conn:
            cursor = conn.execute(query)
            return [dict(row) for row in cursor.fetchall()]

    def get_tracks_by_album(self, album_name: str, artist_name: str) -> List[Track]:
        """
        Fetches all tracks belonging to a specific album.
        Used when the user clicks an album card to 'Open' it.
        """
        query = "SELECT * FROM tracks WHERE album = ? AND artist = ? ORDER BY id"
        with self._get_connection() as conn:
            return [self._map_row_to_track(row) for row in conn.execute(query, (album_name, artist_name)).fetchall()]

    # write
    def bulk_upsert_tracks(self, tracks: List[Track]):
        """
        High-speed batch insertion. Handles thousands of tracks in one disk sync.
        Uses a transaction to ensure data integrity.
        :param tracks:
        :return:
        """
        if not tracks:
            return

        # Prepare the data tuples for executemany
        # extract the attributes from the Track objects
        data = []
        for t in tracks:
            # Standardized order matching the SQL columns
            data.append((
                t.id, t.file_path, t.title, t.artist, t.album,
                t.genre, t.duration, t.track_number, t.year,
                t.bitrate, t.file_extension, t.thumbnail,
                # Convert metadata dict to JSON string for storage
                json.dumps(t.metadata) if isinstance(t.metadata, dict) else t.metadata
            ))

        query = """
            INSERT INTO tracks (
                id, file_path, title, artist, album, 
                genre, duration, track_number, year, 
                bitrate, file_extension, thumbnail, metadata
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(id) DO UPDATE SET
                file_path=excluded.file_path,
                title=excluded.title,
                artist=excluded.artist,
                album=excluded.album,
                genre=excluded.genre,
                duration=excluded.duration,
                metadata=excluded.metadata,
                thumbnail=COALESCE(excluded.thumbnail, tracks.thumbnail)
        """

        with self._get_connection() as conn:
            try:
                conn.execute("BEGIN TRANSACTION")
                conn.executemany(query, data)
                conn.commit()
            except Exception as e:
                conn.rollback()
                raise e

    def save_tracks(self, tracks: List[Track]):
        query = """
            INSERT INTO tracks (id, title, artist, album, duration, file_path, thumbnail, genre, year, metadata, play_count)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, COALESCE((SELECT play_count FROM tracks WHERE id=?), 0))
            ON CONFLICT(id) DO UPDATE SET
                title=excluded.title,
                artist=excluded.artist,
                file_path=excluded.file_path,
                metadata=excluded.metadata
        """
        data = []
        for t in tracks:
            meta_json = json.dumps(t.metadata) if isinstance(t.metadata, dict) else "{}"
            data.append((
                t.id, t.title, t.artist, t.album, t.duration, t.file_path,
                t.thumbnail, t.genre, t.year, meta_json, t.id
            ))
        with self._get_connection() as conn:
            conn.executemany(query, data)
            conn.commit()

    # helpers
    def _map_row_to_track(self, row) -> Track:
        meta = json.loads(row['metadata']) if row['metadata'] else {}
        # thumbnail might be missing in 'light' queries
        thumb = row['thumbnail'] if 'thumbnail' in row.keys() else None

        return Track(
            id=row['id'], title=row['title'], artist=row['artist'],
            album=row['album'], duration=row['duration'],
            file_path=row['file_path'], thumbnail=thumb,
            genre=row['genre'], year=row['year'], metadata=meta
        )

    def get_all_paths(self) -> List[str]:
        with self._get_connection() as conn:
            # Normalized to file_path
            cursor = conn.execute("SELECT file_path FROM tracks")
            return [row[0] for row in cursor.fetchall()]

    def remove_tracks(self, paths: List[str]):
        with self._get_connection() as conn:
            conn.executemany("DELETE FROM tracks WHERE file_path = ?", [(p,) for p in paths])
            conn.commit()

    #Container and playlist operations
    def save_playlist_metadata(self, playlist_id: str, name: str) -> Tuple[bool, str]:
        """
        Creates or updates the playlist header.
        """
        query = """
            INSERT INTO containers (id, name, type, created_at) 
            VALUES (?, ?, 'playlist', ?)
            ON CONFLICT(id) DO UPDATE SET name=excluded.name
        """
        try:
            with self._get_connection() as conn:
                conn.execute(query, (playlist_id, name, datetime.now().isoformat()))
                conn.commit()
            return True, ''
        except Exception as e:
            logger.warning(f"[MusicRepo] Error inserting playlist container, error {e}")
            if "UNIQUE" in e:
                e = "Duplicate Playlist"

            return False, str(e)

    def add_tracks_to_playlist(self, playlist_id: str, items: List[TrackItem]):
        """
        Appends multiple tracks to a playlist, maintaining order.
        """
        if not items:
            return

        query = """
            INSERT INTO container_items (container_id, track_id, position, added_at, play_count) 
            VALUES (?, ?, ?, ?, ?)
        """

        with self._get_connection() as conn:
            #Find the current highest position to append correctly
            res = conn.execute(
                "SELECT MAX(position) FROM container_items WHERE container_id = ?",
                (playlist_id,)
            ).fetchone()

            current_max = res[0] if res[0] is not None else -1
            batch_data = []
            for i, item in enumerate(items):
                batch_data.append((
                    playlist_id,
                    item.track.id,
                    current_max + 1 + i,
                    item.added_at.isoformat() if item.added_at else datetime.now().isoformat(),
                    item.play_count
                ))

            conn.executemany(query, batch_data)
            conn.commit()

    def get_tracks_by_container(self, container_id: str) -> List[TrackItem]:
        """
        Reconstructs TrackItems by joining the tracks and container_items tables
        :param container_id:
        :return:
        """
        query = """
            SELECT t.*, ci.added_at, ci.play_count as local_play_count
            FROM tracks t
            JOIN container_items ci ON t.id = ci.track_id
            WHERE ci.container_id = ?
            ORDER BY ci.position
        """
        with self._get_connection() as conn:
            cursor = conn.execute(query, (container_id,))
            results = []
            for row in cursor.fetchall():
                # Map the track portion
                track = self._map_row_to_track(row)

                # Wrap in TrackItem with container-specific metadata
                item = TrackItem(
                    track=track,
                    added_at=datetime.fromisoformat(row['added_at']),
                    play_count=row['local_play_count']
                )
                results.append(item)
            return results

    def remove_track_from_container(self, container_id: str, track_id: str, position: Optional[int] = None):
        """
        :param container_id:
        :param track_id:
        :param position:
        :return:
        """
        query = "DELETE FROM container_items WHERE container_id = ? AND track_id = ?"
        params = [container_id, track_id]

        if position is not None:
            query += " AND position = ?"
            params.append(position)

        with self._get_connection() as conn:
            conn.execute(query, params)
            conn.commit()

    def get_tracks_by_container_light(self, container_id: str) -> List[TrackItem]:
        """
        Optimized join that skips the thumbnail BLOB.
        :param container_id: 
        :return: 
        """
        query = """
            SELECT t.id, t.title, t.artist, t.album, t.duration, t.file_path, 
                   t.genre, t.year, t.metadata, ci.added_at, ci.play_count as local_play_count
            FROM tracks t
            JOIN container_items ci ON t.id = ci.track_id
            WHERE ci.container_id = ?
            ORDER BY ci.position
        """
        with self._get_connection() as conn:
            cursor = conn.execute(query, (container_id,))
            items = []
            for row in cursor.fetchall():
                track = self._map_row_to_track(row)  # Map_row handles missing 'thumbnail' key
                items.append(TrackItem(
                    track=track,
                    added_at=datetime.fromisoformat(row['added_at']),
                    play_count=row['local_play_count']
                ))
            return items

    def remove_track_from_playlist(self, playlist_id: str, track_id: str, position: Optional[int] = None):
        """
        Removes a track and optionally re-indexes to close the gap.
        :param playlist_id:
        :param track_id:
        :param position:
        :return:
        """
        with self._get_connection() as conn:
            try:
                # Identify exactly which row to delete
                # Using position is safer in case the same song is in the playlist twice
                if position is not None:
                    conn.execute(
                        "DELETE FROM container_items WHERE container_id = ? AND track_id = ? AND position = ?",
                        (playlist_id, track_id, position)
                    )
                else:
                    # Fallback: remove all instances of this song from the playlist
                    conn.execute(
                        "DELETE FROM container_items WHERE container_id = ? AND track_id = ?",
                        (playlist_id, track_id)
                    )

                # Re-index, close the gap to keep positions sequential (0, 1, 2...)
                # This prevents "index out of bounds" errors in the UI later
                conn.execute("""
                    WITH Reindexed AS (
                        SELECT rowid, ROW_NUMBER() OVER (ORDER BY position) - 1 as new_pos
                        FROM container_items
                        WHERE container_id = ?
                    )
                    UPDATE container_items
                    SET position = (SELECT new_pos FROM Reindexed WHERE Reindexed.rowid = container_items.rowid)
                    WHERE container_id = ?
                """, (playlist_id, playlist_id))

                conn.commit()
            except Exception as e:
                conn.rollback()
                logger.error(f"DB: Failed to remove track from playlist: {e}")

    def get_playlist_name(self, playlist_id: str) -> str:
        """
        Retrieves the display name of a playlist from the containers table.
        :param playlist_id:
        :return:
        """
        query = "SELECT name FROM containers WHERE id = ?"
        with self._get_connection() as conn:
            row = conn.execute(query, (playlist_id,)).fetchone()

            return row['name'] if row else "Unknown Playlist"

    def get_all_playlists(self) -> list | None:
        """
        :return:
        """
        query = "SELECT id, name FROM containers WHERE type = 'playlist'"
        with self._get_connection() as conn:
            rows = conn.execute(query).fetchall()
            if rows:
                return [{'id': row[0], 'name': row[1]} for row in rows]
            else:
                return None

    def get_thumbnail_blob(self, track_id: str) -> Optional[bytes]:
        """
        Selective fetch of thumbnail to avoid overhead in list views.
        This is the counterpart to get_all_tracks_no_blobs
        :param track_id:
        """
        query = "SELECT thumbnail FROM tracks WHERE id = ?"
        with self._get_connection() as conn:
            row = conn.execute(query, (track_id,)).fetchone()
            if row and row[0]:
                return row[0]
            return None

