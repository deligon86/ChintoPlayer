import numpy as np
from .effect import CoreAudioEffect
from .fdn_v2 import TapDelayLine, PreDelay, ModulatedCombFilter, EffectsData, AllpassFilter
    


class AllpassReverb(CoreAudioEffect):

    def __init__(self, sample_rate=44100, delay_ms=1200, feedback=1.3, decay=.2, wet=.3, mix=.4,
                 predelay=.2, dry=.0, er_gain=.2, room=.2, damp=.2):
        self.sr = sample_rate
        self.delay_samples = int((delay_ms/1000) * sample_rate)
        self.feedback = feedback + 1e-8
        self.decay = decay + 1e-8
        self.wet = wet + 1e-8
        self.dry = dry + 1e-8
        self.mix = mix + 1e-8
        self.er_gain = er_gain + 1e-8
        self.predelay_gain = predelay
        self.predelay = PreDelay(sample_rate=sample_rate, delay_ms=delay_ms)
        self.tap_delay = TapDelayLine([20, 40], [.841, .504])
        self.room_scale = room + .9 + .1
        self.damp = damp + 1e-8 * .3 + .2
        self.buffer_left = np.zeros(self.delay_samples)
        self.buffer_right = np.zeros(self.delay_samples)
        self.index_left = 0
        self.index_right = 0

        feedback = 1 - np.exp((mix - 1.0 / (np.log(1 - 0.98) * (-1 / np.log(1 - 0.3)))) /
                              (100 / (np.log(1 - 0.98) * (-1 / np.log(1 - 0.3))) + 1))
        self.combs = [ModulatedCombFilter(int(length * (self.room_scale + .5)), feedback, self.damp) 
                      for length in EffectsData.comb_lengths[:1]]
        self.allpass = [AllpassFilter(int(length + .5), 0.55) for length in EffectsData.allpass_lengths[:1]]

    def process(self, data, sample_rate, flat=False):
        if flat:
            return data
        
        output = np.zeros_like(data)
        """for channel in range(data.shape[1]):
            # left channel
            #delay_left = self.buffer_left[self.index_left]
            output[i, 0] = data[i, 0] - self.feedback * self.buffer_left[self.index_left]#delay_left
            self.buffer_left[self.index_left] = data[i, 0] + self.feedback * output[i, 0]
            self.index_left = (self.index_left + 1) % self.delay_samples
            # right channel
            #delay_right = self.buffer_right[self.index_right]
            output[i, 1] = data[i, 1] - self.feedback * self.buffer_right[self.index_right]#delay_right
            self.buffer_right[self.index_right] = data[i, 1] + self.feedback * output[i, 1]
            self.index_right = (self.index_right + 1) % self.delay_samples

            self.feedback = max(self.feedback * self.decay, 0.05)
            wet_left = data[i, 0] * self.mix
            wet_right = data[i, 1] * self.mix
            output[i, 0] = data[i, 0] * (1 - self.wet) + wet_left * self.wet
            output[i, 1] = data[i, 0] * (1 - self.wet) + wet_right * self.wet
            
            output[:, channel] = np.array([self.tap_delay.process(data[n, channel]) for n in range(data.shape[0])], dtype=np.float32)
            """
        for n in range(data.shape[0]):
            for channel in range(data.shape[1]):
                sample = self.predelay.process(data[n, channel])
                sample = sample * self.predelay_gain + sample * (1.0 - self.predelay_gain)
                er = self.tap_delay.process(sample) * self.er_gain
                out = 0
                for comb in self.combs:
                    out += comb.process(sample)
                    #out += comb.process(out)

                output[n, channel] = (er + out) * self.wet + sample * self.dry
        return output
        


