import os
from adapters.media_scanner import MediaScanner
from adapters.audio_engine_service import AudioEngineService
from adapters.music_repository import MusicRepository
from core.constants.events import MediaScannerEvent, LibraryEvent, PlaybackEngineEvent
from core.event_bus import EventBus
from core.event_debugger import EventDebugger
from core.scheduler import Scheduler
from domain.enums.media_scanner import ScannerScanMode
from domain.queue_manager import QueueManager
from domain.library_manager import LibraryManager
from pathlib import Path


library_loaded = False

def library_updated_event(loaded):
    global library_loaded
    print("Library loaded: ", loaded)
    library_loaded = loaded

def scan_progress_log(payload):
    print(f"\rScanner progress: Current - {payload['file']} Total - {payload['count']}", end="", flush=True)

def scan_error(exception):
    print("[+]Scanner error: ", exception)


def bootstrap():

    db_path = Path(os.getcwd()) / 'assets/db'
    if not db_path.exists():
        os.makedirs(db_path, exist_ok=True)

    scheduler = Scheduler()
    # Infrastructure
    db_path = os.path.join(os.getcwd(), db_path/ "library.db")
    bus = EventBus()

    debugger = EventDebugger()
    bus.add_event_debugger(debugger)

    # Persistence layer
    repo = MusicRepository(db_path)

    # Domain manager
    queue_manager = QueueManager(bus)

    # LibraryManager coordinates cross-manager logic and scanner events
    library_manager = LibraryManager(repo, bus)

    # Initialize hardware/IO Adapters
    scanner = MediaScanner(bus, scheduler=scheduler)
    audio_engine = AudioEngineService(bus)

    print("Init bootstrap")

    return {
        "bus": bus,
        "repo": repo,
        "scanner": scanner,
        "queue": queue_manager,
        "scheduler": scheduler,
        "library": library_manager,
        "audio_service": audio_engine,
    }


if __name__ == "__main__":
    app_context = bootstrap()

    # register events
    app_context['bus'].subscribe(LibraryEvent.LIBRARY_READY, library_updated_event)
    # app_context['bus'].subscribe(MediaScannerEvent.SCANNER_PROGRESS, scan_progress_log)
    app_context['bus'].subscribe(MediaScannerEvent.SCANNER_ERROR, scan_error)

    # Start a scan if first time
    #app_context["bus"].publish(MediaScannerEvent.SCANNER_START, {
    #    'mode': ScannerScanMode.SINGLE, 'payload': Path(os.path.expanduser('~')) / 'Music'
    #})
    loaded = False
    # if second time and database is populated
    #app_context['bus'].publish(LibraryEvent.LIBRARY_READY, True)

    # Keep the main thread alive if using background workers
    try:
        import time
        while True:
            if library_loaded:
                if not loaded:
                    container = app_context['library'].get_queue_manager_context()
                    app_context['queue'].load_container(container)
                    loaded = True
            time.sleep(1)
    except KeyboardInterrupt:
        print("\nShutting down...")
        app_context['bus'].publish(PlaybackEngineEvent.KILL, -100083)  # use a random number for now

