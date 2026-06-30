"""Esquema del manifiesto de sincronizacion y E/S atomica."""
import json
import os


def new_manifest(scanned_at):
    return {"scanned_at": scanned_at, "courses": {}}


def add_course(manifest, slug, title, url):
    course = {"title": title, "url": url, "modules": {}}
    manifest["courses"][slug] = course
    return course


def set_module(course, category_id, title, order):
    module = {"title": title, "order": order, "lessons": {}}
    course["modules"][category_id] = module
    return module


def set_lesson(module, post_id, title, order, url, fingerprint=None):
    key = post_id if post_id else f"_pos{order}"
    module["lessons"][key] = {
        "post_id": post_id,
        "title": title,
        "order": order,
        "url": url,
        "fingerprint": fingerprint,
    }


def iter_lessons(manifest):
    rows = []
    for slug, course in manifest.get("courses", {}).items():
        for module in course.get("modules", {}).values():
            for lesson in module.get("lessons", {}).values():
                rows.append({
                    "course_slug": slug,
                    "course_title": course.get("title", ""),
                    "module_title": module.get("title", ""),
                    "post_id": lesson.get("post_id"),
                    "title": lesson.get("title", ""),
                    "order": lesson.get("order"),
                    "url": lesson.get("url", ""),
                    "fingerprint": lesson.get("fingerprint"),
                })
    return rows


def save_manifest(manifest, path):
    tmp = f"{path}.tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(manifest, f, ensure_ascii=False, indent=2)
    os.replace(tmp, path)


def load_manifest(path):
    if not os.path.exists(path):
        return None
    with open(path, encoding="utf-8") as f:
        return json.load(f)
