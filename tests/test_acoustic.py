"""Tap onset detection on synthetic audio (no mic needed).

The synthetic sounds are proxies: they check the mechanism (rise, floor, decay,
refractory, centroid gate), not real-world accuracy. Real numbers come from
scripts/tap_test.py sessions logged to eval/press_trials.csv.
"""

from itertools import pairwise
from types import SimpleNamespace

import numpy as np
import pytest

from paperos.sensing.acoustic import OnsetDetector, TapConfig, TapDetector

SR = 16_000
TOL = 0.010  # onset time tolerance, s


def db(x):
    return 10 ** (x / 20)


def background(seconds, dbfs=-65.0, seed=0):
    rng = np.random.default_rng(seed)
    return rng.normal(0, db(dbfs), int(seconds * SR))


def tap(peak_dbfs=-20.0, seed=0):
    """Finger on paper: soft broadband burst (~4 ms decay) plus a low desk thud."""
    rng = np.random.default_rng(seed)
    n = int(0.06 * SR)
    t = np.arange(n) / SR
    noise = np.convolve(rng.normal(0, 1, n), np.ones(4) / 4, "same")  # soften highs
    burst = noise * np.exp(-t / 0.004)
    thud = 0.8 * np.sin(2 * np.pi * 180 * t) * np.exp(-t / 0.008)
    s = burst + thud
    return s / np.abs(s).max() * db(peak_dbfs)


def key_click(peak_dbfs=-22.0, seed=0):
    """Keyboard key: very short, bright click."""
    rng = np.random.default_rng(seed)
    n = int(0.02 * SR)
    t = np.arange(n) / SR
    s = np.diff(rng.normal(0, 1, n + 1)) * np.exp(-t / 0.0015)  # differentiated = bright
    return s / np.abs(s).max() * db(peak_dbfs)


def syllable(dur, peak_dbfs, seed, attack=0.03, fricative=False):
    """Voiced syllable: jittered harmonic tone, raised-cosine attack, sustained."""
    rng = np.random.default_rng(seed)
    n = int(dur * SR)
    t = np.arange(n) / SR
    f0 = rng.uniform(110, 200) * (1 + 0.03 * np.sin(2 * np.pi * 5 * t))
    phase = 2 * np.pi * np.cumsum(f0) / SR
    s = sum(np.sin(h * phase) / h for h in range(1, 25))
    if fricative:  # "s"/"f"-like noise leading into the vowel
        s = s + 0.6 * np.diff(rng.normal(0, 1, n + 1)) * (t < 0.08)
    env = np.ones(n)
    a, r = int(attack * SR), int(0.04 * SR)
    env[:a] = 0.5 * (1 - np.cos(np.pi * np.arange(a) / a))
    env[-r:] = 0.5 * (1 + np.cos(np.pi * np.arange(r) / r))
    s = s * env
    return s / np.abs(s).max() * db(peak_dbfs)


def mix(base, events):
    out = base.copy()
    for t, sig in events:
        i = int(t * SR)
        out[i : i + len(sig)] += sig[: len(out) - i]
    return out


def speech(seconds, start=0.0, peak_dbfs=-15.0, seed=0):
    """Continuous narration-like syllable stream, louder than the taps."""
    rng = np.random.default_rng(seed)
    events, t = [], start
    while t < start + seconds - 0.4:
        dur = rng.uniform(0.12, 0.3)
        events.append((t, syllable(dur, peak_dbfs - rng.uniform(0, 6), int(rng.integers(1e9)),
                                   attack=rng.uniform(0.02, 0.05),
                                   fricative=rng.random() < 0.3)))
        t += dur + rng.uniform(0.03, 0.15)
    return events


def typing(seconds, start=0.0, rate_hz=6.0, seed=0):
    """Key press click, then a quieter release click ~100 ms later."""
    rng = np.random.default_rng(seed)
    events, t = [], start
    while t < start + seconds - 0.15:
        events.append((t, key_click(-22 + rng.uniform(-3, 3), int(rng.integers(1e9)))))
        events.append((t + rng.uniform(0.08, 0.12), key_click(-30, int(rng.integers(1e9)))))
        t += rng.exponential(1 / rate_hz) + 0.05
    return events


def detect(audio, config=None, block=None, t0=0.0):
    d = OnsetDetector(config)
    if block is None:
        return d.process(audio, t0)
    out = []
    for i in range(0, len(audio), block):
        out += d.process(audio[i : i + block], t0 + i / SR)
    return out


def match(onsets, truth):
    """(hits, false_positives) with each true time matched at most once."""
    times = [o.t for o in onsets]
    hits = sum(any(abs(t - u) <= TOL for t in times) for u in truth)
    fps = sum(not any(abs(t - u) <= TOL for u in truth) for t in times)
    return hits, fps


TAP_TIMES = [0.5, 1.1, 1.6, 2.4, 3.0, 3.35, 4.2]


