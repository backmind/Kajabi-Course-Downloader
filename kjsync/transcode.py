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


def quality_args(encoder, crf, cq, preset):
    if encoder == "libx265":
        return ["-c:v", "libx265", "-preset", preset or "medium", "-crf", str(crf), "-tag:v", "hvc1"]
    if encoder == "hevc_nvenc":
        return ["-c:v", "hevc_nvenc", "-preset", preset or "p5", "-rc", "vbr", "-cq", str(cq), "-tag:v", "hvc1"]
    if encoder == "hevc_qsv":
        return ["-c:v", "hevc_qsv", "-global_quality", str(cq), "-tag:v", "hvc1"]
    if encoder == "hevc_amf":
        return ["-c:v", "hevc_amf", "-quality", "balanced", "-qp_i", str(cq), "-qp_p", str(cq), "-tag:v", "hvc1"]
    return ["-c:v", encoder, "-tag:v", "hvc1"]


def build_ffmpeg_cmd(src, dst, encoder, crf=23, cq=28, preset=None, metadata_args=None):
    cmd = ["ffmpeg", "-y", "-hide_banner", "-i", src]
    cmd += quality_args(encoder, crf, cq, preset)
    cmd += ["-c:a", "copy"]
    if metadata_args:
        cmd += list(metadata_args)
    cmd += [dst]
    return cmd


def output_name(src_name, tag):
    stem, ext = os.path.splitext(src_name)
    return f"{stem} [{tag}]{ext}"


def already_transcoded(src_name, tag):
    return f"[{tag}]" in src_name


def parse_path_metadata(rel_path):
    parts = [p for p in re.split(r"[\\/]+", rel_path) if p]
    course = parts[0] if len(parts) >= 1 else ""
    block = parts[1] if len(parts) >= 3 else ""
    fname = os.path.splitext(parts[-1])[0] if parts else ""
    m = re.match(r"^\s*(\d+)\s*-\s*(.+)$", fname)
    if m:
        track, title = m.group(1), m.group(2).strip()
    else:
        track, title = "", fname
    return {"course": course, "block": block, "track": track, "title": title}


def build_metadata_args(meta):
    args = []
    if meta.get("title"):
        args += ["-metadata", f"title={meta['title']}"]
    if meta.get("course"):
        args += ["-metadata", f"album={meta['course']}"]
    if meta.get("block"):
        args += ["-metadata", f"album_artist={meta['block']}"]
    if meta.get("track"):
        args += ["-metadata", f"track={meta['track']}"]
    return args


def plan_tree(rel_files, video_exts, tag):
    plan = {"transcode": [], "copy": [], "skip": []}
    for rel in rel_files:
        ext = os.path.splitext(rel)[1].lower()
        name = os.path.basename(rel)
        if ext in video_exts:
            if already_transcoded(name, tag):
                plan["skip"].append(rel)
            else:
                plan["transcode"].append(rel)
        else:
            plan["copy"].append(rel)
    return plan


def is_ffmpeg_available():
    return shutil.which("ffmpeg") is not None


def detect_hevc_encoders():
    if not is_ffmpeg_available():
        return []
    try:
        out = subprocess.run(["ffmpeg", "-hide_banner", "-encoders"],
                             capture_output=True, text=True, timeout=30)
        return parse_hevc_encoders(out.stdout)
    except Exception:
        return []


def probe_height(path):
    if shutil.which("ffprobe") is None:
        return None
    try:
        out = subprocess.run(["ffprobe", "-v", "error", "-select_streams", "v:0",
                              "-show_entries", "stream=height", "-of", "csv=p=0", path],
                             capture_output=True, text=True, timeout=30)
        line = out.stdout.strip().splitlines()[0]
        return int(line)
    except Exception:
        return None


def transcode_file(src, dst, cmd):
    os.makedirs(os.path.dirname(dst) or ".", exist_ok=True)
    try:
        r = subprocess.run(cmd, capture_output=True, text=True)
        if r.returncode == 0 and os.path.exists(dst) and os.path.getsize(dst) > 0:
            return True
        if os.path.exists(dst) and os.path.getsize(dst) == 0:
            os.remove(dst)
        return False
    except Exception:
        return False


def transcode_tree(input_root, output_root, encoder="auto", crf=23, cq=28, preset=None,
                   tag="h265", res_tag=False, copy_nonvideo=True, embed_metadata=False,
                   replace=False, jobs=1, dry_run=False, progress=print):
    if not is_ffmpeg_available():
        progress("ERROR: ffmpeg no encontrado en PATH.")
        return {"error": "no-ffmpeg"}
    available = detect_hevc_encoders()
    enc = choose_encoder(encoder, available)
    if enc is None:
        progress("ERROR: ningun encoder HEVC disponible.")
        return {"error": "no-encoder"}
    if _alias(encoder) != "auto" and enc != _alias(encoder):
        progress(f"AVISO: encoder '{encoder}' no disponible; usando '{enc}'.")
    progress(f"Encoder: {enc}")

    rel_files = []
    for dirpath, _dirs, files in os.walk(input_root):
        for f in files:
            rel_files.append(os.path.relpath(os.path.join(dirpath, f), input_root))
    plan = plan_tree(rel_files, VIDEO_EXTS, tag)
    progress(f"Plan: {len(plan['transcode'])} transcode, {len(plan['copy'])} copy, {len(plan['skip'])} skip")

    summary = {"encoder": enc, "transcoded": 0, "copied": 0,
               "skipped": len(plan["skip"]), "failed": []}

    if dry_run:
        for rel in plan["transcode"]:
            progress(f"  [T] {rel}")
        if copy_nonvideo:
            for rel in plan["copy"]:
                progress(f"  [C] {rel}")
        summary["dry_run"] = True
        return summary

    if copy_nonvideo:
        for rel in plan["copy"]:
            dst = os.path.join(output_root, rel)
            os.makedirs(os.path.dirname(dst) or ".", exist_ok=True)
            if not os.path.exists(dst):
                shutil.copy2(os.path.join(input_root, rel), dst)
            summary["copied"] += 1

    def _do(rel):
        src = os.path.join(input_root, rel)
        local_tag = tag
        if res_tag:
            h = probe_height(src)
            if h:
                local_tag = f"{tag}_{h}p"
        dst_name = output_name(os.path.basename(rel), local_tag)
        dst = os.path.join(output_root, os.path.dirname(rel), dst_name)
        if os.path.exists(dst) and os.path.getsize(dst) > 0:
            return ("skip", rel)
        meta_args = build_metadata_args(parse_path_metadata(rel)) if embed_metadata else None
        cmd = build_ffmpeg_cmd(src, dst, enc, crf=crf, cq=cq, preset=preset, metadata_args=meta_args)
        ok = transcode_file(src, dst, cmd)
        if ok and replace:
            try:
                os.remove(src)
            except OSError:
                pass
        return ("ok" if ok else "fail", rel)

    if jobs > 1:
        with ThreadPoolExecutor(max_workers=jobs) as ex:
            results = list(ex.map(_do, plan["transcode"]))
    else:
        results = [_do(rel) for rel in plan["transcode"]]

    for status, rel in results:
        if status == "ok":
            summary["transcoded"] += 1
            progress(f"  OK {rel}")
        elif status == "skip":
            summary["skipped"] += 1
        else:
            summary["failed"].append(rel)
            progress(f"  FALLO {rel}")
    return summary
