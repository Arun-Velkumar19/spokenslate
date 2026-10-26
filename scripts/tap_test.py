"""Day-1 acoustic experiment: does a fingertip tap on paper give a clean mic onset?

    python scripts/tap_test.py                         # live: print every onset
    python scripts/tap_test.py --list-devices
    python scripts/tap_test.py --trials 30 --intent tap --layout bare-desk
    python scripts/tap_test.py --trials 30 --intent speech --layout bare-desk
    python scripts/tap_test.py --wav data/captures/x.wav   # replay a saved recording

Live mode prints each onset with its features (level above floor, rise, decay time,
spectral centroid). Use them to pick TapConfig gates, e.g. a max centroid if keyboard
clicks are brighter than paper taps on your desk.

Trial mode logs one row per trial to eval/press_trials.csv (method=acoustic):
  --intent tap     : a countdown, then a --window second slot; tap once in it.
                     activated=1 if at least one onset landed in the slot.
  --intent speech|typing|bump|silence : do that continuously; each --window slot is a
                     trial and any onset in it is a false activation.
control_hit is left empty: there is no fingertip check in this test.

Keep hands off the keyboard during tap trials: key clicks are onsets too.
--save writes the session audio to data/captures/ (gitignored) for --wav replays.
"""

from __future__ import annotations

import argparse
import csv
import datetime
import pathlib
import time
import wave

import numpy as np

from paperos.config import load_settings
from paperos.sensing.acoustic import Onset, OnsetDetector, TapConfig, TapDetector

CSV = pathlib.Path("eval/press_trials.csv")
CAPTURES = pathlib.Path("data/captures")
INTENTS = ["tap", "speech", "typing", "bump", "silence"]


def fmt(o: Onset, t_ref: float) -> str:
    return (f"onset t={o.t - t_ref:7.3f}s  peak={o.peak_dbfs:6.1f} dBFS  "
            f"level={o.level_db:5.1f} dB  rise={o.rise_db:5.1f} dB  "
            f"decay={o.decay_ms:3.0f} ms  centroid={o.centroid_hz:5.0f} Hz")


def summary(onsets: list[Onset]) -> str:
    if not onsets:
        return "onsets=0"
    lv = max(o.level_db for o in onsets)
    cen = "/".join(f"{o.centroid_hz:.0f}" for o in onsets)
    dec = "/".join(f"{o.decay_ms:.0f}" for o in onsets)
    return f"onsets={len(onsets)} max_level={lv:.0f}dB decay_ms={dec} centroid_hz={cen}"


def append_rows(rows: list[dict]) -> None:
    fields = ["date", "layout_id", "method", "trial", "intent", "activated", "control_hit",
              "notes"]
    new = not CSV.exists() or CSV.stat().st_size == 0
    with CSV.open("a", newline="") as f:
        w = csv.DictWriter(f, fieldnames=fields)
        if new:
            w.writeheader()
        w.writerows(rows)


def replay(path: pathlib.Path, cfg: TapConfig) -> None:
    with wave.open(str(path)) as w:
        if w.getsampwidth() != 2:
            raise SystemExit("expected 16-bit PCM wav (as written by --save)")
        sr, ch = w.getframerate(), w.getnchannels()
        x = np.frombuffer(w.readframes(w.getnframes()), np.int16).astype(np.float32) / 32768
    x = x.reshape(-1, ch)[:, 0]
    if sr != cfg.sample_rate:
        raise SystemExit(f"wav is {sr} Hz; detector expects {cfg.sample_rate} Hz")
    onsets = OnsetDetector(cfg).process(x, 0.0)
    for o in onsets:
        print(fmt(o, 0.0))
    print(f"{len(onsets)} onsets in {len(x) / sr:.1f}s")


