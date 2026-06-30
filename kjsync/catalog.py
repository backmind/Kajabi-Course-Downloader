"""Catalogo/indice generico de un arbol de curso descargado (agnostico al curso)."""
import os
import csv
import json

from kjsync import transcode

MATERIAL_EXTS = {".pdf", ".zip", ".docx", ".pptx", ".xlsx", ".srt", ".txt", ".mp3", ".wav"}


def classify_kind(ext):
    e = (ext or "").lower()
    if e in transcode.VIDEO_EXTS:
        return "video"
    if e in MATERIAL_EXTS:
        return "material"
    return "other"


def catalog_entry(rel_path, size):
    meta = transcode.parse_path_metadata(rel_path)
    ext = os.path.splitext(rel_path)[1].lower()
    return {
        "course": meta["course"],
        "block": meta["block"],
        "track": meta["track"],
        "title": meta["title"],
        "relative_path": rel_path,
        "ext": ext,
        "kind": classify_kind(ext),
        "size": size,
    }


def build_catalog(root):
    entries = []
    for dirpath, _dirs, files in os.walk(root):
        for f in files:
            full = os.path.join(dirpath, f)
            rel = os.path.relpath(full, root)
            try:
                size = os.path.getsize(full)
            except OSError:
                size = 0
            entries.append(catalog_entry(rel, size))
    entries.sort(key=lambda e: e["relative_path"])
    return entries


_FIELDS = ["course", "block", "track", "title", "kind", "ext", "size", "relative_path"]


def write_json(entries, path):
    tmp = f"{path}.tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump({"generated_count": len(entries), "entries": entries}, f,
                  ensure_ascii=False, indent=2)
    os.replace(tmp, path)


def write_csv(entries, path):
    tmp = f"{path}.tmp"
    with open(tmp, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=_FIELDS)
        w.writeheader()
        for e in entries:
            w.writerow({k: e.get(k, "") for k in _FIELDS})
    os.replace(tmp, path)
