import os

from kjsync import extract

FIXTURES = os.path.join(os.path.dirname(__file__), "fixtures")


def _read_fixture(name):
    with open(os.path.join(FIXTURES, name), encoding="utf-8") as f:
        return f.read()


def test_norm_strips_prefix_and_lowercases():
    assert extract.norm("01 - Las Septimas") == "las septimas"
    assert extract.norm("12. Un Modo. Tres escalas.") == "un modo tres escalas"


def test_extract_post_id_from_posts_url():
    href = "https://school.example.com/products/demo-course/categories/123/posts/987654"
    assert extract.extract_post_id(href) == "987654"


def test_extract_post_id_fallback_last_segment():
    assert extract.extract_post_id("https://x.com/a/b/cde?q=1") == "cde"
    assert extract.extract_post_id(None) is None


def test_extract_slug():
    assert extract.extract_slug("https://school.example.com/products/sample-course") == "sample-course"
    assert extract.extract_slug("https://school.example.com/products/sample-course/categories/1") == "sample-course"
    assert extract.extract_slug(None) is None


def test_extract_category_id_skips_phantoms():
    assert extract.extract_category_id("#category-555") == "category-555"
    assert extract.extract_category_id("#") is None
    assert extract.extract_category_id("#sidebar-modal") is None
    assert extract.extract_category_id(None) is None


def test_parse_course_outline_skips_phantom_and_dedupes():
    modules = extract.parse_course_outline(_read_fixture("outline_sample.html"))
    # La cabecera fantasma (data-target="#") no debe producir modulo
    assert [m["title"] for m in modules] == ["Bloque 1", "Bloque 2"]
    assert modules[0]["category_id"] == "category-10"
    assert [l["title"] for l in modules[0]["lessons"]] == ["01 - Intro", "02 - Escalas"]
    assert modules[0]["lessons"][0]["post_id"] == "1001"
    assert modules[1]["lessons"][0]["post_id"] == "2001"
    # Total de lecciones sin duplicar = 3
    total = sum(len(m["lessons"]) for m in modules)
    assert total == 3


def test_lesson_fingerprint_fields():
    html = _read_fixture("lesson_sample.html")
    assert extract.extract_wistia_id(html) == "glxqbp7vs5"
    mats = extract.parse_materials(html)
    assert [m["name"] for m in mats] == ["Letra y acordes", "Partitura"]
    assert mats[0]["url"].startswith("https://files.example.com/letra.pdf")
    assert extract.has_description(html) is True
    fp = extract.lesson_fingerprint(html)
    assert fp == {"wistia_id": "glxqbp7vs5", "materials": ["Letra y acordes", "Partitura"], "has_description": True}


def test_lesson_fingerprint_empty():
    fp = extract.lesson_fingerprint("<html><body></body></html>")
    assert fp == {"wistia_id": None, "materials": [], "has_description": False}


def test_extract_wistia_id_alt_patterns():
    assert extract.extract_wistia_id('<a href="https://wistia.com/medias/abc123">') == "abc123"
    assert extract.extract_wistia_id('src=".../embed/medias/xyz789.m3u8"') == "xyz789"
