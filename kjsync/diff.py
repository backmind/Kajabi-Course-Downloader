"""Diff PURO de manifiestos: clasifica lecciones en nuevo/cambiado/renombrado/borrado."""
from kjsync import model
from kjsync.extract import norm


def _index(rows):
    by_pid = {}
    by_title = {}
    for r in rows:
        if r["post_id"]:
            by_pid[r["post_id"]] = r
        by_title.setdefault((norm(r["course_title"]), norm(r["title"])), r)
    return by_pid, by_title


def _ref(r, **extra):
    ref = {
        "course_slug": r["course_slug"],
        "module_title": r["module_title"],
        "title": r["title"],
        "url": r["url"],
        "post_id": r["post_id"],
    }
    ref.update(extra)
    return ref


def _course_bucket(courses, slug, title):
    if slug not in courses:
        courses[slug] = {"title": title, "new": [], "changed": [],
                         "renamed": [], "removed": [], "unchanged": 0}
    return courses[slug]


def diff_manifests(old, new):
    old_rows = list(model.iter_lessons(old))
    new_rows = list(model.iter_lessons(new))
    old_by_pid, old_by_title = _index(old_rows)

    courses = {}
    matched_old_keys = set()

    for r in new_rows:
        bucket = _course_bucket(courses, r["course_slug"], r["course_title"])
        match = None
        if r["post_id"] and r["post_id"] in old_by_pid:
            match = old_by_pid[r["post_id"]]
        else:
            match = old_by_title.get((norm(r["course_title"]), norm(r["title"])))
        if match is None:
            bucket["new"].append(_ref(r))
            continue
        # marcar el old emparejado
        matched_old_keys.add(match["post_id"] or ("title", match["course_slug"], norm(match["title"])))
        # renombrado y cambiado son independientes: una leccion puede ser ambos.
        is_renamed = bool(
            r["post_id"] and match["post_id"] == r["post_id"]
            and norm(match["title"]) != norm(r["title"])
        )
        is_changed = bool(
            r["fingerprint"] and match["fingerprint"]
            and r["fingerprint"] != match["fingerprint"]
        )
        if is_renamed:
            bucket["renamed"].append(_ref(r, old_title=match["title"]))
        if is_changed:
            bucket["changed"].append(_ref(r))
        if not is_renamed and not is_changed:
            bucket["unchanged"] += 1

    # borrados: lecciones de old con post_id no emparejadas
    for r in old_rows:
        if not r["post_id"]:
            continue
        if r["post_id"] in matched_old_keys:
            continue
        bucket = _course_bucket(courses, r["course_slug"], r["course_title"])
        bucket["removed"].append(_ref(r))

    totals = {"new": 0, "changed": 0, "renamed": 0, "removed": 0, "lessons": len(new_rows)}
    for b in courses.values():
        totals["new"] += len(b["new"])
        totals["changed"] += len(b["changed"])
        totals["renamed"] += len(b["renamed"])
        totals["removed"] += len(b["removed"])
    return {"courses": courses, "totals": totals}
