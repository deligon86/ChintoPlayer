import multiprocessing

import numpy as np
import sounddevice as sd
import soundfile as sf
import threading
import queue
import time
import gc
import os
import math
from fractions import Fraction
import scipy.signal as sps
from collections import deque

from scipy.signal import lfilter

os.environ['PYTHON_GIL'] = '0'


# from pydub import AudioSegment


class AudioProcessor(threading.Thread):
    def __init__(self, engine, buffer_queue, buffer_size=4096):
        super().__init__()
        self.engine = engine
        self.buffer_queue = buffer_queue
        self.buffer_size = buffer_size
        self.running = True
        self.daemon = True
        self.lock = threading.Lock()
        self.latency = engine.buffer_size / engine.sample_rate * 1000
        print("Latency: ", self.latency, "Ms")

    def target_func_mock(self):
        try:
            with self.lock:
                # Get active audio source
                if self.engine.mixer and self.engine.mixer.get_active_channel():
                    buffer = self.engine.mixer.get_next_buffer()
                elif self.engine._channel and self.engine._channel.playing:
                    buffer = self.engine._channel.get_next_buffer()
                else:
                    buffer = np.zeros((self.buffer_size, 2), dtype=np.float32)

                # Maintain buffer queue
                #if buffer.any():
                if self.buffer_queue.qsize() < 4:
                    self.buffer_queue.put(buffer)
                print("Audio Buffer: ", self.buffer_queue.qsize())
                #time.sleep(.01)
                #else:
                #    time.sleep(self.latency)  # Prevent buffer overflow
        except Exception as e:
            print(f"Audio processing error: {e}")
        

    def run(self):
        while self.running:
        #if self.running:
            self.target_func_mock()    

    def stop(self):
        self.running = False


class CustomThread(threading.Thread):
    def __init__(self, target=None, name=None):
        """
        A custom threading class that utilizes native threading mechanisms
        without relying on a while loop.

        :param target: Target function to execute in the thread.
        :param name: Name of the thread.
        """
        super().__init__(name=name)
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


class CoreEngine:

    def __init__(self, sample_rate=44100, buffer_size=512):
        self.buffer_size = buffer_size
        self.sample_rate = sample_rate
        self.lock = threading.Lock()
        self.mixer = None
        self.output_stream = None
        self._sample_absolute = [0, 0]
        self._peak = 0
        self._channel = None
        self._end_event = 1  # 1 stopped 0, playing 2 paused
        self._volume = 60
        self.receive_audio_buffer = None
        self.buffer_queue = queue.Queue(maxsize=8)
        self.processor = None
        self._output_latency = 'low'
        self._startup_delay = 0.1

    @property
    def SampleAbsoluteValue(self):
        with self.lock:
            return self._sample_absolute

    @property
    def PeakValue(self):
        with self.lock:
            return self._peak

    def end_event_emitted(self, value):
        """
        Used by mixer
        :param value:
        :return:
        """
        if value is True:
            if len(self.mixer.channels) == 0:
                # set end event
                self._set_end_event(1)

    def start_stream(self):
        if self.output_stream:
            self.shutdown()

        # Create and start processor first
        self.processor = AudioProcessor(self, self.buffer_queue, self.buffer_size)
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
        try:
            data = self.buffer_queue.get_nowait()
            outdata[:] = data
        except queue.Empty:
            outdata[:] = np.zeros((self.buffer_size, 2), dtype=np.float32)
        if self.receive_audio_buffer:
            self.send_buffer(outdata)

    def send_buffer(self, buffer):
        self.receive_audio_buffer(buffer)

    def _create_channel(self, set_channel=False):
        channel = CoreAudioChannel(self.sample_rate, self.buffer_size)
        if self.mixer:
            self.mixer.add_channel(channel)
        else:
            channel.on_playback_end = self.handle_playback_end
        if set_channel:
            if not self.mixer:
                self._channel = channel
        self.set_volume(self._volume)
        return channel

    def handle_playback_end(self, channel):
        # print("[+] Playback ended, removing channel")
        # self.remove_channel(channel)
        # Optionally, you can reuse the channel here if needed
        # Example: channel.playing = False; channel.position = 0
        channel.playing = False
        channel.position = 0
        self._set_end_event(1)
        self._channel = channel

    def clear_channels(self):
        if self.mixer:
            self.mixer.clear_channels()

    def pause(self):
        if self.mixer:
            self.mixer.pause_all()
        # self.shutdown()
        else:
            if self._channel:
                self._channel.paused = True
                self._set_end_event(1)

    def resume(self):
        if self.mixer:
            self.mixer.resume_all()
            self._set_end_event(0)
        # self.start_stream()
        else:
            if self._channel:
                self._channel.paused = False
                self._set_end_event(0)

    def set_volume(self, volume):
        self._volume = volume
        if self.mixer:
            self.mixer.set_volume(volume)
        else:
            if self._channel:
                self._channel.set_volume(volume)
    
    def queue_file(self, file):
        if not self.mixer:
            self._channel.queue_file(file)
        else:
            self.mixer.queue_next_file(file)

    def _set_end_event(self, val):
        self._end_event = val

    def shutdown(self):
        if self.output_stream:
            self.output_stream.stop()
            self.output_stream.close()
            self.output_stream = None
        if self.processor:
            self.processor.stop()
            self.processor.join()
        self.buffer_queue.queue.clear()
        gc.collect()


