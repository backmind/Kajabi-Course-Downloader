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
