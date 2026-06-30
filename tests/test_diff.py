from kjsync import diff, model


def mk(slug, title, lessons):
    """lessons: list of (post_id, title, fingerprint)"""
    m = model.new_manifest("t")
    c = model.add_course(m, slug, title, "")
    mod = model.set_module(c, "cat-1", "Bloque 1", 1)
    for i, (pid, ltitle, fp) in enumerate(lessons, start=1):
        model.set_lesson(mod, pid, ltitle, i, f"/posts/{pid}" if pid else "", fp)
    return m


def test_new_lesson_detected():
    old = mk("curso", "Curso", [("1", "Intro", None)])
    new = mk("curso", "Curso", [("1", "Intro", None), ("2", "Escalas", None)])
    d = diff.diff_manifests(old, new)
    assert [r["title"] for r in d["courses"]["curso"]["new"]] == ["Escalas"]
    assert d["totals"]["new"] == 1


def test_removed_lesson_detected():
    old = mk("curso", "Curso", [("1", "Intro", None), ("2", "Escalas", None)])
    new = mk("curso", "Curso", [("1", "Intro", None)])
    d = diff.diff_manifests(old, new)
    assert [r["title"] for r in d["courses"]["curso"]["removed"]] == ["Escalas"]
    assert d["totals"]["removed"] == 1


def test_renamed_lesson_same_post_id():
    old = mk("curso", "Curso", [("1", "Intro", None)])
    new = mk("curso", "Curso", [("1", "Introduccion", None)])
    d = diff.diff_manifests(old, new)
    assert d["courses"]["curso"]["renamed"][0]["old_title"] == "Intro"
    assert d["totals"]["renamed"] == 1
    assert d["totals"]["new"] == 0


def test_changed_fingerprint():
    fp_a = {"wistia_id": "aaa", "materials": [], "has_description": True}
    fp_b = {"wistia_id": "bbb", "materials": [], "has_description": True}
    old = mk("curso", "Curso", [("1", "Intro", fp_a)])
    new = mk("curso", "Curso", [("1", "Intro", fp_b)])
    d = diff.diff_manifests(old, new)
    assert d["totals"]["changed"] == 1


def test_no_change_when_fingerprint_missing_on_new():
    fp_a = {"wistia_id": "aaa", "materials": [], "has_description": True}
    old = mk("curso", "Curso", [("1", "Intro", fp_a)])
    new = mk("curso", "Curso", [("1", "Intro", None)])  # estructural: sin huella
    d = diff.diff_manifests(old, new)
    assert d["totals"]["changed"] == 0
    assert d["courses"]["curso"]["unchanged"] == 1


def test_positional_insert_no_false_new():
    # Insertar al principio NO debe marcar las demas como nuevas (emparejan por post_id)
    old = mk("curso", "Curso", [("1", "A", None), ("2", "B", None)])
    new = mk("curso", "Curso", [("9", "Nueva", None), ("1", "A", None), ("2", "B", None)])
    d = diff.diff_manifests(old, new)
    assert [r["title"] for r in d["courses"]["curso"]["new"]] == ["Nueva"]
    assert d["totals"]["new"] == 1


def test_title_fallback_when_no_post_id():
    # Semilla sin post_id empareja por titulo normalizado
    old = mk("curso", "Curso", [(None, "01 - Intro", None)])
    new = mk("curso", "Curso", [("1", "Intro", None)])
    d = diff.diff_manifests(old, new)
    assert d["totals"]["new"] == 0
    assert d["courses"]["curso"]["unchanged"] == 1


def test_renamed_and_changed_both_classified():
    fp_a = {"wistia_id": "aaa", "materials": [], "has_description": True}
    fp_b = {"wistia_id": "bbb", "materials": [], "has_description": True}
    old = mk("curso", "Curso", [("1", "Intro", fp_a)])
    new = mk("curso", "Curso", [("1", "Introduccion", fp_b)])
    d = diff.diff_manifests(old, new)
    assert d["totals"]["renamed"] == 1
    assert d["totals"]["changed"] == 1
    assert d["courses"]["curso"]["unchanged"] == 0


def test_title_fallback_matches_across_differing_course_slugs():
    # Seed baseline: course_slug derived from CSV title (norm), post_id=None.
    old = model.new_manifest("t")
    c_old = model.add_course(old, "demo course", "Demo Course!", "")
    mo = model.set_module(c_old, "seed-x", "Bloque", 1)
    model.set_lesson(mo, None, "01 - Intro Lesson", 1, "")
    # Live scan: product slug differs, post_id present.
    new = model.new_manifest("t")
    c_new = model.add_course(new, "demo-course", "Demo Course!", "")
    mn = model.set_module(c_new, "cat-1", "Bloque", 1)
    model.set_lesson(mn, "1000001", "Intro Lesson", 1, "/posts/1000001")
    d = diff.diff_manifests(old, new)
    assert d["totals"]["new"] == 0
    assert d["courses"]["demo-course"]["unchanged"] == 1
