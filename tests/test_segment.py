"""SAM 3.1 masks: parsing the API's token text, the client call, and the board-read gate.

tests/data/sam_person_480x352.txt is a real sam-3.1 response (Oct 30) for "person" on a
480x352 frame of MIT OCW 18.06 Lecture 2 (Gilbert Strang, CC BY-NC-SA): a box and a
lossless mask of the lecturer, no image data.
"""

from pathlib import Path
from types import SimpleNamespace as NS

import numpy as np
from meta_sam_parser._mask_codec import _encode_raster  # one_bit encoder, test-only use

from spokenslate.models.segment import MetaSAM, parse_sam_text

REAL = (Path(__file__).parent / "data" / "sam_person_480x352.txt").read_text()


def one_bit(rows: list[str]) -> tuple[int, int, str]:
    bits = bytes(int(c) for r in rows for c in r)
    return len(rows), len(rows[0]), _encode_raster(bits, len(rows[0]), len(rows))


def obj(x1, y1, rows, conf=0.9, w=20, h=10, dx=0, dy=0):
    mh, mw, payload = one_bit(rows)
    return (f"<|box;x1={x1};y1={y1};x2={x1 + mw};y2={y1 + mh};w={w};h={h};c={conf}|>"
            f"<|mask;x={dx};y={dy};c={conf};data={mh},{mw},{payload}|>")


def test_real_sam_response_decodes_to_the_lecturer():
    m = parse_sam_text(REAL, 352, 480)
    assert m.shape == (352, 480) and m.dtype == np.uint8
    assert (m == 255).sum() == 18429                 # the raster's ones, placed at the box
    assert m[195, 345] == 255                        # pointing hand
    assert m[100, 50] == 0 and m[20, 300] == 0       # board writing stays visible
    up = parse_sam_text(REAL, 704, 960)              # frame was downscaled for upload
    assert up.shape == (704, 960) and abs((up > 0).sum() - 4 * 18429) < 0.02 * 4 * 18429


def test_objects_are_placed_unioned_and_filtered():
    text = "<0f>0" + obj(2, 1, ["11", "11"]) + obj(10, 5, ["1"], dx=1, dy=2) \
        + obj(15, 0, ["1"], conf=0.2)
    m = parse_sam_text(text, 10, 20)
    assert set(zip(*np.nonzero(m))) == {(1, 2), (1, 3), (2, 2), (2, 3), (7, 11)}
    assert m[0, 15] == 0                              # low-confidence object dropped


def test_bad_output_means_no_mask_never_a_crash():
    assert parse_sam_text("", 10, 20) is None
    assert parse_sam_text("I can't segment that.", 10, 20) is None
    assert parse_sam_text("<|mask;x=0;y=0;data=1,1,!!|>", 10, 20) is None   # mask w/o box
    assert parse_sam_text(obj(0, 0, ["1"]).replace("data=1,1,", "data=9,9,"), 10, 20) is None
    assert parse_sam_text(obj(0, 0, ["1"], conf=0.1), 10, 20) is None       # nothing confident


class FakeClient:
    def __init__(self, text=REAL, fail=False):
        self.text, self.fail, self.deleted, self.requests = text, fail, [], []
        self.files = NS(create=self._upload, delete=self.deleted.append)
        self.responses = NS(create=self._respond)

    def _upload(self, file, purpose):
        assert purpose == "user_data" and file[2] == "image/jpeg"
        return NS(id="file-1")

    def _respond(self, **kw):
        self.requests.append(kw)
        if self.fail:
            raise RuntimeError("503")
        return NS(output=[NS(content=[NS(type="output_text", text=self.text)])])


def test_metasam_request_shape_and_cleanup():
    c = FakeClient()
    sam = MetaSAM("k", "u", client=c)
    m = sam.person_mask(np.zeros((352, 480, 3), np.uint8))
    assert m is not None and m[195, 345] == 255 and sam.calls == 2
    (req,) = c.requests
    assert req["model"] == "sam-3.1" and req["stream"] is False
    content = req["input"][0]["content"]
    assert content[0] == {"type": "input_text", "text": "person"}
    assert content[1] == {"type": "input_image", "file_id": "file-1"}
    assert req["metadata"] == {"mask_encoding": "lossless", "include_confidence": "true"}
    assert c.deleted == ["file-1"]                   # uploaded frame not left on the server


def test_metasam_failure_is_no_mask():
    c = FakeClient(fail=True)
    assert MetaSAM("k", "u", client=c).person_mask(np.zeros((8, 8, 3), np.uint8)) is None
    assert c.deleted == ["file-1"]