class CoreMixer:

    def __init__(self, sample_rate=44100, buffer_size=512, end_event_reached=None):
        self.buffer_size = buffer_size
        self.sample_rate = sample_rate
        self.channels = []
        self.lock = threading.Lock()
        self.end_event = 1  # 0 playing, 1 stopped, 2 paused
        self.emit_end_event = end_event_reached

    def add_channel(self, channel):
        with self.lock:
            self.channels.append(channel)
            # Set the callback for playback end
            channel.on_playback_end = self.handle_playback_end

    def handle_playback_end(self, channel):
        # print("[+] Playback ended, removing channel")
        # self.remove_channel(channel)
        # Optionally, you can reuse the channel here if needed
        # Example: channel.playing = False; channel.position = 0
        channel.playing = False
        channel.position = 0
        self.remove_channel(channel)
        self.emit_end_event(True)

    def is_playing(self):
        with self.lock:
            if any([channel for channel in self.channels if channel.playing]):
                return True
            else:
                return False

    def remove_channel(self, channel):
        with self.lock:
            if channel in self.channels:
                self.channels.remove(channel)

    def clear_channels(self):
        with self.lock:
            for channel in self.channels:
                channel.close()
            self.channels.clear()

    def pause_all(self):
        with self.lock:
            for channel in self.channels:
                channel.pause()
            # print("[+] All channels paused")

    def resume_all(self):
        with self.lock:
            for channel in self.channels:
                channel.resume()
            # print("[+] All channels resumed")

    def get_next_buffer(self):
        mix_buffer = np.zeros((self.buffer_size, 2), dtype=np.float32)
        with self.lock:
            for channel in self.channels:
                if channel.playing:
                    data = channel.get_next_buffer()
                    mix_buffer += data

        return np.clip(mix_buffer, -1.0, 1.0)

    def set_volume(self, volume):
        with self.lock:
            for channel in self.channels:
                channel.set_volume(volume)

    def get_active_channel(self):
        """
        Ger channels
        :return:
        """
        with self.lock:
            active = []
            for channel in self.channels:
                if channel.playing:
                    active.append(channel)
            return active
    
    def queue_next_file(self, file):
        channels = self.get_active_channel()
        if channels:
            channels[0].queue_file(file)


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
        self.fade_out_samples = 0
        self.fade_in_samples = 0
        self.fade_position = 0
        self.fade_type = 'linear'

    def load_file(self, file_path):
        """Load a new audio file for playback, closing any existing file."""
        with self.lock:
            try:
                if self.audio_file is not None:
                    self.audio_file.close()
                print("File: ", file_path)
                self.audio_file = sf.SoundFile(file_path, 'r')
                self.file_length = self.audio_file.frames // self.sample_rate
                self.current_is_mono = self.audio_file.channels == 1
                self.do_not_play = False
                # Determine resampling factors if the file's sample rate doesn't match.
                if self.audio_file.samplerate != self.sample_rate:
                    ratio = self.sample_rate / self.audio_file.samplerate
                    self.resample_ratio = ratio
                    frac = Fraction(self.sample_rate, self.audio_file.samplerate).limit_denominator(1000)
                    self.up_factor = frac.numerator
                    self.down_factor = frac.denominator
                    print(
                        f"Warning: File sample rate {self.audio_file.samplerate} doesn't match target {self.sample_rate}. "
                        f"Resampling with ratio {self.resample_ratio:.5f} (up={self.up_factor}, down={self.down_factor})")
                else:
                    self.resample_ratio = 1.0
                    self.up_factor = 1
                    self.down_factor = 1
            except Exception as e:
                print(f"Error loading file: {e}")
                self.audio_file = None
                self.do_not_play = True

    def queue_file(self, file_path):
        """Queue the next file for gapless playback."""
        with self.lock:
            try:
                if self.next_audio_file is not None:
                    self.next_audio_file.close()
                self.next_audio_file = sf.SoundFile(file_path, 'r')
                self.file_length = self.next_audio_file.frames // self.sample_rate
                self.next_is_mono = self.next_audio_file.channels == 1
                print("[+] Next file queued for gapless playback")
            except Exception as e:
                print(f"Error queuing file: {e}")
                self.next_audio_file = None

    def start_fade_out(self, fade_time_ms):
        with self.lock:
            self.fade_out_samples = int(fade_time_ms * self.sample_rate / 1000)
            self.fade_position = 0

    def start_fade_in(self, fade_time_ms):
        with self.lock:
            self.fade_in_samples = int(fade_time_ms * self.sample_rate / 1000)
            self.fade_position = 0

    def _apply_fade(self, data):
        """Apply fade-in or fade-out to the audio data."""
        if self.fade_out_samples > 0:
            fade_scale = 1.0 - (self.fade_position / self.fade_out_samples)
            if self.fade_type == 'exponential':
                fade_scale = fade_scale ** 2
            data *= fade_scale
            self.fade_position += len(data)
            if self.fade_position >= self.fade_out_samples:
                self.fade_out_samples = 0
                self.fade_position = 0
                self.playing = False  # Stop playback after fade-out

        elif self.fade_in_samples > 0:
            fade_scale = self.fade_position / self.fade_in_samples
            if self.fade_type == 'exponential':
                fade_scale = fade_scale ** 2
            data *= fade_scale
            self.fade_position += len(data)
            if self.fade_position >= self.fade_in_samples:
                self.fade_in_samples = 0
                self.fade_position = 0

        return data

    def _apply_effects(self, data):
        for effect in self.effects:
            data = effect.process(data, self.sample_rate)
        return data

    def get_next_buffer(self):
        """Return a buffer of self.buffer_size samples (at the target sample rate)."""
        with self.lock:
            if not self.playing or self.audio_file is None or self.paused:
                return np.zeros((self.buffer_size, 2), dtype=np.float32)

            chunks = []
            total_output = 0  # Count of output samples (after resampling)

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
                    # Convert mono to stereo if needed.
                    if self.current_is_mono:
                        data = np.tile(data, (1, 2))
                    # Resample using scipy.signal.resample_poly.
                    if self.resample_ratio != 1.0:
                        data = sps.resample_poly(data, self.up_factor, self.down_factor, axis=0)
                    chunks.append(data)
                    total_output += len(data)
                else:
                    # End-of-file reached.
                    if self.loop:
                        self.audio_file.seek(0)
                    elif self.next_audio_file is not None:
                        # Switch to next file.
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
                        self.next_loaded = True
                    else:
                        # No more data: fill with silence.
                        self.next_loaded = False
                        zeros_needed = self.buffer_size - total_output
                        chunks.append(np.zeros((zeros_needed, 2), dtype=np.float32))
                        total_output = self.buffer_size
                        if self.on_playback_end:
                            self.on_playback_end(self)
                        break

            # Concatenate chunks and trim to exactly buffer_size samples.
            output = np.concatenate(chunks, axis=0)[:self.buffer_size]

            # Apply fades and effects.
            output = self._apply_fade(output)
            output = self._apply_effects(output)
            return output * self.volume

    def set_volume(self, volume):
        with self.lock:
            self.volume = float(volume / 100)

    def set_position(self, pos):
        with self.lock:
            if self.audio_file is not None:
                sample_pos = int(pos * self.sample_rate)
                try:
                    self.audio_file.seek(sample_pos)
                except ValueError:
                    pass

    def get_position(self):
        with self.lock:
            if self.audio_file is not None:
                return self.audio_file.tell() / self.sample_rate
            return 0.0

    def play(self):
        with self.lock:
            if self.audio_file is not None and not self.do_not_play:
                self.playing = True
                self.paused = False

    def stop(self):
        with self.lock:
            self.playing = False
            if self.audio_file is not None:
                self.audio_file.seek(0)

    def pause(self):
        with self.lock:
            self.paused = True

    def close(self):
        """Close any open file handles."""
        with self.lock:
            if self.audio_file is not None:
                self.audio_file.close()
            if self.next_audio_file is not None:
                self.next_audio_file.close()


