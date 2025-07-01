#!/usr/bin/env python3
"""
speaker_test.py – quick sanity-check for the Adafruit I2S 3 W Speaker Bonnet
on a Raspberry Pi 5.

▪ Generates a 440 Hz sine tone for 2 s and plays it.
▪ Requires: numpy, simpleaudio  (install with `pip install numpy simpleaudio`)
"""

import os
import subprocess
import sys
import time

import numpy as np
import simpleaudio as sa


def list_alsa_cards() -> None:
    """Print the ALSA sound cards that the OS sees."""
    print("\n=== Detected ALSA sound cards (aplay -l) ===")
    try:
        subprocess.run(["aplay", "-l"], check=True)
    except Exception as exc:
        print(f"(Could not run aplay: {exc})")
    print("===========================================\n")


def play_sine(freq_hz: float = 440.0, seconds: float = 2.0, volume: float = 0.4):
    """Generate and play a sine wave via simpleaudio."""
    sample_rate = 44_100  # Hz
    t = np.linspace(0, seconds, int(sample_rate * seconds), endpoint=False)
    wave = (volume * np.sin(2 * np.pi * freq_hz * t)).astype(np.float32)

    # simpleaudio expects 16-bit PCM; convert:
    pcm16 = (wave * 32767).astype(np.int16)
    audio = sa.play_buffer(pcm16, 1, 2, sample_rate)
    audio.wait_done()


def main():
    list_alsa_cards()

    print("Playing 440 Hz test tone…")
    play_sine()
    print("Done.  If you heard the tone clearly, the speaker bonnet is working!")


if __name__ == "__main__":
    # Make sure we’re not running as root if you don’t need to; ALSA is happier.
    if os.geteuid() == 0:
        print("Warning: running as root is usually unnecessary for audio playback.")
        time.sleep(1)
    try:
        main()
    except KeyboardInterrupt:
        sys.exit(0)
