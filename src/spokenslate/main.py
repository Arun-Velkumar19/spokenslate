"""CLI.

    python -m spokenslate process lecture.mp4 --words words.json --out site/ --title "Calc 2, 6.1"
    python -m spokenslate render site/lecture.json --out site/lecture.html

`process` writes <out>/<stem>.json (the LectureDoc) and <out>/<stem>.html (the page).
Without --words it transcribes the audio (Muse Voice Transcribe; unverified, see
models/transcribe.py).
"""

from __future__ import annotations

import argparse
import json
import logging
import tempfile
from pathlib import Path

from spokenslate.config import load_settings
from spokenslate.render import render_html
from spokenslate.spec import LectureDoc


def _process(args: argparse.Namespace) -> None:
    from spokenslate.models.muse import MuseClient
    from spokenslate.models.transcribe import MuseTranscriber, load_words
    from spokenslate.pipeline import Clients, process
    from spokenslate.video import VideoFile, extract_audio

    s = load_settings()
    video = Path(args.video)
    source = VideoFile(video)
    if args.words:
        words = load_words(Path(args.words))
    else:
        with tempfile.TemporaryDirectory() as d:
            wav = extract_audio(video, Path(d) / "audio.wav")
            words = MuseTranscriber(s.api_key, s.base_url, s.transcribe_model).transcribe(wav)
    fingertips = [tuple(x) for x in json.loads(Path(args.fingertips).read_text())] \
        if args.fingertips else []

    clients = Clients(
        board=MuseClient(s.api_key, s.base_url, s.board_model),
        resolver=MuseClient(s.api_key, s.base_url, s.resolve_model),
        escalate=MuseClient(s.api_key, s.base_url, s.escalate_model) if args.escalate else None,
    )
    models = {"board": s.board_model, "resolve": s.resolve_model,
              "escalate": s.escalate_model if args.escalate else "", "words": "file" if args.words else s.transcribe_model}
    doc, stats = process(source, words, clients, title=args.title or video.stem,
                         source_name=args.source or video.name, fingertips=fingertips,
                         threshold=s.confidence_threshold, models=models)
    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    (out / f"{video.stem}.json").write_text(doc.model_dump_json(indent=1))
    (out / f"{video.stem}.html").write_text(render_html(doc))
    print(f"{stats}\nwrote {out / video.stem}.json and .html")


def _render(args: argparse.Namespace) -> None:
    doc = LectureDoc.model_validate_json(Path(args.doc).read_text())
    Path(args.out).write_text(render_html(doc))
    print(f"wrote {args.out}")


def main(argv: list[str] | None = None) -> None:
    p = argparse.ArgumentParser(prog="spokenslate", description="SpokenSlate: board-aware lecture transcripts")
    sub = p.add_subparsers(dest="cmd", required=True)
    pr = sub.add_parser("process", help="lecture video -> accessible page")
    pr.add_argument("video")
    pr.add_argument("--words", help="JSON [{text,start,end}] instead of transcribing")
    pr.add_argument("--fingertips", help="JSON [[t,u,v], ...] board-normalized fingertip track")
    pr.add_argument("--out", default="site")
    pr.add_argument("--title")
    pr.add_argument("--source", help="credit line, e.g. 'MIT OCW 18.06, CC BY-NC-SA'")
    pr.add_argument("--escalate", action="store_true", help="retry unresolved with Wonder")
    pr.set_defaults(fn=_process)
    rd = sub.add_parser("render", help="re-render a saved LectureDoc JSON")
    rd.add_argument("doc")
    rd.add_argument("--out", required=True)
    rd.set_defaults(fn=_render)

    args = p.parse_args(argv)
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")
    args.fn(args)


if __name__ == "__main__":
    main()
