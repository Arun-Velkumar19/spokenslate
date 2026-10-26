"""Tap onset detection from the mic.

A fingertip tap on paper is a short broadband transient: energy jumps within a few ms
and is gone within a few tens of ms. Speech syllables also start fast but *sustain*.
So an onset needs all of:

1. rise   : frame energy >= rise_db above the minimum of the last rise_ms
2. level  : >= level_db above an adaptive noise floor (and >= min_dbfs absolute)
3. decay  : the smoothed (smooth_ms) envelope falls >= decay_db below its peak within
             max_decay_ms. The envelope matters: a 4 ms frame is shorter than a voice's
             pitch period, so raw voiced-speech frames look like a train of transients.
4. outside the refractory period after the previous onset (bounces, double hits)
5. optional spectral-centroid gate, off by default (see below)

Check 3 delays each onset until the decay is seen (~20-30 ms for a tap, at most
max_decay_ms). Reported timestamps are the onset time, not the confirm time, so fusion
can look up where the fingertip was when the tap happened.

Known limit: keyboard clicks and desk bumps are transients too and pass checks 1-4.
The centroid gate may separate clicks from soft paper taps, but its range must come
from real recordings (scripts/tap_test.py prints every onset's features). Until then,
every onset must be fused with a fingertip-in-region check (sensing/press.py).
Two transients within ~max_decay_ms merge into one candidate, so a tap landing on a
click can be lost.

`OnsetDetector` is pure (samples in, onsets out) and tested on synthetic audio.
`TapDetector` wraps a sounddevice input stream around it.
"""

from __future__ import annotations

import logging
import threading
import time
from collections import deque
from collections.abc import Callable
from dataclasses import dataclass
from typing import Self

import numpy as np

log = logging.getLogger(__name__)

_EPS = 1e-12


@dataclass(frozen=True)
class TapConfig:
    sample_rate: int = 16_000
    hop: int = 64                   # samples per energy frame (4 ms at 16 kHz)
    rise_ms: float = 12.0
    rise_db: float = 15.0
    level_db: float = 18.0          # above the adaptive noise floor
    min_dbfs: float = -60.0
    smooth_ms: float = 16.0
    decay_db: float = 12.0
    max_decay_ms: float = 50.0
    refractory_ms: float = 120.0
    floor_rise_s: float = 2.0       # floor follows louder background slowly...
    floor_fall_s: float = 0.05      # ...and quieter background quickly
    min_centroid_hz: float | None = None
    max_centroid_hz: float | None = None


@dataclass(frozen=True)
class Onset:
    t: float              # onset time (same clock as the t0 passed to process)
    peak_dbfs: float
    level_db: float       # peak above the noise floor
    rise_db: float
    decay_ms: float       # onset to decay_db below peak
    centroid_hz: float


