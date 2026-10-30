"""CLI.

    python -m spokenslate process lecture.mp4 --words words.json --out site/ --title "Calc 2, 6.1"
    python -m spokenslate render site/lecture.json --out site/lecture.html

`process` writes <out>/<stem>.json (the LectureDoc) and <out>/<stem>.html (the page).
Without --words it transcribes locally with faster-whisper (word timestamps) and saves
<out>/<stem>.words.json so later runs can pass --words and skip transcription.
"""

from __future__ import annotations

import argparse
import json
import logging
from pathlib import Path

from spokenslate.config import load_settings
from spokenslate.render import render_html
from spokenslate.spec import LectureDoc


def _process(args: argparse.Namespace) -> None:
    from spokenslate.models.muse import MuseClient
    from spokenslate.models.segment import MetaSAM, NullSegmenter
    from spokenslate.models.transcribe import WhisperTranscriber, load_words, save_words
    from spokenslate.pipeline import Clients, process
    from spokenslate.video import VideoFile

    s = load_settings()
    video = Path(args.video)
    source = VideoFile(video)
    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    if args.words:
        words = load_words(Path(args.words))
    else:
        words = WhisperTranscriber(s.whisper_model).transcribe(video)
        save_words(words, out / f"{video.stem}.words.json")
    fingertips = [tuple(x) for x in json.loads(Path(args.fingertips).read_text())] \
        if args.fingertips else []

    clients = Clients(
        board=MuseClient(s.api_key, s.base_url, s.board_model),
        resolver=MuseClient(s.api_key, s.base_url, s.resolve_model),
        escalate=MuseClient(s.api_key, s.base_url, s.escalate_model) if args.escalate else None,
        segmenter=(NullSegmenter() if args.no_sam or not s.sam_model
                   else MetaSAM(s.api_key, s.base_url, s.sam_model)),
    )
    models = {"board": s.board_model, "resolve": s.resolve_model,
              "segment": "" if args.no_sam else s.sam_model,
              "escalate": s.escalate_model if args.escalate else "",
              "words": "file" if args.words else f"faster-whisper:{s.whisper_model}"}
    doc, stats = process(source, words, clients, title=args.title or video.stem,
                         source_name=args.source or video.name, fingertips=fingertips,
                         threshold=s.confidence_threshold, models=models)
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
    pr.add_argument("--no-sam", action="store_true",
                    help="don't mask the lecturer with SAM 3.1 (saves 2 calls per keyframe)")
    pr.set_defaults(fn=_process)
    rd = sub.add_parser("render", help="re-render a saved LectureDoc JSON")
    rd.add_argument("doc")
    rd.add_argument("--out", required=True)
    rd.set_defaults(fn=_render)

    args = p.parse_args(argv)
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")
    for noisy in ("httpx", "httpx2", "openai", "huggingface_hub"):  # one line per HTTP call
        logging.getLogger(noisy).setLevel(logging.WARNING)
    args.fn(args)


if __name__ == "__main__":
    main()
