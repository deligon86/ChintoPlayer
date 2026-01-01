from .effect import CoreAudioEffect
import numpy as np


class UltraLightReverb(CoreAudioEffect):
    """
    Minimal Reverb Effect
    """

    def __init__(self, decay_time=1.0, wet=0.3, pre_delay=2, damping=0.2, sr=44100):
        super().__init__()
        # Parameters
        self.decay_time = decay_time  # Seconds
        self.wet = wet  # 0-1 wet/dry mix
        self.pre_delay = pre_delay  # Milliseconds
        self.damping = damping  # 0-1 (high-frequency attenuation)

        # Fixed delay line size (stereo)
        self.delay_samples = int(decay_time * sr)  # Max delay time
        self.delay_buffer = np.zeros((2, self.delay_samples))
        self.delay_ptr = 0

        # Pre-delay buffer (stereo)
        self.pre_delay_samples = int(pre_delay * (sr/1000))
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
    def __init__(self, decay_time=1.5, wet=0.3, pre_delay=20, diffusion=0.7, sr=48000):
        super().__init__()
        # Parameters
        self.decay_time = decay_time  # Seconds
        self.wet = wet  # 0-1 wet/dry mix
        self.pre_delay = pre_delay  # Milliseconds
        self.diffusion = diffusion  # 0-1 echo density

        # Fixed architecture (4 comb + 2 allpass)
        self.comb_times = [29.7, 37.1, 43.7, 51.3]  # Prime numbers (ms)
        self.allpass_times = [5.0, 1.7]  # Milliseconds
        self.sample_rate = sr
        # Initialize buffers
        self._init_buffers()

    def _init_buffers(self):
        # Pre-delay buffer (stereo)
        self.pre_delay_samples = int(self.pre_delay * (self.sample_rate/1000))
        self.pre_delay_buf = np.zeros((2, self.pre_delay_samples))
        self.pre_delay_ptr = 0

        # Comb filters (parallel)
        self.comb_buffers = [
            np.zeros((2, int(t * (self.sample_rate/1000))))
            for t in self.comb_times
        ]
        self.comb_ptrs = [0] * 4

        # All-pass filters (series)
        self.allpass_buffers = [
            np.zeros((2, int(t * (self.sample_rate/1000))))
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
    def __init__(self, decay_time=2.0, pre_delay=0.0, damping=0.5, diffusion=0.7,
                 room_size=0.8, wet=0.3, modulation_depth=0.1, modulation_rate=0.5,
                 sr=44100):
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
        self.sample_rate = sr

        # Delay line configuration (FDN with 4 delay lines)
        self.delay_times = np.array([37, 87, 181, 271])  # Prime numbers for FDN
        self.delay_buffers = [np.zeros((2, int(t))) for t in self.delay_times * room_size]  # Stereo buffers
        self.delay_idx = [0] * 4

        # Pre-delay buffer
        self.pre_delay_samples = int(pre_delay * (sr/1000))
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
        dt = 1.0 / self.sample_rate
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
            #diffused = pre_delayed.copy()
            """for ap_idx in range(2):
                buf = self.allpass_buffers[ap_idx]
                idx = self.allpass_idx[ap_idx]
                buf_len = buf.shape[1]

                for c in range(2):  # Process each channel
                    delayed = buf[c, (idx - 5) % buf_len]
                    diffused[c] = diffused[c] * -self.diffusion + delayed
                    buf[c, idx] = pre_delayed[c] + diffused[c] * self.diffusion
                self.allpass_idx[ap_idx] = (idx + 1) % buf_len"""

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
                """for c in range(2):  # Process each channel
                    filtered = self.damping_filter * delayed[c] + (1 - self.damping_filter) * self.z[dly % 2, c]
                    self.z[dly % 2, c] = filtered
                    delayed[c] = filtered"""

                # Feedback matrix (Hadamard)
                feedback = delayed * (0.25 * np.sqrt(1 / self.decay_time))

                # Write to delay line
                self.delay_buffers[dly][:, self.delay_idx[dly]] = pre_delayed + feedback
                self.delay_idx[dly] = (self.delay_idx[dly] + 1) % len(self.delay_buffers[dly][0])

                # Sum outputs
                fdn_out += delayed

            # Mix dry/wet
            processed[i] = data[i] * (1 - self.wet) + fdn_out * self.wet

        return processed


class OptimalReverb(CoreAudioEffect):

    def __init__(self, sample_rate=44100, wet=0.5, dry=0.5, predelay=.02, room_size=.6,
                 early_reflection=.2, damping=.5, diffusion=.5, decay=1.5):
        self.sample_rate = sample_rate
        self.wet = wet
        self.dry = dry
        self.predelay = int(predelay * self.sample_rate)
        self.room_size = room_size
        self.decay = decay
        self.er = early_reflection
        self.damping = damping
        self.difussion = diffusion

        self.max_delay = int(sample_rate * (decay + predelay))
        #print("Max delay: ", self.max_delay)

        self.delay_line_1 = np.zeros(self.max_delay)
        self.delay_line_2 = np.zeros(self.max_delay)
        self.delay_line_3 = np.zeros(self.max_delay)
        #print(self.delay_line_1)
        self.reflection_feedback = 0.3 * self.room_size
        self.reverb_feedback = 0.7 * self.room_size

        self.damping_factor = np.exp(-self.damping/self.sample_rate)
        self.decay_factor = np.exp(-1.0/self.decay)

    def shift_delay_line(self, delay_line, new_sample: np.ndarray):
        """if isinstance(new_sample, np.ndarray):
            new_sample = new_sample.item()
        delay_line[:-1] = delay_line[1:]
        delay_line[-1] = new_sample"""
        sample_length = new_sample.shape[0]
        delay_line = np.roll(delay_line,shift=sample_length)
        delay_line[:sample_length] = new_sample
        return delay_line

    def process(self, data, sample_rate, flat=False):
        if flat:
            return data
        
        output = np.zeros_like(data)
        dry_signal = self.dry * data
        wet_signal = np.zeros_like(dry_signal)

        for i in range(len(data)):
            samples = data[i,:]
            
            er = self.er * (self.delay_line_1[0] + self.delay_line_2[0] + self.delay_line_3[0])
            reverb_out = self.reflection_feedback * er + self.reverb_feedback * self.delay_line_1[0]
            #print(self.reflection_feedback)
            # difussion
            
            self.delay_line_1 = self.shift_delay_line(self.delay_line_1, samples + self.reflection_feedback * er + self.damping_factor * self.delay_line_1[0])
            self.delay_line_2 = self.shift_delay_line(self.delay_line_2, samples + self.reverb_feedback * reverb_out)
            self.delay_line_3 = self.shift_delay_line(self.delay_line_3, samples + self.difussion * reverb_out)
            # decay & damping
            wet_signal[i] = self.wet * (self.decay_factor * (self.delay_line_1[-1] + self.delay_line_2[-1] + self.delay_line_3[-1]))
        
        output = dry_signal + wet_signal


        return output
