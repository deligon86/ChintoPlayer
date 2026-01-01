import numpy as np


class CoreAudioEffect:

    def process(self, data: np.ndarray, sample_rate:int, flat=False):
        ...
        