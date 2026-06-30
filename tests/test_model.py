import os
from kjsync import model


def build_sample():
    m = model.new_manifest("2026-06-30T00:00:00Z")
    c = model.add_course(m, "curso", "Curso", "https://x/products/curso")
    mod = model.set_module(c, "category-10", "Bloque 1", 1)
    model.set_lesson(mod, "1001", "01 - Intro", 1, "https://x/posts/1001",
                     {"wistia_id": "aaa", "materials": [], "has_description": True})
    return m


def test_iter_lessons_flattens():
    rows = model.iter_lessons(build_sample())
    assert len(rows) == 1
    r = rows[0]
    assert r["course_slug"] == "curso"
    assert r["module_title"] == "Bloque 1"
    assert r["post_id"] == "1001"
    assert r["fingerprint"]["wistia_id"] == "aaa"
    assert r["order"] == 1


def test_save_load_roundtrip(tmp_path):
    path = os.path.join(tmp_path, "m.json")
    m = build_sample()
    model.save_manifest(m, path)
    loaded = model.load_manifest(path)
    assert loaded == m


def test_load_missing_returns_none(tmp_path):
    assert model.load_manifest(os.path.join(tmp_path, "nope.json")) is None
