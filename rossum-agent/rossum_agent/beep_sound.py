"""Beep sound for UI notifications."""

import io
import wave

import numpy as np


def generate_beep_wav(frequency: int = 460, duration: float = 0.33, sample_rate: int = 16000) -> bytes:
    """Generate a beep sound as WAV bytes.

    Args:
        frequency: Frequency of the beep in Hz
        duration: Duration of the beep in seconds
        sample_rate: Sample rate in Hz

    Returns:
        WAV file as bytes
    """
    time_points = np.linspace(0, duration, int(sample_rate * duration), endpoint=False)
    wave_data = np.sin(2 * np.pi * frequency * time_points)

    # Normalize to 16-bit integer range
    wave_data = (wave_data * 32767).astype(np.int16)

    # Create WAV file in memory
    buffer = io.BytesIO()
    with wave.open(buffer, "wb") as wav_file:
        wav_file.setnchannels(1)  # Mono
        wav_file.setsampwidth(2)  # 16-bit
        wav_file.setframerate(sample_rate)
        wav_file.writeframes(wave_data.tobytes())

    return buffer.getvalue()