class CoreAudioEffect:

    def process(self, data, sample_rate, flat=False):
        raise NotImplementedError()


class EQEffect(CoreAudioEffect):

    def __init__(self, sample_rate=44100):
        self.sample_rate = sample_rate

        self.low_gain = 0.0
        self.mid_gain = 0.0
        self.high_gain = 0.0

        self.low_freq = 100
        self.mid_freq = 800
        self.high_freq = 2000
        self.q = 1.0

        self._update_filters()

        self.low_z = np.zeros((2, 2))
        self.mid_z = np.zeros((2, 2))
        self.high_z = np.zeros((2, 2))

    def _update_filters(self):
        self.low_b, self.low_a = self._butterworth_low_shelf(
            self.low_freq, self.low_gain
        )

    def _butterworth_low_shelf(self, freq, gain):
        A = 10 ** (gain / 40)
        omega = 2 * np.pi * freq / self.sample_rate
        sn = np.sin(omega)
        cs = np.cos(omega)
        beta = np.sqrt(A + A)

        b0 = A + ((A + 1) - (A - 1) * cs + beta * sn)
        b1 = 2 * A * ((A - 1) - (A + 1) * cs)
        b2 = A * ((A + 1) - (A - 1) * cs - beta * sn)
        a0 = (A + 1) + (A - 1) * cs + beta * sn
        a1 = -2 * ((A - 1) + (A + 1) * cs)
        a2 = (A + 1) * (A - 1) * cs - beta * sn

        return [b0 / a0, b1 / a0, b2 / a0], [1.0, a1 / a0, a2 / a0]

    def process(self, data, sample_rate, flat=False):
        if flat:
            return data
        processed = data.copy().astype(np.float64)
        for c in range(2):
            processed[:, c], self.mid_z[c] = lfilter(
                self.low_b, self.low_a, processed[:, c], zi=self.low_z[c]
            )

            # processed[:, c] = self._soft_clip(processed[:, c])
        return np.clip(processed, -1.0, 1.0).astype(np.float32)

    def _soft_clip(self, x):
        thresh = 0.95
        return np.where(
            np.abs(x) < thresh,
            x,
            np.sign(x) * (thresh + (1 - thresh) * np.tanh((np.abs(x) - thresh) /
                                                          (1 - thresh)))
        )


