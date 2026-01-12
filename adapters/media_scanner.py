import os
import uuid
from typing import List
from core import logger
from domain.models.song import Track
from core.utility.tag_reader import TagReader
from domain.enums.media_scanner import ScannerState, ScannerScanMode
from core.constants.events import MediaScannerEvent


class MediaScanner:
    extensions = ["mp4", "mp3"]

    def __init__(self, event_bus, extensions: List[str] = None, music_directories: List[str] = None, scheduler=None):
        self.bus = event_bus
        self.status: ScannerState = ScannerState.STOP
        self.bus.subscribe(MediaScannerEvent.SCANNER_START, self.receive_scan_events)

        # Clean extensions
        if extensions:
            valid_exts = [ext for ext in extensions if ext in self.extensions]
            if len(valid_exts) != len(extensions):
                logger.warning(f"[Media Scanner] Removed unsupported extensions")
            self.extensions = valid_exts

        self._history = []
        self._scan_job_id = "media_unique_scan_job"
        self._scan_delay = 5
        self._scheduler = scheduler
        self._music_directories = []
        self._to_be_scanned = []
        self.add_directories(music_directories)

    def add_scheduler(self, scheduler):
        """
        Add the task scheduler
        :param scheduler:
        :return:
        """
        self._scheduler = scheduler

    @property
    def music_dirs(self):
        return self._music_directories

    def add_directory(self, directory: str):
        """
        Add individual directory paths
        :param directory:
        :return:
        """
        if directory not in self._to_be_scanned:
            self._to_be_scanned.append(directory)
            logger.info(f"[Media Scanner] Added a directory to be scanned")
            # schedule scan
            self.schedule_scan(self._scan_delay)

    def add_directories(self, directories: List[str]):
        """
        Add multiple directories at once
        :param directories:
        :return:
        """
        if directories:
            changed = False
            for directory in directories:
                if directory not in self._to_be_scanned:
                    self._to_be_scanned.append(directory)
                    changed = True
            logger.info(f"[Media Scanner] Added directories to be scanned.")

            if changed:
                # schedule scan
                self.schedule_scan(self._scan_delay)

    def scan(self, *args):
        """
        Perform scan
        :param args:
        :return:
        """

        def get_count(directories:list):
            logger.info("[Media Scanner] Counting objects")
            count = 0
            for d in directories:
                for r, d_, f in os.walk(d):
                    count += len([file for file in f])

            return count

        if self.status == ScannerState.SCAN:
            logger.warning(f"[Media Scanner] Scanner already active, cannot scan")
            return

        try:
            self.status = ScannerState.SCAN
            self.bus.publish(MediaScannerEvent.SCANNER_STARTED, self._to_be_scanned)

            scanned = []
            logger.info("[Media Scanner] Start scanning for media")
            snap_directories = self._to_be_scanned.copy()

            total = get_count(snap_directories)
            current = 1
            for directory in snap_directories:
                for root, _, files in os.walk(directory):
                    for file in files:
                        if any(file.endswith(f".{ext.lower()}") for ext in self.extensions):
                            file_path = os.path.join(root, file)
                            tag = TagReader(path=file_path, autoextract=True)
                            track = Track(id=str(uuid.uuid4()), title=tag.title, artist=tag.artist, album=tag.album,
                                          duration=tag.file_length, file_path=tag.song_path, genre=tag.genre,
                                          year=tag.year, thumbnail=tag.raw_image_data, metadata={'track_no': tag.track_no,
                                                                                                 'producer': tag.producer})
                            scanned.append(track)
                            #Emit individual files for real-time progress
                            self.bus.publish(MediaScannerEvent.SCANNER_PROGRESS, {"file": file_path, "count": total})
                        current += 1

            # save directories
            for directory in snap_directories:
                if directory not in self._music_directories:
                    self._music_directories.append(directory)

            # clear to be scanned
            for directory in snap_directories:
                if directory in self._to_be_scanned:
                    self._to_be_scanned.remove(directory)
            logger.info("[Media Scanner] Finished scanning")
            self.bus.publish(MediaScannerEvent.SCANNER_FINISHED, scanned)

        except Exception as e:
            logger.error(f"[Media Scanner] Scan failed: {e}")
            self.status = ScannerState.STOP
            self.bus.publish(MediaScannerEvent.SCANNER_ERROR, e)

        finally:
            self.status = ScannerState.COMPLETE

    def schedule_scan(self, after: int):
        """
        Schedule to scan after some time
        :param after:
        :return:
        """
        if not self._scheduler:
            logger.critical(f"[Media Scanner] Cannot schedule scan, scheduler not initialized")
            return

        # If already scanning, push the next scan back
        if self.status == ScannerState.SCAN:
            after += 60

        self._scheduler.add_job(self._scan_job_id, self.scan, after, (), unique=True)
        logger.info(f"[Media Scanner] Scheduled scanning after {after} seconds")

    def receive_scan_events(self, payload: dict | None = None):
        """
        :param payload:
        :return:
        """
        if payload:
            msg = f"[Media Scanner] Scan payload: {payload}"
            logger.info(msg)
            mode = payload.get('mode')
            if mode == ScannerScanMode.SINGLE:
                self.add_directory(payload.get('payload'))
            else:
                self.add_directories(payload.get('payload'))
        else:
            # use common directories
            self.add_directories(self._get_common())

    def _get_common(self):
        common = ["Music"]
        directories = []
        for c in common:
            directories.append(os.path.join(os.path.expanduser('~'), c))

        return directories