def save_wav(blocks: list[np.ndarray], sr: int, tag: str) -> pathlib.Path:
    CAPTURES.mkdir(parents=True, exist_ok=True)
    path = CAPTURES / f"{time.strftime('%Y%m%d-%H%M%S')}-{tag}.wav"
    pcm = (np.clip(np.concatenate(blocks), -1, 1) * 32767).astype(np.int16)
    with wave.open(str(path), "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(sr)
        w.writeframes(pcm.tobytes())
    return path


def live(td: TapDetector) -> None:
    t_ref = time.monotonic()
    last_status = t_ref
    print("listening; tap the paper. Ctrl-C to stop.")
    while True:
        for o in td.poll_onsets():
            print(fmt(o, t_ref))
        now = time.monotonic()
        if now - last_status > 5:
            print(f"  floor={td.floor_dbfs:.1f} dBFS  overflows={td.overflows}")
            last_status = now
        time.sleep(0.01)


def collect(td: TapDetector, t0: float, t1: float) -> list[Onset]:
    got: list[Onset] = []
    while time.monotonic() < t1 + td.detector.cfg.max_decay_ms / 1000 + 0.05:
        got += td.poll_onsets()
        time.sleep(0.01)
    return [o for o in got if t0 <= o.t < t1]


def trials(td: TapDetector, args) -> list[dict]:
    today = datetime.date.today().isoformat()
    rows = []
    time.sleep(1.0)  # let the noise floor settle
    td.poll_onsets()
    if args.intent != "tap":
        print(f"start {args.intent} now: {args.trials} slots of {args.window:.1f}s")
    for k in range(1, args.trials + 1):
        if args.intent == "tap":
            for n in (3, 2, 1):
                print(f"\rtrial {k}/{args.trials}: tap in {n} ", end="", flush=True)
                time.sleep(0.4)
            print(f"\rtrial {k}/{args.trials}: TAP NOW          ", end="", flush=True)
        t0 = time.monotonic()
        onsets = collect(td, t0, t0 + args.window)
        activated = int(bool(onsets))
        ok = activated == (args.intent == "tap")
        print(f"\rtrial {k}/{args.trials}: {'ok  ' if ok else 'MISS' if activated == 0 else 'FALSE'}"
              f"  {summary(onsets)}")
        note = summary(onsets) + (f"; {args.note}" if args.note else "")
        rows.append({"date": today, "layout_id": args.layout, "method": "acoustic",
                     "trial": k, "intent": args.intent, "activated": activated,
                     "control_hit": "", "notes": note})
        if args.intent == "tap":
            time.sleep(0.3)
    hits = sum(r["activated"] for r in rows)
    if args.intent == "tap":
        print(f"\ndetected {hits}/{args.trials} taps (gate: >=27/30)")
    else:
        print(f"\nfalse activations {hits}/{args.trials} slots (gate: <=3/30)")
    return rows


def main() -> None:
    s = load_settings()
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--device", default=s.mic_device, help="sounddevice input name or index")
    ap.add_argument("--list-devices", action="store_true")
    ap.add_argument("--trials", type=int, default=0, help="0 = live mode")
    ap.add_argument("--intent", choices=INTENTS, default="tap")
    ap.add_argument("--layout", default="", help="surface/layout id, e.g. bare-desk, mousepad")
    ap.add_argument("--window", type=float, default=1.5, help="seconds per trial slot")
    ap.add_argument("--note", default="", help="appended to every row's notes")
    ap.add_argument("--max-centroid", type=float, default=None, help="Hz; gate bright clicks")
    ap.add_argument("--save", action="store_true", help="save session audio to data/captures/")
    ap.add_argument("--wav", type=pathlib.Path, help="replay a 16 kHz wav instead of the mic")
    args = ap.parse_args()

    cfg = TapConfig(max_centroid_hz=args.max_centroid)
    if args.list_devices:
        import sounddevice as sd

        print(sd.query_devices())
        return
    if args.wav:
        replay(args.wav, cfg)
        return
    if args.trials and not args.layout:
        raise SystemExit("--layout is required for logged trials (e.g. --layout bare-desk)")

    device = int(args.device) if args.device and args.device.isdigit() else args.device
    td = TapDetector(cfg, device=device)
    blocks: list[np.ndarray] = []
    if args.save:
        td.on_block = blocks.append
    rows: list[dict] = []
    try:
        with td:
            if args.trials:
                rows = trials(td, args)
            else:
                live(td)
    except KeyboardInterrupt:
        print()
    finally:
        if rows:
            append_rows(rows)
            print(f"logged {len(rows)} rows to {CSV}")
        if blocks:
            print(f"saved {save_wav(blocks, cfg.sample_rate, args.intent)}")
        if td.overflows:
            print(f"warning: {td.overflows} input overflows (dropped audio)")


if __name__ == "__main__":
    main()