class UltraLightReverb(CoreAudioEffect):
    """
    Minimal Reverb Effect
    """

    def __init__(self, decay_time=1.0, wet=0.3, pre_delay=2, damping=0.2):
        super().__init__()
        # Parameters
        self.decay_time = decay_time  # Seconds
        self.wet = wet  # 0-1 wet/dry mix
        self.pre_delay = pre_delay  # Milliseconds
        self.damping = damping  # 0-1 (high-frequency attenuation)

        # Fixed delay line size (stereo)
        self.delay_samples = int(decay_time * 44100)  # Max delay time
        self.delay_buffer = np.zeros((2, self.delay_samples))
        self.delay_ptr = 0

        # Pre-delay buffer (stereo)
        self.pre_delay_samples = int(pre_delay * 44.1)
        self.pre_delay_buf = np.zeros((2, self.pre_delay_samples))
        self.pre_delay_ptr = 0

        # Damping filter (simple 1-pole lowpass)
        self.damping_filter = damping
        self.z = np.zeros(2)  # Filter state

    def process(self, data, sample_rate, flat=False):
        if flat or self.wet < 0.01:
            return data

        wet = self.wet
        dry = 1 - wet
        output = np.zeros_like(data)

        # Process each sample in block
        for i in range(data.shape[0]):
            # Input with pre-delay
            in_sample = data[i]

            # Write to pre-delay buffer
            self.pre_delay_buf[:, self.pre_delay_ptr] = in_sample
            delayed_in = self.pre_delay_buf[:,
                         (self.pre_delay_ptr - self.pre_delay_samples) % self.pre_delay_samples
                         ]
            self.pre_delay_ptr = (self.pre_delay_ptr + 1) % self.pre_delay_samples

            # Read from delay line
            read_ptr = (self.delay_ptr - self.delay_samples // 2) % self.delay_samples
            delayed = self.delay_buffer[:, read_ptr]

            # Apply damping filter
            for c in range(data.shape[1]):
                delayed[c] = self.damping_filter * delayed[c] + (1 - self.damping_filter) * self.z[c]
                self.z[c] = delayed[c]

            # Write to delay line
            self.delay_buffer[:, self.delay_ptr] = delayed_in + delayed * (0.97 ** (1 / self.decay_time))
            self.delay_ptr = (self.delay_ptr + 1) % self.delay_samples

            # Mix dry/wet
            output[i] = in_sample * dry + delayed * wet

        return output


class LiteReverb(CoreAudioEffect):
    def __init__(self, decay_time=1.5, wet=0.3, pre_delay=20, diffusion=0.7):
        super().__init__()
        # Parameters
        self.decay_time = decay_time  # Seconds
        self.wet = wet  # 0-1 wet/dry mix
        self.pre_delay = pre_delay  # Milliseconds
        self.diffusion = diffusion  # 0-1 echo density

        # Fixed architecture (4 comb + 2 allpass)
        self.comb_times = [29.7, 37.1, 43.7, 51.3]  # Prime numbers (ms)
        self.allpass_times = [5.0, 1.7]  # Milliseconds

        # Initialize buffers
        self._init_buffers()

    def _init_buffers(self):
        # Pre-delay buffer (stereo)
        self.pre_delay_samples = int(self.pre_delay * 44.1)
        self.pre_delay_buf = np.zeros((2, self.pre_delay_samples))
        self.pre_delay_ptr = 0

        # Comb filters (parallel)
        self.comb_buffers = [
            np.zeros((2, int(t * 44.1)))
            for t in self.comb_times
        ]
        self.comb_ptrs = [0] * 4

        # All-pass filters (series)
        self.allpass_buffers = [
            np.zeros((2, int(t * 44.1)))
            for t in self.allpass_times
        ]
        self.allpass_ptrs = [0] * 2

        # Feedback coefficients
        self.comb_feedback = 0.93 ** (1 / (self.decay_time * 4))

    def process(self, data, sample_rate, flat=False):
        if flat or self.wet < 0.01:
            return data

        wet = self.wet
        dry = 1 - wet
        output = np.zeros_like(data)

        # Process each sample in block
        for i in range(data.shape[0]):
            # Input with pre-delay
            in_sample = data[i]

            # Write to pre-delay buffer
            self.pre_delay_buf[:, self.pre_delay_ptr] = in_sample
            delayed_in = self.pre_delay_buf[:,
                         (self.pre_delay_ptr - self.pre_delay_samples) % self.pre_delay_samples
                         ]
            self.pre_delay_ptr = (self.pre_delay_ptr + 1) % self.pre_delay_samples

            # Parallel comb filters
            comb_sum = np.zeros(2)
            for n in range(4):
                buf = self.comb_buffers[n]
                ptr = self.comb_ptrs[n]

                # Read delayed sample
                delayed = buf[:, ptr]

                # Write to buffer
                buf[:, ptr] = delayed_in + delayed * self.comb_feedback
                self.comb_ptrs[n] = (ptr + 1) % buf.shape[1]

                comb_sum += delayed

            # Series all-pass filters
            ap = comb_sum
            for n in range(2):
                buf = self.allpass_buffers[n]
                ptr = self.allpass_ptrs[n]
                read_ptr = (ptr - int(self.allpass_times[n] * 44.1)) % buf.shape[1]

                delayed = buf[:, read_ptr]
                ap = -ap + delayed
                buf[:, ptr] = ap * self.diffusion + delayed * (1 - self.diffusion)

                self.allpass_ptrs[n] = (ptr + 1) % buf.shape[1]
                ap = delayed + ap * self.diffusion

            # Mix dry/wet
            output[i] = in_sample * dry + ap * wet

        return output


class ReverbEffect(CoreAudioEffect):
    def __init__(self, decay_time=2.0, pre_delay=50.0, damping=0.5, diffusion=0.7,
                 room_size=0.8, wet=0.3, modulation_depth=0.1, modulation_rate=0.5
                 ):
        super().__init__()
        # Parameters
        self.decay_time = decay_time  # Seconds
        self.pre_delay = pre_delay  # Milliseconds
        self.damping = damping  # 0-1 (high-frequency attenuation)
        self.diffusion = diffusion  # 0-1 (echo density)
        self.room_size = room_size  # 0-1 (perceived space size)
        self.wet = wet  # Dry/Wet mix (0-1)
        self.modulation_depth = modulation_depth  # Chorus-like modulation
        self.modulation_rate = modulation_rate  # Hz

        # Delay line configuration (FDN with 4 delay lines)
        self.delay_times = np.array([37, 87, 181, 271])  # Prime numbers for FDN
        self.delay_buffers = [np.zeros((2, int(t))) for t in self.delay_times * room_size]  # Stereo buffers
        self.delay_idx = [0] * 4

        # Pre-delay buffer
        self.pre_delay_samples = int(pre_delay * 44.1)
        self.pre_delay_buffer = np.zeros((2, self.pre_delay_samples))
        self.pre_delay_idx = 0

        # All-pass filters for diffusion
        self.allpass_buffers = [np.zeros((2, 105)), np.zeros((2, 337))]  # Stereo buffers
        self.allpass_idx = [0, 0]

        # Modulation
        self.mod_phase = 0.0
        self.lfo_rates = [0.7, 1.1, 1.5, 2.0]  # Different LFO rates for each delay line

        # Damping filter coefficients
        self.damping_filter = self._create_lowpass(damping)
        self.z = np.zeros((2, 2))  # Filter state (2 channels, 2 states)

    def _create_lowpass(self, cutoff):
        """Create a first-order lowpass filter coefficient"""
        freq = 20000 * (1 - cutoff) + 100  # 100Hz to 20kHz
        rc = 1.0 / (2 * np.pi * freq)
        dt = 1.0 / 44100
        alpha = dt / (rc + dt)
        return alpha

    def process(self, data, sample_rate, flat=False):
        if flat:
            return data

        processed = np.zeros_like(data)
        for i in range(data.shape[0]):
            # Pre-delay
            pre_delayed = np.zeros(2)
            for c in range(2):
                self.pre_delay_buffer[c, self.pre_delay_idx] = data[i, c]
                pre_delayed[c] = self.pre_delay_buffer[c, (
                                                                  self.pre_delay_idx - self.pre_delay_samples) % self.pre_delay_samples]
            self.pre_delay_idx = (self.pre_delay_idx + 1) % self.pre_delay_samples

            # Input diffusion (stereo all-pass filters)
            diffused = pre_delayed.copy()
            for ap_idx in range(2):
                buf = self.allpass_buffers[ap_idx]
                idx = self.allpass_idx[ap_idx]
                buf_len = buf.shape[1]

                for c in range(2):  # Process each channel
                    delayed = buf[c, (idx - 5) % buf_len]
                    diffused[c] = diffused[c] * -self.diffusion + delayed
                    buf[c, idx] = pre_delayed[c] + diffused[c] * self.diffusion
                self.allpass_idx[ap_idx] = (idx + 1) % buf_len

            # FDN processing with modulation
            fdn_out = np.zeros(2)
            for dly in range(4):
                # Modulate delay time
                mod = self.modulation_depth * np.sin(2 * np.pi * self.mod_phase)
                mod_phase_inc = self.lfo_rates[dly] / sample_rate
                self.mod_phase = (self.mod_phase + mod_phase_inc) % 1.0

                # Read modulated delay
                read_idx = int((self.delay_idx[dly] - self.delay_times[dly] *
                                (1 + mod)) % len(self.delay_buffers[dly][0]))

                # Get delayed sample
                delayed = self.delay_buffers[dly][:, read_idx]

                # Apply damping filter
                for c in range(2):  # Process each channel
                    filtered = self.damping_filter * delayed[c] + (1 - self.damping_filter) * self.z[dly % 2, c]
                    self.z[dly % 2, c] = filtered
                    delayed[c] = filtered

                # Feedback matrix (Hadamard)
                feedback = delayed * (0.25 * np.sqrt(1 / self.decay_time))

                # Write to delay line
                self.delay_buffers[dly][:, self.delay_idx[dly]] = diffused + feedback
                self.delay_idx[dly] = (self.delay_idx[dly] + 1) % len(self.delay_buffers[dly][0])

                # Sum outputs
                fdn_out += delayed

            # Mix dry/wet
            processed[i] = data[i] * (1 - self.wet) + fdn_out * self.wet

        return processed


class ConvolutionReverbEffect(CoreAudioEffect):

    def __init__(self, impulse_res_path):
        self.impulse, _ = sf.read(impulse_res_path)
        self.impulse = self.impulse.T
        self.conv_buffer = np.zeros((2, len(self.impulse[0])))

    def process(self, data, sample_rate, flat=False):
        output = np.zeros_like(data)
        if flat:
            output = data
        else:
            for c in range(2):
                output[:, c] = np.convolve(data[:, c], self.impulse[c], mode='same')

        return output


class PlaylistManager:

    def __init__(self, engine):
        self.engine = engine
        self.playlist = deque()
        self.current_channel = None
        self.next_channel = None

    def start_engine(self):
        # self.engine.start_stream()
        self.engine.play()

    def add_track(self, path):
        self.playlist.append(path)
    
    def queue_file(self, file):
        self.engine.queue_file(file)

    def play_next(self):
        if self.playlist:
            print("[+] Playing..")
            if self.current_channel:
                self.current_channel.playing = False

            self.current_channel = self.engine._create_channel(True)
            self.current_channel.load_file(self.playlist[0])
            # self.current_channel.effects.append(UltraLightReverb())
            # self.current_channel.effects.append(EQEffect())
            self.current_channel.playing = True
            self.playlist.popleft()


# ####### Custom engine ######

class AudioEngine(CoreEngine):

    def __init__(self, sample_rate=44100, buffer_size=2048):
        super().__init__(sample_rate, buffer_size)
        self.donot_play = True
        self.process = None
        self._output_latency = 'high'  # Increased latency tolerance
        self._startup_delay = 0.2

        self.eq_names = ["60", "125", "250", "500", "1k", "2k", "4k", "8k", "16k"]
        self.eq_values = [1, 0, 0, 0, 0, 0, 0, 0, 0]

        self._map_events = {1: "Stopped", 0: "Playing", 2: "Paused"}

    def initiliaze_soundout(self, path):
        """
        Load file, Backward comptibility
        :param path:
        :return:
        """
        self.shutdown()
        self.clear_channels()
        self._channel = self._create_channel()
        self._channel.load_file(file_path=path)
        self.donot_play = self._channel.do_not_play

    def play(self):
        """
        Start streaming
        :return:
        """
        '''self.stop()
        # self.process = multiprocessing.Process(target=self.start_stream, daemon=True)
        self.process = CustomThread(target=self.start_stream)
        self.process.daemon = True
        self.process.start()
        if self._channel:
            self._channel.playing = True
            self._channel.on_playback_end = self.handle_playback_end
        self._set_end_event(0)  # backward compatibility'''
        # new
        # self.end_event = 0
        self.shutdown()

        # Initialize audio channel before starting stream
        if not self._channel:
            self._channel = self._create_channel()

        # Start audio processing and streaming
        self.start_stream()

        # Activate playback
        with self.lock:
            if self._channel:
                self._channel.playing = True
                self._channel.on_playback_end = self.handle_playback_end
            self._set_end_event(0)

    def set_pos(self, pos):
        """
        Set playback position
        :param pos:
        :return:
        """
        self._channel.set_position(pos)

    def get_pos(self):
        """
        For backward compatibility
        :return:
        """
        return self._channel.get_position()

    def get_volume(self):
        """
        Gets the volume
        :return:
        """
    
    def get_file_length(self):
        return self._channel.file_length

    def get_endevent(self):
        """
        End Event
        :return:
        """
        return self._end_event

    def map_event(self):
        """
        For backward compatibility
        :return:
        """

    def is_playing(self):
        """
        For backward compatibility
        :return:
        """
        with self.lock:
            return True if self._end_event == 0 else False

    def stop(self):
        """
        For backward compatibility
        :return:
        """
        if self.process:
            # if self.process.is_alive():
            #    self.process.terminate()
            #    self.process.join()
            if not self.process.stopped():
                self.process.stop()

        self.shutdown()


if __name__ == '__main__':
    import os

    engine = AudioEngine(buffer_size=4096)
    # engine.mixer = CoreMixer(engine.sample_rate, engine.buffer_size)
    play_manager = PlaylistManager(engine)

    music_dir = os.path.expanduser("~") + "/Music"
    for file in os.listdir(music_dir):
        if file.endswith(".mp3"):
            play_manager.add_track(os.path.join(music_dir, file))
    print("[+] Loaded songs")

    def check_end_event():
        global engine, play_manager
        while True:
            if engine.is_playing():
                pos = engine.get_pos()
                print(f"\rPOS: {pos:.1f}/{engine.get_file_length()}", end="", flush=True)
                if pos + 1 >= engine.get_file_length():
                    engine.queue_file(play_manager.playlist.pop())
                    
            time.sleep(.5)

    engine.play()
    play_manager.play_next()

    try:
        print(f"""
Commands:\n
n - next song
v int - volume
p - pause
r - resume
q - stop
""")
        threading.Thread(target=check_end_event, daemon=True).start()
        while True:
            cmd = input("Command: ")
            if cmd == "n":
                play_manager.play_next()
            elif "v" in cmd:
                c, v = cmd.split(" ")
                engine.set_volume(float(v))
            elif cmd == "q":
                engine.stop()
                break
            elif cmd == "p":
                engine.pause()
            elif cmd == "r":
                engine.resume()

    except KeyboardInterrupt:
        engine.stop()
