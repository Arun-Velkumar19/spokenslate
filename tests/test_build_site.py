import importlib.util
from pathlib import Path

from fixtures import leonard_timeline

from spokenslate.spec import LectureDoc

_spec = importlib.util.spec_from_file_location(
    "build_site", Path(__file__).resolve().parents[1] / "scripts" / "build_site.py")
site = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(site)


def test_site_has_index_pages_and_escapes_titles(tmp_path):
    doc = LectureDoc(title="Calc <2>", source="credit & license", duration=140, words=[],
                     elements=leonard_timeline().all(), phrases=[], resolutions=[])
    src = tmp_path / "calc.json"
    src.write_text(doc.model_dump_json())
    written = site.build([(src, "calc-2")], tmp_path / "public")
    out = tmp_path / "public"
    assert {p.name for p in written} == {"calc-2.html", "index.html"}
    assert (out / ".nojekyll").exists()
    index = (out / "index.html").read_text()
    assert '<a href="calc-2.html">Calc &lt;2&gt;</a>' in index
    assert "3 board steps" in index and "credit &amp; license" in index
    assert index.startswith("<!doctype html>") and 'lang="en"' in index
    assert "<h2>Lectures</h2>" in index and "unresolved" in index
