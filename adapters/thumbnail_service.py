import io
import threading
from PIL import Image
from typing import Tuple
from collections import OrderedDict
from concurrent.futures import ThreadPoolExecutor
from core.constants.events import ThumbnailEvent


class ThumbnailService:
    def __init__(self, repo, event_bus, max_items: int = 200, target_size: Tuple[float, float] = (600, 600)):
        """
        Thumbnail processing, saving and retrieval
        :param repo:
        :param event_bus:
        :param max_items:
        :param target_size:
        """
        self._repo = repo
        self._bus = event_bus
        self._max_items = max_items
        self._target_size = target_size

        self._cache: OrderedDict[str, bytes] = OrderedDict()
        self._lock = threading.Lock()
        self._executor = ThreadPoolExecutor(max_workers=1)

    def process_and_save(self, track_id: str, raw_data: bytes):
        """
        Downsamples raw image data before storage.
        This is the most critical step for long-term performance.
        :param track_id:
        :param raw_data:
        :return
        """

        def _task():
            try:
                processed_data = self._downsample(raw_data)
                self._repo.update_thumbnail(track_id, processed_data)

                with self._lock:
                    self._update_cache(track_id, processed_data)

                self._bus.publish(ThumbnailEvent.THUMBNAIL_UPDATED, track_id)
            except Exception as e:
                print(f"Thumbnail processing failed for {track_id}: {e}")

        self._executor.submit(_task)

    def _downsample(self, raw_data: bytes) -> bytes:
        """
        Resizes image to target_size and converts to optimized JPEG/WebP
        :param raw_data:
        :return: Image bytes
        """
        img = Image.open(io.BytesIO(raw_data))

        # Convert to RGB to ensure compatibility (removes transparency/alpha)
        if img.mode in ("RGBA", "P"):
            img = img.convert("RGB")

        img.thumbnail(self._target_size, Image.Resampling.LANCZOS)

        output = io.BytesIO()
        # Quality 85 is the good for size and visual fidelity
        img.save(output, format="JPEG", quality=85, optimize=True)
        return output.getvalue()

    def request_thumbnail(self, track_id: str):
        """
        UI will call this. Returns data via event bus
        :param track_id:
        :return:
        """
        with self._lock:
            if track_id in self._cache:
                self._cache.move_to_end(track_id)
                data = self._cache[track_id]
                self._bus.publish(ThumbnailEvent.THUMBNAIL_LOADED, {"id": track_id, "data": data})
                return

        self._executor.submit(self._async_fetch, track_id)

    def _async_fetch(self, track_id: str):
        blob = self._repo.get_thumbnail_blob(track_id)
        if blob:
            with self._lock:
                self._update_cache(track_id, blob)
            self._bus.publish(ThumbnailEvent.THUMBNAIL_LOADED, {"id": track_id, "data": blob})

    def _update_cache(self, track_id: str, data: bytes):
        """
        Internal helper to update cache
        :param track_id:
        :param data
        :return:
        """
        if len(self._cache) >= self._max_items:
            self._cache.popitem(last=False)
        self._cache[track_id] = data