class OnsetDetector:
    """Streaming onset detector. Feed blocks of any size; state carries across calls."""

    def __init__(self, config: TapConfig | None = None) -> None:
        self.cfg = c = config or TapConfig()
        self.dt = c.hop / c.sample_rate
        self._rise_frames = max(1, round(c.rise_ms / 1000 / self.dt))
        self._smooth: deque[float] = deque(maxlen=max(1, round(c.smooth_ms / 1000 / self.dt)))
        self._max_decay_frames = max(1, round(c.max_decay_ms / 1000 / self.dt))
        self._refractory_s = c.refractory_ms / 1000
        self._a_rise = 1 - np.exp(-self.dt / c.floor_rise_s)
        self._a_fall = 1 - np.exp(-self.dt / c.floor_fall_s)
        self.floor_dbfs: float | None = None
        self._recent: deque[float] = deque(maxlen=self._rise_frames)
        self._pending = np.zeros(0, np.float32)
        self._t_next: float | None = None   # time of the first sample in _pending
        self._last_onset = -np.inf
        self._cand: dict | None = None

    def process(self, samples: np.ndarray, t0: float) -> list[Onset]:
        """samples: mono float in [-1, 1]; t0: time of samples[0] in seconds."""
        x = np.asarray(samples, np.float32).reshape(-1)
        if self._t_next is None or len(self._pending) == 0:
            self._t_next = t0
        x = np.concatenate([self._pending, x])
        n = len(x) // self.cfg.hop * self.cfg.hop
        self._pending = x[n:]
        out: list[Onset] = []
        if n == 0:
            return out
        frames = x[:n].astype(np.float64).reshape(-1, self.cfg.hop)
        frames = frames - frames.mean(axis=1, keepdims=True)  # DC offset, rumble
        energies = 10 * np.log10((frames**2).mean(axis=1) + _EPS)
        t = self._t_next
        for frame, e in zip(frames, energies, strict=True):
            onset = self._step(float(e), frame, t)
            if onset is not None:
                out.append(onset)
            t += self.dt
        self._t_next = t
        return out

    # ------------------------------------------------------------------ internals
    def _step(self, e: float, frame: np.ndarray, t: float) -> Onset | None:
        c = self.cfg
        if self.floor_dbfs is None:
            self.floor_dbfs = e
        self._smooth.append(10 ** (e / 10))
        env = 10 * np.log10(sum(self._smooth) / len(self._smooth) + _EPS)
        result = None
        if self._cand is not None:
            result = self._advance_candidate(e, env, frame)
        elif t - self._last_onset >= self._refractory_s and self._recent:
            rise = e - min(self._recent)
            level = e - self.floor_dbfs
            if rise >= c.rise_db and level >= c.level_db and e >= c.min_dbfs:
                self._cand = {
                    "t": t, "peak": e, "env_peak": env, "rise": rise, "frames": [frame], "n": 0
                }
        if self._cand is None and t - self._last_onset >= self._refractory_s:
            a = self._a_rise if e > self.floor_dbfs else self._a_fall
            self.floor_dbfs += a * (e - self.floor_dbfs)
        self._recent.append(e)
        return result

    def _advance_candidate(self, e: float, env: float, frame: np.ndarray) -> Onset | None:
        c, cand = self.cfg, self._cand
        cand["n"] += 1
        cand["frames"].append(frame)
        cand["peak"] = max(cand["peak"], e)
        cand["env_peak"] = max(cand["env_peak"], env)
        if env <= cand["env_peak"] - c.decay_db:
            self._cand = None
            onset = Onset(
                t=cand["t"],
                peak_dbfs=cand["peak"],
                level_db=cand["peak"] - self.floor_dbfs,
                rise_db=cand["rise"],
                decay_ms=cand["n"] * self.dt * 1000,
                centroid_hz=self._centroid(np.concatenate(cand["frames"])),
            )
            if c.min_centroid_hz is not None and onset.centroid_hz < c.min_centroid_hz:
                return None
            if c.max_centroid_hz is not None and onset.centroid_hz > c.max_centroid_hz:
                return None
            # Only kept onsets start the refractory: a gated-out click must not hide a tap.
            self._last_onset = cand["t"]
            return onset
        if cand["n"] >= self._max_decay_frames:
            self._cand = None  # sustained: speech, music, a fan switching on
        return None

    def _centroid(self, y: np.ndarray) -> float:
        nfft = max(256, 1 << (len(y) - 1).bit_length())
        mag = np.abs(np.fft.rfft(y * np.hanning(len(y)), nfft))
        freqs = np.fft.rfftfreq(nfft, 1 / self.cfg.sample_rate)
        return float((freqs * mag).sum() / (mag.sum() + _EPS))


class TapDetector:
    """Live mic onsets. Detection runs in the audio callback; poll() drains results.

    Timestamps are time.monotonic() seconds, estimated from PortAudio's ADC time for
    each block, so they line up with camera frame timestamps.
    """

    def __init__(
        self,
        config: TapConfig | None = None,
        device: int | str | None = None,
        blocksize: int = 256,
        clock: Callable[[], float] = time.monotonic,
    ) -> None:
        self.detector = OnsetDetector(config)
        self.device = device
        self.blocksize = blocksize
        self.clock = clock
        self.overflows = 0
        self._onsets: list[Onset] = []
        self._lock = threading.Lock()
        self._stream = None
        self._last_t0: float | None = None
        self.on_block: Callable[[np.ndarray], None] | None = None  # e.g. save raw audio

    def start(self) -> Self:
        import sounddevice as sd

        self._stream = sd.InputStream(
            samplerate=self.detector.cfg.sample_rate,
            channels=1,
            dtype="float32",
            blocksize=self.blocksize,
            device=self.device,
            callback=self._callback,
        )
        self._stream.start()
        return self

    def stop(self) -> None:
        if self._stream is not None:
            self._stream.stop()
            self._stream.close()
            self._stream = None

    def __enter__(self) -> Self:
        return self.start()

    def __exit__(self, *exc) -> None:
        self.stop()

    def poll(self) -> list[float]:
        """Return onset timestamps since last poll (monotonic seconds)."""
        return [o.t for o in self.poll_onsets()]

    def poll_onsets(self) -> list[Onset]:
        with self._lock:
            out, self._onsets = self._onsets, []
        return out

    @property
    def floor_dbfs(self) -> float | None:
        return self.detector.floor_dbfs

    def _callback(self, indata, frames, time_info, status) -> None:
        if status and status.input_overflow:
            self.overflows += 1
        now = self.clock()
        try:
            age = time_info.currentTime - time_info.inputBufferAdcTime
        except AttributeError:
            age = 0.0
        if not 0 < age < 1:  # some backends report 0; assume the block just finished
            age = frames / self.detector.cfg.sample_rate
        t0 = now - age
        mono = indata[:, 0] if indata.ndim == 2 else indata
        if self.on_block is not None:
            self.on_block(mono.copy())
        onsets = self.detector.process(mono, t0)
        if onsets:
            with self._lock:
                self._onsets.extend(onsets)
