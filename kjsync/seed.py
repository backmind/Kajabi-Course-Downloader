"""Construye un manifiesto base aproximado desde download_log.csv (sin post_id)."""
import csv
from kjsync import model, extract


def seed_manifest_from_csv(csv_path, scanned_at=""):
    manifest = model.new_manifest(scanned_at)
    course_objs = {}
    module_objs = {}
    with open(csv_path, encoding="utf-8") as f:
        for order, row in enumerate(csv.DictReader(f), start=1):
            course_title = row.get("Course", "").strip()
            module_title = row.get("Module", "").strip()
            lesson_title = row.get("Lesson", "").strip()
            if not course_title or not lesson_title:
                continue
            slug = extract.norm(course_title) or course_title
            if slug not in course_objs:
                course_objs[slug] = model.add_course(manifest, slug, course_title, "")
            ckey = (slug, module_title)
            if ckey not in module_objs:
                cat_id = f"seed-{extract.norm(module_title)}"
                module_objs[ckey] = model.set_module(
                    course_objs[slug], cat_id, module_title, len(module_objs) + 1)
            model.set_lesson(module_objs[ckey], None, lesson_title, order, "")
    return manifest
