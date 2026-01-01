import random
import numpy as np
from concurrent.futures import ThreadPoolExecutor
from effects.effect import CoreAudioEffect


class EffectsData:
    tap_delays = [190, 949, 993, 1183, 1192, 1315,
                  2021, 2140, 2524, 2590, 2625, 2700,
                  3119, 3123, 3202, 3268, 3321, 3515]
    tap_gains = [.841, .504, .49, .379, .38, .346,
                 .289, .272, .192, .193, .217, .181,
                 .18, .181, .176, .142, .167, .134]
    comb_lengths = [1116, 1188, 1277, 1356, 1422, 1491, 1557, 1617]
    allpass_lengths = [556, 441, 341, 225]
    allpass_gains = [0.55, 0.55, 0.55, 0.55]


class PreDelay:

    def __init__(self, sample_rate=44100, delay_ms=1000):
        self.delay_samples = int(sample_rate * (delay_ms / 1000))
        self.buffer = np.zeros(self.delay_samples, dtype=np.float32)
        self.index = 0

    def process(self, data):
        output = self.buffer[self.index]
        self.buffer[self.index] = data
        self.index = (self.index + 1) % self.delay_samples
        return output
    

"""class TapDelayLine:

    def __init__(self, tap_delays, tap_gains):
        self.tap_delays = np.array(tap_delays)
        self.tap_gains = np.array(tap_gains)
        self.buffer_index = 0
        self.delay_length = max(self.tap_delays) + 1
        self.buffer = np.zeros(self.delay_length, dtype=np.float32)

    def process(self, data):
        output = 0
        self.buffer[self.buffer_index] = data
        for delay, gain in zip(self.tap_delays, self.tap_gains):
            delay_index = (self.buffer_index - delay) % self.delay_length
            output += gain * self.buffer[delay_index]
        self.buffer_index = (self.buffer_index + 1) % self.delay_length
        return output
"""
class TapDelayLine:
    def __init__(self, tap_delays, tap_gains):
        self.delay_length = max(tap_delays)
        self.buffer = np.zeros(self.delay_length, dtype=np.float32)
        self.tap_delays = tap_delays
        self.tap_gains = tap_gains
        self.pos = 0

    def process(self, x):
        y = 0
        self.buffer[self.pos] = x
        for i, delay in enumerate(self.tap_delays):
            gain = self.tap_gains[i]
            delay_idx = self.pos - delay
            if delay_idx < 0:
                delay_idx += self.delay_length
            y += gain * self.buffer[delay_idx]
        
        self.pos = self.pos + 1
        if self.pos >= self.delay_length:
            self.pos = self.pos - self.delay_length
        return y
    

class Delay:

    def __init__(self, delay_length):
        self.buffer = np.zeros(delay_length, dtype=np.float32)
        self.pos = 0
        self.length = delay_length

    def front(self):
        return self.buffer[self.pos]
    
    def push(self, x):
        self.buffer[self.pos] = x
        self.pos = (self.pos + 1) % self.length
        
    def go_back(self, idx):
        return self.buffer[(self.pos - idx) % self.length]


class AllpassFilter:

    def __init__(self, delay_length, feedback):
        self.feedback = feedback
        self.delay = Delay(delay_length)
    
    def process(self, data):
        v_delay = self.delay.front()
        v = self.feedback * v_delay + data
        output = v_delay - self.feedback * v
        self.delay.push(output)
        return output
    

class ModulatedCombFilter:

    def __init__(self, delay_length, feedback, damp):
        self.base_delay_length = delay_length
        self.buffer = np.zeros(delay_length, dtype=np.float32)
        self.feedback = feedback
        self.damp1 = damp
        self.damp2 = 1.0 - damp
        self.last = 0
        self.index = 0

    def process(self, data):
        output = self.buffer[self.index]
        self.last = output * self.damp2 + self.last * self.damp1
        self.buffer[self.index] = data + self.last * self.feedback
        self.index = (self.index + 1) % len(self.buffer)
        return output
    

