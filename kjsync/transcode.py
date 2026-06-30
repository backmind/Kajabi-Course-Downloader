"""Transcodificacion generica a HEVC via ffmpeg (agnostica al curso)."""
import os
import re
import shutil
import subprocess
from concurrent.futures import ThreadPoolExecutor

VIDEO_EXTS = {".mp4", ".mov", ".mkv", ".avi", ".webm", ".m4v"}

_FALLBACK_ORDER = ["hevc_nvenc", "hevc_qsv", "hevc_amf", "libx265"]
_ALIASES = {"nvenc": "hevc_nvenc", "qsv": "hevc_qsv", "amf": "hevc_amf",
            "libx265": "libx265", "x265": "libx265", "auto": "auto"}


def _alias(short):
    return _ALIASES.get((short or "auto"), short)


def parse_hevc_encoders(text):
    """Extrae encoders HEVC de la salida de 'ffmpeg -encoders'."""
    found = []
    for line in (text or "").splitlines():
        m = re.match(r"\s+(\S{6})\s+(\S+)", line)
        if not m or m.group(1)[0] != "V":
            continue
        name = m.group(2)
        if name == "libx265" or name.startswith("hevc_"):
            found.append(name)
    return found


def choose_encoder(preferred, available):
    """'auto' elige el mejor hardware disponible y cae a libx265; un encoder
    concreto se usa si esta, si no cae por el orden de fallback. None si nada."""
    available = list(available or [])
    pref = _alias(preferred or "auto")
    if pref != "auto" and pref in available:
        return pref
    for enc in _FALLBACK_ORDER:
        if enc in available:
            return enc
    return None
