import os
import json

from kjsync import catalog


def test_classify_kind():
    assert catalog.classify_kind(".mp4") == "video"
    assert catalog.classify_kind(".PDF") == "material"
    assert catalog.classify_kind(".xyz") == "other"


def test_catalog_entry():
    e = catalog.catalog_entry("Curso X/Bloque 1/03 - La leccion.mp4", 12345)
    assert e["course"] == "Curso X"
    assert e["block"] == "Bloque 1"
    assert e["track"] == "03"
    assert e["title"] == "La leccion"
    assert e["ext"] == ".mp4"
    assert e["kind"] == "video"
    assert e["size"] == 12345
    assert e["relative_path"] == "Curso X/Bloque 1/03 - La leccion.mp4"


def test_build_and_write(tmp_path):
    root = tmp_path / "lib"
    d = root / "Curso A" / "Bloque 1"
    d.mkdir(parents=True)
    (d / "01 - intro.mp4").write_bytes(b"x" * 10)
    (d / "02 - notas.pdf").write_bytes(b"y" * 5)
    entries = catalog.build_catalog(str(root))
    assert len(entries) == 2
    kinds = {e["title"]: e["kind"] for e in entries}
    assert kinds["intro"] == "video"
    assert kinds["notas"] == "material"

    jpath = str(tmp_path / "cat.json")
    cpath = str(tmp_path / "cat.csv")
    catalog.write_json(entries, jpath)
    catalog.write_csv(entries, cpath)
    data = json.loads(open(jpath, encoding="utf-8").read())
    assert data["generated_count"] == 2
    assert len(data["entries"]) == 2
    csv_text = open(cpath, encoding="utf-8").read()
    assert "relative_path" in csv_text.splitlines()[0]
    assert "intro" in csv_text


def test_build_catalog_uses_forward_slashes(tmp_path):
    d = tmp_path / "lib" / "Curso" / "Bloque"
    d.mkdir(parents=True)
    (d / "01 - v.mp4").write_bytes(b"x")
    entries = catalog.build_catalog(str(tmp_path / "lib"))
    assert all("\\" not in e["relative_path"] for e in entries)
    assert entries[0]["relative_path"] == "Curso/Bloque/01 - v.mp4"
