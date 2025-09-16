import os
import numpy as np
from scipy.io.wavfile import read

class Clip:
    def __init__(self, audio_file_path):
        self.audio_file_path = audio_file_path
        self.waveform_image_path = audio_file_path.replace(".wav", ".png")
        self.trim_start_ratio = 0.0
        self.trim_end_ratio = 1.0
        
        try:
            samplerate, data = read(self.audio_file_path)
            self.duration_samples = len(data)
            self.duration_seconds = self.duration_samples / samplerate
        except FileNotFoundError:
            self.duration_samples = 0
            self.duration_seconds = 0
        
    def get_trimmed_data(self):
        if not os.path.exists(self.audio_file_path): return np.array([], dtype=np.int16)
        samplerate, data = read(self.audio_file_path)
        start_sample = int(len(data) * self.trim_start_ratio)
        end_sample = int(len(data) * self.trim_end_ratio)
        return data[start_sample:end_sample]
        
    def to_dict(self):
        return {
            "audio_file_path": self.audio_file_path,
            "waveform_image_path": self.waveform_image_path,
            "trim_start_ratio": self.trim_start_ratio,
            "trim_end_ratio": self.trim_end_ratio
        }

    @classmethod
    def from_dict(cls, data):
        clip = cls(data["audio_file_path"])
        clip.waveform_image_path = data["waveform_image_path"]
        clip.trim_start_ratio = data["trim_start_ratio"]
        clip.trim_end_ratio = data["trim_end_ratio"]
        return clip