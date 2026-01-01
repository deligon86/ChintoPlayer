import math
import threading
import soundfile as sf
import numpy as np
import scipy.signal as sps
from fractions import Fraction

from adapters.audio_engine.errors import AudioEngineError
from core import logger


class CoreAudioChannel:
    def __init__(self, sample_rate=44100, buffer_size=512):
        self.file_path = ""
        self.buffer_size = buffer_size
        self.sample_rate = sample_rate
        self.audio_file = None  # Current audio file handle
        self.next_audio_file = None  # Next audio file handle for gapless playback
        self.current_is_mono = False  # Track if current file is mono
        self.next_is_mono = False  # Track if next file is mono
        self.resample_ratio = 1.0  # Target rate / file rate
        self.up_factor = 1  # For resample_poly: numerator
        self.down_factor = 1  # For resample_poly: denominator
        self.playing = False
        self.do_not_play = False
        self.loop = False
        self.volume = 0.5
        self.effects = []
        self.lock = threading.Lock()
        self.pan = 0.0
        self.on_playback_end = None
        self.paused = False
        self.fade_out_samples = 0 #(1500/1000) * sample_rate
        self.fade_in_samples = 0 #(2000/1000) * sample_rate
        self.fade_position = 0
        self._fade = False
        self.fade_type = 'exponential' # linear, exponetial
        self.file_length = 0.1
        self.latency = self.buffer_size // self.sample_rate * 1000

    def add_effects(self, effects:list):
        with self.lock:
            for effect in effects:
                if effect not in self.effects:
                    self.effects.append(effect)

    def load_file(self, file_path):
        """
        Load a new audio file for playback, closing any existing file
        :param file_path:
        :return:
        """
        with self.lock:
            try:
                self.fade_in_samples = (2000/1000) * self.sample_rate if self._fade else 0
                audio_file = sf.SoundFile(file_path, 'r')
                if self.audio_file is not None:
                    self.audio_file.close()
                self.audio_file = audio_file
                self.current_is_mono = self.audio_file.channels == 1
                self.do_not_play = False
                self.file_length = self.audio_file.frames // self.sample_rate

                # Determine resampling factors if the file's sample rate doesn't match.
                if self.audio_file.samplerate != self.sample_rate:
                    ratio = self.sample_rate / self.audio_file.samplerate
                    self.resample_ratio = ratio
                    frac = Fraction(self.sample_rate, self.audio_file.samplerate).limit_denominator(1000)
                    self.up_factor = frac.numerator
                    self.down_factor = frac.denominator
                    logger.info(
                        f"Warning: File sample rate {self.audio_file.samplerate} doesn't match target {self.sample_rate}. "
                        f"Resampling with ratio {self.resample_ratio:.5f} (up={self.up_factor}, down={self.down_factor})")
                else:
                    self.resample_ratio = 1.0
                    self.up_factor = 1
                    self.down_factor = 1
            except Exception as e:
                error = f"Error loading file {e}"
                self.do_not_play = True
                # self.audio_file = None
                logger.warning(error)
                return [AudioEngineError.CHANNEL_LOAD_ERROR, error]

    def queue_file(self, file_path):
        """
        Queue the next file for gapless playback
        :param file_path:
        :return: error or None
        """
        with self.lock:
            try:
                if self.next_audio_file is not None:
                    self.next_audio_file.close()
                self.next_audio_file = sf.SoundFile(file_path, 'r')
                self.next_is_mono = self.next_audio_file.channels == 1
                self.file_length = self.next_audio_file.frames // self.sample_rate
                #print("[+] Next file queued for gapless playback")
                return None
            except Exception as e:
                error = f"{AudioEngineError.CHANNEL_QUEUE_ERROR} Error queueing file: {e}"
                logger.warning(error)
                self.next_audio_file = None
                return [AudioEngineError.CHANNEL_QUEUE_ERROR, error]
    def start_fade_out(self, fade_time_ms):
        """
        :param fade_time_ms:
        :return:
        """
        with self.lock:
            self.fade_out_samples = int(fade_time_ms * self.sample_rate / 1000)
            self.fade_position = 0

    def start_fade_in(self, fade_time_ms):
        """
        :param fade_time_ms:
        :return:
        """
        with self.lock:
            self.fade_in_samples = int(fade_time_ms * self.sample_rate / 1000)
            self.fade_position = 0

    def _apply_fade(self, data):
        """
        Apply fade-in or fade-out to the audio data.
        :param data: audio samples
        :return:
        """
        
        if self.fade_in_samples > 0 :
            fade_scale = self.fade_position / self.fade_in_samples
            if self.fade_type == 'exponential':
                fade_scale = fade_scale ** 2
            data *= fade_scale
            self.fade_position += len(data)
            if self.fade_position >= self.fade_in_samples:
                self.fade_in_samples = 0
                self.fade_position = 0
            self._fade = False
        elif self.fade_out_samples > 0:
            fade_scale = 1.0 - (self.fade_position / self.fade_out_samples)
            if self.fade_type == 'exponential':
                fade_scale = fade_scale ** 2
            data *= fade_scale
            self.fade_position += len(data)
            if self.fade_position >= self.fade_out_samples:
                self.fade_out_samples = 0
                self.fade_position = 0
                # self.playing = False  # Stop playback after fade-out

        return data

    def _apply_effects(self, data):
        """
        :param data: audio samples
        :return:
        """
        if self.effects:
            out = np.zeros_like(data)
            for effect in self.effects:
                out += effect.process(data, self.sample_rate)
            #print(f"Processed: {out} original: {data}")
            return out
        else:
            return data

    def get_next_buffer(self):
        """
        Return a buffer of self.buffer_size samples (at the target sample rate).
        :return:
        """
        with self.lock:
            if not self.playing or self.audio_file is None or self.paused:
                return np.zeros((self.buffer_size, 2), dtype=np.float32)

            chunks = []
            total_output = 0

            # Loop until we've accumulated enough output samples.
            while total_output < self.buffer_size:
                out_frames_needed = self.buffer_size - total_output
                # If resampling, compute how many input frames are needed.
                if self.resample_ratio != 1.0:
                    in_frames_needed = int(math.ceil(out_frames_needed / self.resample_ratio))
                else:
                    in_frames_needed = out_frames_needed

                try:
                    data = self.audio_file.read(in_frames_needed, dtype='float32')
                except ValueError:
                    data = np.zeros((in_frames_needed, 2), dtype=np.float32)

                if len(data) > 0:
                    if self.current_is_mono:
                        data = np.tile(data, (1, 2))
                    # resample
                    if self.resample_ratio != 1.0:
                        data = sps.resample_poly(data, self.up_factor, self.down_factor, axis=0)
                    chunks.append(data)
                    total_output += len(data)
                else:
                    # End-of-file reached, switch to next file
                    if self.loop:
                        self.audio_file.seek(0)
                    elif self.next_audio_file is not None:
                        self.audio_file.close()
                        self.audio_file = self.next_audio_file
                        self.current_is_mono = self.next_is_mono
                        if self.audio_file.samplerate != self.sample_rate:
                            ratio = self.sample_rate / self.audio_file.samplerate
                            self.resample_ratio = ratio
                            frac = Fraction(self.sample_rate, self.audio_file.samplerate).limit_denominator(1000)
                            self.up_factor = frac.numerator
                            self.down_factor = frac.denominator
                        else:
                            self.resample_ratio = 1.0
                            self.up_factor = 1
                            self.down_factor = 1
                        self.next_audio_file = None
                        self.next_is_mono = False
                    else:
                        if self.audio_file:
                            self.audio_file.close()
                        self.audio_file = None
                        self.playing = False
                        # No more data: fill with silence.
                        zeros_needed = self.buffer_size - total_output
                        chunks.append(np.zeros((zeros_needed, 2), dtype=np.float32))
                        total_output = self.buffer_size
                        if self.on_playback_end:
                            self.on_playback_end(self)
                        break

            # Concatenate chunks and trim to exactly buffer_size samples.
            output = np.concatenate(chunks, axis=0)[:self.buffer_size]
            output = output * self.volume

            # Apply fades and effects.
            output = self._apply_fade(output)
            output = self._apply_effects(output)
            return output

    def set_volume(self, volume):
        """
        :param volume:
        :return:
        """
        with self.lock:
            self.volume = float(volume / 100)

    def set_position(self, pos):
        """
        :param pos:
        :return:
        """
        with self.lock:
            if self.audio_file is not None:
                sample_pos = int(pos * self.sample_rate)
                try:
                    self.audio_file.seek(sample_pos)
                except ValueError:
                    pass

    def get_position(self):
        """
        :return:
        """
        with self.lock:
            if self.audio_file is not None:
                return self.audio_file.tell() / self.sample_rate
            return 0.0

    def play(self):
        """
        :return:
        """
        with self.lock:
            if self.audio_file is not None and not self.do_not_play:
                self.playing = True
                self.paused = False

    def stop(self):
        """
        :return:
        """
        with self.lock:
            self.playing = False
            if self.audio_file is not None:
                self.audio_file.seek(0)
                self.audio_file.close()
                self.audio_file = None

    def pause(self):
        """
        :return:
        """
        with self.lock:
            self.paused = True

    def close(self):
        """
        Close any open file handles
        :return:
        """
        with self.lock:
            if self.audio_file is not None:
                self.audio_file.close()
            if self.next_audio_file is not None:
                self.next_audio_file.close()
