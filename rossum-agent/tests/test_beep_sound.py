"""Tests for rossum_agent.beep_sound module."""

from __future__ import annotations

import io
import wave

import numpy as np
from rossum_agent.streamlit_app.beep_sound import generate_beep_wav


class TestGenerateBeepWav:
    """Test generate_beep_wav function."""

    def test_generates_valid_wav_bytes(self):
        """Test that function returns valid WAV file bytes."""
        result = generate_beep_wav()

        assert isinstance(result, bytes)
        assert len(result) > 0

        with wave.open(io.BytesIO(result), "rb") as wav_file:
            assert wav_file.getnchannels() == 1
            assert wav_file.getsampwidth() == 2
            assert wav_file.getframerate() == 16000

    def test_default_parameters(self):
        """Test that default parameters generate expected duration."""
        result = generate_beep_wav()

        with wave.open(io.BytesIO(result), "rb") as wav_file:
            n_frames = wav_file.getnframes()
            frame_rate = wav_file.getframerate()
            duration = n_frames / frame_rate

            assert abs(duration - 0.33) < 0.01

    def test_custom_frequency(self):
        """Test that custom frequency parameter is accepted."""
        result = generate_beep_wav(frequency=880)

        assert isinstance(result, bytes)
        assert len(result) > 0

    def test_custom_duration(self):
        """Test that custom duration generates correct length."""
        duration = 0.5
        sample_rate = 16000
        result = generate_beep_wav(duration=duration, sample_rate=sample_rate)

        with wave.open(io.BytesIO(result), "rb") as wav_file:
            n_frames = wav_file.getnframes()
            actual_duration = n_frames / sample_rate

            assert abs(actual_duration - duration) < 0.01

    def test_custom_sample_rate(self):
        """Test that custom sample rate is set correctly."""
        sample_rate = 22050
        result = generate_beep_wav(sample_rate=sample_rate)

        with wave.open(io.BytesIO(result), "rb") as wav_file:
            assert wav_file.getframerate() == sample_rate

    def test_wave_data_is_16bit_signed_integer(self):
        """Test that wave data is in 16-bit signed integer format."""
        result = generate_beep_wav()

        with wave.open(io.BytesIO(result), "rb") as wav_file:
            frames = wav_file.readframes(wav_file.getnframes())
            data = np.frombuffer(frames, dtype=np.int16)

            assert data.dtype == np.int16
            assert data.min() >= -32768
            assert data.max() <= 32767

    def test_different_frequencies_produce_different_output(self):
        """Test that different frequencies produce different WAV data."""
        result1 = generate_beep_wav(frequency=440)
        result2 = generate_beep_wav(frequency=880)

        assert result1 != result2

    def test_deterministic_output(self):
        """Test that same parameters produce identical output."""
        result1 = generate_beep_wav(frequency=460, duration=0.33, sample_rate=16000)
        result2 = generate_beep_wav(frequency=460, duration=0.33, sample_rate=16000)

        assert result1 == result2

    def test_mono_audio(self):
        """Test that generated audio is mono (1 channel)."""
        result = generate_beep_wav()

        with wave.open(io.BytesIO(result), "rb") as wav_file:
            assert wav_file.getnchannels() == 1

    def test_short_duration(self):
        """Test that very short durations work correctly."""
        result = generate_beep_wav(duration=0.1)

        with wave.open(io.BytesIO(result), "rb") as wav_file:
            duration = wav_file.getnframes() / wav_file.getframerate()
            assert abs(duration - 0.1) < 0.01

    def test_long_duration(self):
        """Test that longer durations work correctly."""
        result = generate_beep_wav(duration=2.0, sample_rate=16000)

        with wave.open(io.BytesIO(result), "rb") as wav_file:
            duration = wav_file.getnframes() / wav_file.getframerate()
            assert abs(duration - 2.0) < 0.01
