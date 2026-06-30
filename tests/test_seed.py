import os
from kjsync import seed, model, extract

FIXTURES = os.path.join(os.path.dirname(__file__), "fixtures")


def test_seed_builds_baseline_with_null_post_ids():
    m = seed.seed_manifest_from_csv(os.path.join(FIXTURES, "download_log_sample.csv"))
    rows = model.iter_lessons(m)
    assert len(rows) == 3
    assert all(r["post_id"] is None for r in rows)
    titles = {extract.norm(r["title"]) for r in rows}
    assert "bienvenidos" in titles
    assert "escalas" in titles
    # Un unico curso (Armonia Basica) con dos modulos
    assert len(m["courses"]) == 1
    course = next(iter(m["courses"].values()))
    assert len(course["modules"]) == 2
