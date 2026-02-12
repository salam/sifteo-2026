"""
Sifteo V1 Sound Playback.

Host-side sound player for Sifteo games. The original Sifteo SDK played
sounds on the host machine (not on the cubes — they have no speakers).
SiftRunner used a native C extension (siftx.sound) for playback.

This implementation uses macOS `afplay` as a zero-dependency backend.
Each playing sound is a subprocess, allowing multiple concurrent sounds.

Usage:
    from sifteo.sound import SoundMixer

    mixer = SoundMixer()
    handle = mixer.play("explosion.wav")
    mixer.stop(handle)
    mixer.stop_all()
"""

from __future__ import annotations

import os
import subprocess
import threading
from typing import Optional


class SoundMixer:
    """Host-side sound mixer using macOS afplay.

    Manages multiple concurrent sound playbacks. Each play() call
    returns a handle that can be used to stop that specific sound.
    """

    def __init__(self):
        self._sounds: dict[int, subprocess.Popen] = {}
        self._next_handle = 0
        self._lock = threading.Lock()

    def play(self, path: str, volume: float = 1.0) -> int:
        """Play a sound file. Returns a handle for stopping it.

        Args:
            path: Path to a .wav or .mp3 file.
            volume: Volume from 0.0 to 1.0 (maps to afplay's 0-255 range).

        Returns:
            An integer handle for this playing sound.

        Raises:
            FileNotFoundError: If the sound file doesn't exist.
        """
        if not os.path.isfile(path):
            raise FileNotFoundError(f"Sound file not found: {path}")

        vol = max(0, min(255, int(volume * 255)))

        try:
            proc = subprocess.Popen(
                ["afplay", "-v", str(vol / 255.0), path],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )
        except FileNotFoundError:
            # afplay not available (non-macOS)
            return -1

        with self._lock:
            handle = self._next_handle
            self._next_handle += 1
            self._sounds[handle] = proc

        # Clean up when sound finishes naturally
        def _wait():
            proc.wait()
            with self._lock:
                self._sounds.pop(handle, None)
        threading.Thread(target=_wait, daemon=True).start()

        return handle

    def stop(self, handle: int) -> None:
        """Stop a specific playing sound by its handle."""
        with self._lock:
            proc = self._sounds.pop(handle, None)
        if proc and proc.poll() is None:
            proc.terminate()

    def pause_all(self) -> None:
        """Pause all playing sounds (sends SIGSTOP on Unix)."""
        import signal as sig
        with self._lock:
            for proc in self._sounds.values():
                if proc.poll() is None:
                    try:
                        proc.send_signal(sig.SIGSTOP)
                    except OSError:
                        pass

    def resume_all(self) -> None:
        """Resume all paused sounds (sends SIGCONT on Unix)."""
        import signal as sig
        with self._lock:
            for proc in self._sounds.values():
                if proc.poll() is None:
                    try:
                        proc.send_signal(sig.SIGCONT)
                    except OSError:
                        pass

    def stop_all(self) -> None:
        """Stop all playing sounds."""
        with self._lock:
            procs = list(self._sounds.values())
            self._sounds.clear()
        for proc in procs:
            if proc.poll() is None:
                proc.terminate()

    def is_playing(self, handle: int) -> bool:
        """Check if a sound is still playing."""
        with self._lock:
            proc = self._sounds.get(handle)
        return proc is not None and proc.poll() is None

    @property
    def active_count(self) -> int:
        """Number of currently playing sounds."""
        with self._lock:
            return sum(1 for p in self._sounds.values() if p.poll() is None)