class MultiAllpassReverb(CoreAudioEffect):

    def __init__(self, sample_rate=44100, early_delay_ms=[10, 20], late_delay_ms=[100, 150, 200], early_feedback=[.9, .7], 
                 late_feedbacks=[.8, .65, .5], decay=0.995, min_feedback=0.05, wet=.3, reverb=.4):
        super().__init__()
        self.sr = sample_rate
        self.decay_rate = decay
        self.min_feedback = min_feedback
        self.early_delay_samples = [int(delay/1000) for delay in early_delay_ms]
        self.late_delay_samples = [int(delay/1000) for delay in late_delay_ms]
        self.early_feedbacks = early_feedback
        self.late_feedbacks = late_feedbacks
        self.wet = wet
        self.reverb = reverb

        self.early_buffers = [np.zeros(delay_samples) for delay_samples in self.early_delay_samples]
        self.later_buffers = [np.zeros(delay_samples) for delay_samples in self.late_delay_samples]

        self.early_indices = [0] * len(self.early_delay_samples)
        self.late_indices = [0] * len(self.late_delay_samples)

    def process(self, data, sample_rate, flat=False):
        if flat:
            return data
        output = np.zeros_like(data)
        for i in range(data.shape[0]):
            sample_left = data[i, 0]
            sample_right = data[i, 1]
            """for j in range(len(self.delay_samples)):
                # left
                delay_left = self.buffers[j][self.indices[j]]
                sample_left -= self.feedbacks[j] * delay_left
                self.buffers[j][self.indices[j]] = data[i, 0] + self.feedbacks[j] * sample_left

                delay_right = self.buffers[j][self.indices[j]]
                sample_right -= self.feedbacks[j][self.indices[j]] * delay_right
                self.buffers[j][self.indices[j]] = data[i, 1] + self.feedbacks[j] * sample_right

                self.indices[j] = (self.indices[j] + 1) % self.delay_samples[j]

                # decay
                self.feedbacks[j] = max(self.feedbacks[j] * self.decay_rate, self.min_feedback)
            """
            # er
            for j in range(len(self.early_delay_samples)):
                delay_left = self.early_buffers[j][self.early_indices[j]]
                sample_left -= self.early_feedbacks[j] * delay_left
                self.early_buffers[j][self.early_indices[j]] = data[i, 0] + self.early_feedbacks[j] * sample_left

                delay_right = self.early_buffers[j][self.early_indices[j]]
                sample_right -= self.early_feedbacks[j] * delay_right
                self.early_buffers[j][self.early_indices[j]] = data[i, 1] + self.early_feedbacks[j] * sample_right

                self.early_indices[j] = (self.early_indices[j] + 1) % self.early_delay_samples[j]
                self.early_feedbacks[j] = max(self.early_feedbacks[j] * self.decay_rate, self.min_feedback)
            # late re
            for n in range(len(self.late_delay_samples)):
                delay_left = self.late_buffers[j][self.late_indices[j]]
                sample_left -= self.late_feedbacks[j] * delay_left
                self.late_buffers[j][self.late_indices[j]] = data[i, 0] + self.late_feedbacks[j] * sample_left

                delay_right = self.late_buffers[j][self.late_indices[j]]
                sample_right -= self.late_feedbacks[j] * delay_right
                self.late_buffers[j][self.late_indices[j]] = data[i, 1] + self.late_feedbacks[j] * sample_right

                self.late_indices[j] = (self.late_indices[j] + 1) % self.late_delay_samples[j]
                self.late_feedbacks[j] = max(self.late_feedbacks[j] * self.decay_rate, self.min_feedback)

            wet_left = sample_left * self.reverb
            wet_right = sample_right * self.reverb

            output[i, 0] = sample_left * (1 - self.wet) + wet_left * self.wet
            output[i, 1] = sample_right * (1 - self.wet) + wet_right * self.wet

        return output


class AllpassReverbUnit(CoreAudioEffect):

    def __init__(self, sample_rate=44100, delay_ms=[80, 50, 120], feedbacks=[.8, .5, .4], decay=.5, min_feedback=.05):
        self.sr = sample_rate
        self.decay_rate = decay
        self.min_feedback = min_feedback
        self.delay_samples = [int(delay/1000) for delay in delay_ms]
        self.feedbacks = feedbacks

        self.buffers = [np.zeros(delay_samples) for delay_samples in self.delay_samples]
        self.indices = [0] * len(self.delay_samples)

    def process(self, data, sample_rate, flat=False):
        if flat:
            return data
        output = np.zeros_like(data)
        for i in range(data.shape[0]):
            sample_left, sample_right = data[i, 0], data[i, 1]
            for j in range(len(self.delay_samples)):
                sample_left -= self.feedbacks[j] * self.buffers[j][self.indices[j]]
                self.buffers[j][self.indices[j]] = data[i, 0] + self.feedbacks[j] * sample_left

                sample_right -= self.feedbacks[j] * self.buffers[j][self.indices[j]]
                self.buffers[j][self.indices[j]] = data[i, 1] + self.feedbacks[j] * sample_right

                self.indices[j] = (self.indices[j] + 1) % self.delay_samples[j]
                self.feedbacks[j] = max(self.feedbacks[j] * self.decay_rate, self.min_feedback)

            output[i, 0] = sample_left
            output[i, 1] = sample_right
        
        return output