class ReverbFilter(CoreAudioEffect):
    episilion = 1e-8  # Prevent floating-point issues
    def __init__(self, room_scale=50, predelay_ms=50, predelay_mix=20, decay=1.0, wet=20,
                 dry=0.0, damp=30, reverberance=23, stereo=20, er_gain=20, sr=44100):
        self.sample_rate = sr
        self.room_scale = room_scale
        self.predelay = predelay_ms
        self.predelay_mix = predelay_mix
        self.decay = decay
        self.wet = (wet + self.episilion) / 100
        self.dry = (dry + self.episilion) / 100
        self.damping = damp
        self.reverberance = (reverberance + self.episilion) / 100
        self.stereo = stereo
        self.cer_gain = er_gain

        self.limit_filters_num = 1
        self.init_reverb()

    def init_reverb(self):
        scale = (self.room_scale + self.episilion) / 100 * .9 + .1
        feedback = 1 - np.exp((self.reverberance - 100 / (np.log(1 - 0.98) * (-1 / np.log(1 - 0.3)))) /
                              (100 / (np.log(1 - 0.98) * (-1 / np.log(1 - 0.3))) + 1))
        hdamp = (self.damping + self.episilion) / 100 * .3 + .2
        width = (self.stereo + self.episilion) / 100
        self.er_gain = (self.cer_gain + self.episilion) / 100 * (width / 2.0 + .5)

        self.predelay_gain = (self.predelay_mix + self.episilion) / 100

        # Precompute taps for combs and allpass filters
        self.predelay_line = PreDelay(self.sample_rate, self.predelay)
        self.er_line = TapDelayLine(EffectsData.tap_delays[:self.limit_filters_num], EffectsData.tap_gains[:self.limit_filters_num])

        self.combs = [ModulatedCombFilter(int(length * (scale + .5)), feedback, hdamp) 
                      for length in EffectsData.comb_lengths[:self.limit_filters_num]]

        self.allpass = [AllpassFilter(int(length + .5), 0.55) for length in EffectsData.allpass_lengths[:self.limit_filters_num]]

    def process_single_sample(self, data):
        input_ = self.predelay_line.process(data)
        input_ = input_ * self.predelay_gain + input_ * (1.0 - self.predelay_gain)
        er = self.er_line.process(input_) * self.er_gain

        output = sum(comb.process(input_) for comb in self.combs)
        output += sum(allpass.process(output) for allpass in self.allpass)

        return (er+output) * self.wet + input_ * self.dry
    
    def process(self, data: np.ndarray, sample_rate: int, flat=False):
        if flat:
            return data
        
        output = np.zeros_like(data, dtype=np.float32)
        for n in range(data.shape[0]):
            for channel in range(data.shape[1]):
                output[n, channel] = self.process_single_sample(data[n, channel])
        """for channel in range(data.shape[1]):
            output[:, channel] = np.array([self.process_single_sample(data[n, channel]) for n in range(data.shape[0])], dtype=np.float32)"""
        """num_chunks = data.shape[0] // 512
        for chunk_idx in range(num_chunks):
            chunk_start = chunk_idx * 512
            chunk_end = (chunk_idx + 1) * 512
            chunk_data = data[chunk_start:chunk_end]
            for channel in range(data.shape[1]):
                output[chunk_start:chunk_end, channel] = np.array([self.process_single_sample(chunk_data[n, channel]) for n in range(chunk_data.shape[0])])
        """
        """with ThreadPoolExecutor() as executor:
            # process channel in parallel
            futures = [executor.submit(self.process_channel, data, channel_idx) for channel_idx in range(data.shape[1])]
            # wait results
            for channel_idx, future in enumerate(futures):
                output[:, channel_idx] = future.result()"""

        return output

    def process_channel(self, data, channel_idx):
        out_channel = np.zeros(data.shape[0], dtype=np.float32)
        #print(out_channel)
        for n in range(data.shape[0]):
            out_channel[n] = self.process_single_sample(data[n, channel_idx])
        
        return out_channel
    