def test_taps_on_quiet_desk():
    audio = mix(background(5), [(t, tap(seed=i)) for i, t in enumerate(TAP_TIMES)])
    onsets = detect(audio)
    assert match(onsets, TAP_TIMES) == (len(TAP_TIMES), 0)
    for o in onsets:
        assert o.decay_ms <= TapConfig().max_decay_ms
        assert o.level_db > 30


def test_quiet_room_gives_nothing():
    assert detect(background(5)) == []


def test_speech_alone_gives_no_onsets():
    audio = mix(background(8), speech(8, seed=3))
    assert detect(audio) == []


def test_taps_between_speech():
    sp = speech(6, seed=7)
    busy = [(t, t + len(s) / SR) for t, s in sp]
    # place taps in the gaps between syllables, >= 20 ms clear of speech
    taps = [a + 0.02 for (_, a), (b, _) in pairwise(busy) if b - a > 0.09]
    assert len(taps) >= 5
    audio = mix(background(6), sp + [(t, tap(-18, seed=i)) for i, t in enumerate(taps)])
    hits, fps = match(detect(audio), taps)
    assert fps == 0
    assert hits >= len(taps) - 1


def test_bounce_suppressed_by_refractory():
    audio = mix(background(2), [(0.5, tap()), (0.53, tap(-26, seed=1))])
    onsets = detect(audio)
    assert len(onsets) == 1 and abs(onsets[0].t - 0.5) <= TOL


def test_taps_spaced_past_refractory_both_count():
    audio = mix(background(2), [(0.5, tap()), (0.65, tap(seed=1))])
    assert match(detect(audio), [0.5, 0.65]) == (2, 0)


def test_noise_floor_adapts_to_louder_room():
    """A fan switches on at 1 s (+25 dB). No onset from the step; taps still count."""
    base = background(6)
    base[SR:] += background(5, dbfs=-40, seed=1)
    taps = [3.0, 4.0, 5.0]
    d = OnsetDetector()
    onsets = d.process(mix(base, [(t, tap(-12, seed=i)) for i, t in enumerate(taps)]), 0.0)
    assert match(onsets, taps) == (3, 0)
    assert -50 < d.floor_dbfs < -35


def test_floor_falls_back_quickly():
    base = background(4, dbfs=-40)
    base[2 * SR :] = background(2, dbfs=-65, seed=2)
    d = OnsetDetector()
    d.process(base, 0.0)
    assert d.floor_dbfs < -55


def test_typing_passes_default_gates():
    """Clicks are transients too: the default detector reports them. This is why every
    onset is fused with a fingertip-in-region check."""
    onsets = detect(mix(background(4), typing(3.5, start=0.3)))
    assert len(onsets) >= 10


def test_centroid_gate_rejects_bright_clicks_keeps_taps():
    """Type for 3 s, then tap. (A tap within ~50 ms of a click merges with it.)"""
    cfg = TapConfig(max_centroid_hz=2500)
    taps = [3.5, 4.0, 4.4, 5.0, 5.6]
    events = typing(3, start=0.2, seed=4) + [(t, tap(seed=i)) for i, t in enumerate(taps)]
    onsets = detect(mix(background(6), events), cfg)
    assert match(onsets, taps) == (len(taps), 0)


def test_centroid_reported():
    (t,) = detect(mix(background(1), [(0.5, tap())]))
    (k,) = detect(mix(background(1), [(0.5, key_click())]))
    assert t.centroid_hz < k.centroid_hz


@pytest.mark.parametrize("block", [1, 37, 64, 256, 1000])
def test_block_size_does_not_matter(block):
    audio = mix(background(5), [(t, tap(seed=i)) for i, t in enumerate(TAP_TIMES)])
    whole = [round(o.t, 6) for o in detect(audio, t0=10.0)]
    chunked = [round(o.t, 6) for o in detect(audio, block=block, t0=10.0)]
    assert whole == chunked
    assert match(detect(audio, block=block), TAP_TIMES) == (len(TAP_TIMES), 0)


def test_tap_detector_callback_and_poll():
    """Drive the sounddevice callback directly with a fake clock and ADC time."""
    audio = mix(background(2), [(0.5, tap()), (1.2, tap(seed=1))]).astype(np.float32)
    now = [100.0]
    td = TapDetector(blocksize=256, clock=lambda: now[0])
    for i in range(0, len(audio) - 255, 256):
        now[0] = 100.0 + (i + 256) / SR + 0.005  # callback runs 5 ms after the block
        info = SimpleNamespace(currentTime=50.0, inputBufferAdcTime=50.0 - 256 / SR - 0.005)
        td._callback(audio[i : i + 256, None], 256, info, None)
    ts = td.poll()
    assert len(ts) == 2
    assert abs(ts[0] - 100.5) <= TOL and abs(ts[1] - 101.2) <= TOL
    assert td.poll() == []
