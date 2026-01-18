import gc
import time
import queue
import threading
from typing import AnyStr, List

import numpy as np
import sounddevice as sd

from adapters.audio_engine.errors import AudioEngineError
from adapters.audio_engine.utils.threads import AudioProcessorThread, data_ready
from adapters.audio_engine.core.mixer import CoreMixer
from adapters.audio_engine.core.channel import CoreAudioChannel
from adapters.audio_engine.effects.effect import CoreAudioEffect
from core import logger


# engine
class CoreEngine:

    def __init__(self, sample_rate=44100, buffer_size=512, use_mixer=False):
        self.buffer_size = buffer_size
        self.sample_rate = sample_rate
        self.lock = threading.Lock()
        self.mixer = CoreMixer(sample_rate, buffer_size, self.end_event_emitted) if use_mixer else None
        self.output_stream = None
        self.latency = (buffer_size / self.sample_rate) * 1000

        self._sample_absolute = [0, 0]
        self._peak = 0

        self._channel = None
        self._end_event = 1  # 1 stopped 0, playing 2 paused
        self._volume = 60
        self._event_maps = {1: 'stop',
                            2: 'paused',
                            0: 'play'
                            }

        self.receive_audio_buffer = None
        self.buffer_queue = queue.Queue(maxsize=8)
        self.processor = None
        self._output_latency = 'low'
        self._startup_delay = 0.1
        self.effects = []
        # go ahead flag
        self.do_not_play = True

        # events
        self.end_event_handler = None
        self.playback_event_handler = None
        self.position_event_handler = None
        self.error_event_handler = None

        self.errors = []

    def register_end_event(self, handle):
        self.end_event_handler = handle

    def register_playback_event(self, handle):
        self.playback_event_handler = handle

    def register_position_event(self, handle):
        self.position_event_handler = handle

    def register_error_event(self, handle):
        self.error_event_handler = handle

    @property
    def sample_absolute_value(self):
        with self.lock:
            return self._sample_absolute

    @property
    def peak_value(self):
        with self.lock:
            return self._peak
    
    def add_effect(self, effect: CoreAudioEffect):
        self.effects.append(effect)
        if self._channel:
            self._channel.effects.append(effect)

    def add_error(self, error: list):
        """
        :param error: [AudioEngineError, error string]
        :return:
        """
        self.errors.append(error)
        if self.error_event_handler:
            self.error_event_handler(error)
        # keep only last 10
        self.errors = self.errors[:-10]

    def end_event_emitted(self, channel: CoreAudioChannel=None, value=False):
        """
        Used by mixer
        :param channel
        :param value:
        :return:
        """
        if value:
            if self.mixer.get_active_channel():
                self._set_end_event(0)
            else:
                self._set_end_event(1)

            if self.end_event_handler:
                self.end_event_handler(True)
    
    def is_playing(self):
        """
        :return:
        """
        with self.lock:
            return True if self._map_event(self._end_event) == "play" else False

    def load_file(self, path, channel:int=None):
        """
        :param path:
        :param channel: channel index if using mixer
        :return:
        """
        if self.mixer:
            if not self.mixer.channels:
                channel = self._create_channel()
            self.do_not_play = self.mixer.load_file_to_channel(channel, path)
        else:
            # use channel
            channel = self._create_channel(True)
            error = channel.load_file(path)
            if error:
                self.add_error(error)

            self.do_not_play = channel.do_not_play

    def play(self, channel=None):
        """
        Start streaming
        :param channel channel index
        :return:
        """
        if self.do_not_play:
            err = [AudioEngineError.PLAYBACK_ERROR, self.last_error()]
            self.add_error(err)
            return None

        if self.is_playing():
            self.shutdown()

        # Start audio processing and streaming
        self.start_stream()

        # Activate playback
        with self.lock:
            # check if mixer is initialized and channel is provided and play that channel
            if self.mixer and channel is not None:
                self.mixer.add_effects(self.effects, channel)
                self.mixer.play_channel(channel)
            elif self._channel:
                self._channel.add_effects(self.effects)
                self._channel.playing = True
                self._channel.on_playback_end = self.handle_playback_end
            else:
                # mixer is initialized but channel index is set to None, play loaded channels only
                channels = self.mixer.get_loaded_channels()
                for channel in channels:
                    channel.add_effects(self.effects)
                    channel.playing = True
            self._set_end_event(0)
        return True

    def start_stream(self):
        if self.output_stream:
            self.shutdown()

        # Create and start processor first
        self.processor = AudioProcessorThread(self, self.buffer_queue, self.buffer_size)
        self.processor.start()

        # Let buffer accumulate before starting output
        time.sleep(self._startup_delay)

        self.output_stream = sd.OutputStream(
            samplerate=self.sample_rate,
            channels=2,
            blocksize=self.buffer_size,
            callback=self._audio_callback,
            dtype="float32",
            latency=self._output_latency
        )
        self.output_stream.start()

    def _audio_callback(self, outdata, frames, time, status):
        #with data_ready:
        if not self.buffer_queue.empty():
            data = self.buffer_queue.get_nowait()
            outdata[:] = data
        else:
            logger.warning("Queue empty")
            outdata[:] = np.zeros((self.buffer_size, 2), dtype=np.float32)
        if self.receive_audio_buffer:
            self.send_buffer(outdata)

        # send the position, will be using only channel no mixer here
        if self.position_event_handler:
            self.position_event_handler(self.get_pos(), self.get_file_length())

    def send_buffer(self, buffer):
        self.receive_audio_buffer(buffer)

    def _create_channel(self, set_channel=False):
        channel = CoreAudioChannel(self.sample_rate, self.buffer_size)
        if self.mixer:
            self.mixer.add_channel(channel)
        else:
            channel.on_playback_end = self.handle_playback_end
        # set channel if mixer is not initialized
        if set_channel and not self.mixer:
            self._channel = channel

        self.set_volume(self._volume)
        return channel

    def handle_playback_end(self, channel):
        channel.playing = False
        channel.position = 0
        if not self.mixer:
            # avoid setting this if mixer is initialized as it takes care of this
            self._set_end_event(1)
        # self._channel = channel
        if self.end_event_handler:
            self.end_event_handler(True)
    
    def get_pos(self, channel=None):
        """
        For backward compatibility
        :param channel:
        :return:
        """
        if self.mixer:
            return self.mixer.get_pos(channel)
        
        return self._channel.get_position()

    def get_file_length(self, channel:int=None):
        """
        Get the current file length
        :param channel: channel index if using a mixer
        :return:
        """
        if self.mixer and channel is not None:
            return self.mixer.get_file_length(channel)
        else:
            return self._channel.file_length

    def clear_channels(self):
        if self.mixer:
            self.mixer.clear_channels()

    def pause(self, channel:int=None):
        if self.mixer:
            self.mixer.pause(channel)
        else:
            if self._channel:
                self._channel.paused = True
                self._set_end_event(1)
    
    def queue_file(self, file, channel:CoreAudioChannel|int=None):
        """
        Queue next file for gapless playback
        :param file:
        :param channel:
        :return:
        """
        if self.mixer:
            self.mixer.queue_to_channel(channel=channel, file=file)
        else:
            error = self._channel.queue_file(file)
            if error:
                self.add_error(error)

    def resume(self, channel:int=None):
        if self.mixer:
            self.mixer.resume(channel)
            self._set_end_event(0)
        else:
            if self._channel:
                self._channel.paused = False
                self._set_end_event(0)
    
    def stop(self, shutdown=False):
        if self.mixer:
            self.mixer.stop()
        else:
            if self._channel.playing:
                self._channel.playing = False
        if shutdown:
            self.shutdown()

    def set_volume(self, volume, channel: CoreAudioChannel|int=None):
        """
        Set volume in range 1 - 120 max
        :param volume:
        :param channel:
        :return:
        """
        if volume > 120:
            volume = 120

        volume /= 120

        self._volume = volume
        if self.mixer:
            self.mixer.set_volume(volume, channel)
        else:
            if self._channel:
                self._channel.set_volume(volume)

    def _set_end_event(self, val):
        self._end_event = val
        #if self.end_event_handler:
        #    self.end_event_handler(True self._map_event(val) != "play" else False)

    def _map_event(self, event):
        return self._event_maps.get(event)

    def last_error(self):
        """
        Get the latest error in place
        :return:
        """
        return self.errors[-1] if self.errors else None

    def shutdown(self):
        if self.output_stream:
            self.output_stream.stop()
            self.output_stream.close()
            self.output_stream = None
        if self.processor:
            self.processor.stop()
            # self.processor.join()

        while not self.buffer_queue.empty():
            try:
                self.buffer_queue.get_nowait()
            except queue.Empty:
                break

        gc.collect()
