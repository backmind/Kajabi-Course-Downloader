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
