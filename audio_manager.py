"""
audio_manager.py
Handles all sound feedback:
  - Procedural tones for correct / wrong answers
  - TTS via pyttsx3 (offline) or espeak fallback
  - Sound enabled/disabled flag
"""

import pygame
import math
import array
import threading
from typing import Optional


class AudioManager:
    """
    Generates all sounds programmatically – no audio asset files needed.
    TTS is attempted via pyttsx3; if unavailable, prompts are printed.
    """

    SAMPLE_RATE = 44100

    def __init__(self):
        self._tts_engine = None
        self._tts_lock   = threading.Lock()
        self._init_tts()

    # ------------------------------------------------------------------ #
    #  TTS                                                                 #
    # ------------------------------------------------------------------ #

    def _init_tts(self):
        try:
            import pyttsx3
            engine = pyttsx3.init()
            engine.setProperty('rate', 155)
            engine.setProperty('volume', 0.95)
            # Try to find a child-friendly voice
            voices = engine.getProperty('voices')
            for v in voices:
                if any(k in v.name.lower() for k in ('child', 'samantha', 'victoria', 'zira', 'hazel')):
                    engine.setProperty('voice', v.id)
                    break
            self._tts_engine = engine
        except Exception:
            self._tts_engine = None

    def speak(self, text: str):
        """Non-blocking TTS."""
        print(f"[AUDIO] {text}")   # always print as fallback
        if self._tts_engine is None:
            return

        def _run():
            with self._tts_lock:
                try:
                    self._tts_engine.say(text)
                    self._tts_engine.runAndWait()
                except Exception:
                    pass

        t = threading.Thread(target=_run, daemon=True)
        t.start()

    # ------------------------------------------------------------------ #
    #  Synthesised SFX                                                     #
    # ------------------------------------------------------------------ #

    def play_correct(self):
        """Ascending arpeggio – happy reward."""
        notes = [523, 659, 784, 1047]   # C5 E5 G5 C6
        self._play_arpeggio(notes, dur_ms=90, gap_ms=40)

    def play_wrong(self):
        """Low descending tone."""
        self._play_tone(220, 350, wave='saw', volume=0.4)

    def play_level_up(self):
        """Fanfare."""
        notes = [523, 587, 659, 784, 1047]
        self._play_arpeggio(notes, dur_ms=110, gap_ms=30)

    def play_tick(self):
        """Short click on bubble selection."""
        self._play_tone(880, 60, wave='sine', volume=0.3)

    def play_hint(self):
        """Soft bell hint."""
        self._play_tone(660, 300, wave='sine', volume=0.25)

    # ------------------------------------------------------------------ #
    #  Low-level synth                                                     #
    # ------------------------------------------------------------------ #

    def _play_tone(self, freq: float, dur_ms: int,
                   wave: str = 'sine', volume: float = 0.5):
        try:
            samples   = int(self.SAMPLE_RATE * dur_ms / 1000)
            amplitude = int(32767 * volume)
            buf       = array.array('h', [0] * samples * 2)   # stereo

            for i in range(samples):
                t = i / self.SAMPLE_RATE
                # Envelope: linear fade-out last 20 %
                env = 1.0 if i < samples * 0.8 else (samples - i) / (samples * 0.2)

                if wave == 'sine':
                    val = math.sin(2 * math.pi * freq * t)
                elif wave == 'saw':
                    val = 2 * (t * freq - math.floor(0.5 + t * freq))
                else:
                    val = 1.0 if math.sin(2 * math.pi * freq * t) >= 0 else -1.0

                s          = int(amplitude * val * env)
                buf[i * 2]     = s
                buf[i * 2 + 1] = s

            sound = pygame.sndarray.make_sound(
                pygame.surfarray.map_array(
                    pygame.Surface((1, 1)),
                    [[0]]
                )
            ) if False else None   # placeholder – use raw sndarray

            # Use pygame.sndarray directly
            import numpy as np
            arr = np.array(buf, dtype=np.int16).reshape((-1, 2))
            sound = pygame.sndarray.make_sound(arr)
            sound.play()
        except Exception:
            pass  # Audio failure is non-fatal

    def _play_arpeggio(self, freqs, dur_ms: int = 100, gap_ms: int = 50):
        def _run():
            for f in freqs:
                self._play_tone(f, dur_ms, wave='sine', volume=0.45)
                pygame.time.delay(dur_ms + gap_ms)
        t = threading.Thread(target=_run, daemon=True)
        t.start()
