import time
import threading
import numpy as np
import queue


data_ready = threading.Condition()


class AudioProcessorThread(threading.Thread):
    def __init__(self, engine, buffer_queue: queue.Queue, buffer_size, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.engine = engine
        self.buffer_queue = buffer_queue
        self.buffer_size = buffer_size
        self.running = True

    def run(self):
        while self.running:
            try:
                # Get active audio source
                if self.engine.mixer and self.engine.mixer.get_active_channel():
                    buffer = self.engine.mixer.get_next_buffer()
                elif self.engine._channel and self.engine._channel.playing:
                    buffer = self.engine._channel.get_next_buffer()
                else:
                    buffer = np.zeros((self.buffer_size, 2), dtype=np.float32)
                #print("Queue before put: ", self.buffer_queue.qsize())
                #if self.buffer_queue.qsize() < 4:
                self.buffer_queue.put(buffer)
                    #print("Queue after put: ", self.buffer_queue.qsize())
                    
                time.sleep(min(self.engine.latency, 0.01))
            except Exception as e:
                print(f"Audio processing error: {e}")
                break

    def stop(self):
        self.running = False


class CustomThread(threading.Thread):
    def __init__(self, target=None, name=None, daemon=False):
        """
        A custom threading class that utilizes native threading mechanisms
        without relying on a while loop.

        :param target: Target function to execute in the thread.
        :param name: Name of the thread.
        """
        super().__init__(name=name, daemon=daemon)
        self._stop_event = threading.Event()  # Event to signal thread termination
        self._target = target

    def stop(self):
        """Sets the stop event to signal the thread to stop execution."""
        self._stop_event.set()

    def stopped(self):
        """Returns whether the stop event has been triggered."""
        return self._stop_event.is_set()

    def run(self):
        """Override the run method to execute the target unless stopped."""
        if self._target and not self.stopped():
            self._target()