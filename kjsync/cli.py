"""Comandos scan / diff / sync (orquestacion del motor)."""
import os
from datetime import datetime, timezone
from dotenv import load_dotenv

from kjsync import browser, scan, diff as diffmod, report as reportmod, model, seed


def _now():
    return datetime.now(timezone.utc).isoformat()


def _env():
    load_dotenv()
    return (os.getenv("KAJABI_EMAIL"), os.getenv("KAJABI_PASSWORD"),
            (os.getenv("KAJABI_URL") or "").rstrip("/"))


def _scan_to_manifest(args):
    email, password, base = _env()
    driver = browser.build_driver(headless=args.headless)
    try:
        if not browser.login(driver, base, email, password):
            print("ERROR: login fallido")
            return None
        course_filter = args.course or None
        return scan.scan_library(driver, base, _now(), course_filter=course_filter, deep=args.deep)
    finally:
        driver.quit()


def cmd_scan(args):
    manifest = _scan_to_manifest(args)
    if manifest is None:
        return 1
    model.save_manifest(manifest, args.manifest)
    print(f"Manifiesto escrito en {args.manifest}")
    return 0


def cmd_diff(args):
    new = model.load_manifest(args.manifest)
    if new is None:
        print(f"ERROR: no existe {args.manifest}; corre 'scan' primero")
        return 1
    # Para 'diff' suelto comparamos el manifiesto guardado contra la base sembrada
    baseline = seed.seed_manifest_from_csv(args.seed_csv, _now()) if args.seed_csv and os.path.exists(args.seed_csv) else model.new_manifest(_now())
    result = diffmod.diff_manifests(baseline, new)
    md = reportmod.render_report(result, new.get("scanned_at", ""), args.deep)
    with open(args.report, "w", encoding="utf-8") as f:
        f.write(md)
    print(md)
    return 0


def _transcode_config():
    import configparser
    c = configparser.ConfigParser()
    c.read("config.ini")
    if not c.has_section("Transcode"):
        return {}
    return {
        "encoder": c.get("Transcode", "encoder", fallback="auto"),
        "crf": c.getint("Transcode", "crf", fallback=23),
        "cq": c.getint("Transcode", "cq", fallback=28),
        "preset": c.get("Transcode", "preset", fallback="") or None,
        "tag": c.get("Transcode", "tag", fallback="h265"),
        "copy_nonvideo": c.getboolean("Transcode", "copy_nonvideo", fallback=True),
        "jobs": c.getint("Transcode", "jobs", fallback=1),
    }


def _seed_or_empty(args):
    if args.seed_csv and os.path.exists(args.seed_csv):
        print(f"Sin manifiesto previo; sembrando base desde {args.seed_csv}")
        return seed.seed_manifest_from_csv(args.seed_csv, _now())
    return model.new_manifest(_now())


def _restrict_to_scanned_courses(baseline, scanned):
    """Para sync acotado (--course): limita la base a los cursos escaneados
    (casando por slug o por titulo normalizado) para no reportar como borrados
    los cursos no escaneados."""
    from kjsync.extract import norm
    scanned_slugs = set(scanned.get("courses", {}).keys())
    scanned_titles = {norm(c.get("title", "")) for c in scanned.get("courses", {}).values()}
    out = model.new_manifest(baseline.get("scanned_at", ""))
    for slug, course in baseline.get("courses", {}).items():
        if slug in scanned_slugs or norm(course.get("title", "")) in scanned_titles:
            out["courses"][slug] = course
    return out


def _merge_scanned_into_prior(prior, scanned):
    """Funde los cursos escaneados sobre el manifiesto previo (sin perder los
    cursos no escaneados); casa por slug."""
    merged = {"scanned_at": scanned.get("scanned_at", ""),
              "courses": dict(prior.get("courses", {}))}
    for slug, course in scanned.get("courses", {}).items():
        merged["courses"][slug] = course
    return merged


def _drop_lessons(manifest, post_ids):
    """Elimina del manifiesto las lecciones con esos post_id (descargas fallidas),
    para que reaparezcan como delta en la proxima sync."""
    for course in manifest.get("courses", {}).values():
        for moduleobj in course.get("modules", {}).values():
            doomed = [k for k, l in list(moduleobj.get("lessons", {}).items())
                      if l.get("post_id") in post_ids]
            for k in doomed:
                del moduleobj["lessons"][k]


def cmd_sync(args):
    prior_file = model.load_manifest(args.manifest)
    baseline = prior_file if prior_file is not None else _seed_or_empty(args)
    new = _scan_to_manifest(args)
    if new is None:
        return 1

    diff_baseline = baseline
    if args.course:
        diff_baseline = _restrict_to_scanned_courses(baseline, new)

    result = diffmod.diff_manifests(diff_baseline, new)
    md = reportmod.render_report(result, new.get("scanned_at", ""), args.deep)
    with open(args.report, "w", encoding="utf-8") as f:
        f.write(md)
    print(md)
    print(f"\nInforme escrito en {args.report}")

    to_download = []
    for b in result["courses"].values():
        to_download.extend(b["new"])
        to_download.extend(b["changed"])
    print(f"\nA descargar (nuevo + cambiado): {len(to_download)} lecciones")

    if args.dry_run:
        print("--dry-run: no se descarga nada. (Manifiesto NO actualizado.)")
        return 0
    if not args.yes and to_download:
        resp = input("Proceder con la descarga? [s/N] ").strip().lower()
        if resp not in ("s", "si", "y", "yes"):
            print("Cancelado. (Manifiesto NO actualizado.)")
            return 0

    failed_pids = set()
    if to_download:
        from kjsync import download
        email, password, base = _env()
        driver = browser.build_driver(headless=args.headless)
        try:
            if not browser.login(driver, base, email, password):
                print("ERROR: login fallido; no se descarga el delta. Manifiesto NO actualizado.")
                return 1
            new_by_pid = {r["post_id"]: r for r in model.iter_lessons(new) if r["post_id"]}
            for ref in to_download:
                full = new_by_pid.get(ref["post_id"], ref)
                lesson = {"order": full.get("order", 1), "title": full["title"], "url": full["url"]}
                safe_mod = "".join(c if c.isalnum() or c in " ._-" else "_" for c in ref["module_title"])[:200]
                dest = os.path.join(args.staging_dir, ref["course_slug"], safe_mod)
                print(f"  -> {ref['course_slug']} / {ref['title']}")
                status = download.download_lesson(driver, lesson, dest)
                if status.get("video") == "Failed" or status.get("materials") == "Failed":
                    failed_pids.add(ref["post_id"])
                    print(f"     AVISO: descarga incompleta, se reintentara en la proxima sync: {ref['title']}")
        finally:
            driver.quit()

    if failed_pids:
        _drop_lessons(new, failed_pids)

    if getattr(args, "transcode", False) and not args.dry_run and to_download:
        from kjsync import transcode as tc
        if tc.is_ffmpeg_available():
            out = args.transcode_output or (args.staging_dir.rstrip("/\\") + "_hevc")
            print(f"\nTranscodificando staging -> {out}")
            tc.transcode_tree(args.staging_dir, out, progress=print, **_transcode_config())
        else:
            print("AVISO: --transcode pedido pero ffmpeg no esta disponible; se omite.")

    if prior_file is not None and args.course:
        to_save = _merge_scanned_into_prior(prior_file, new)
    else:
        to_save = new
    model.save_manifest(to_save, args.manifest)
    print(f"Manifiesto actualizado en {args.manifest}")
    return 0


def cmd_transcode(args):
    from kjsync import transcode
    out = args.output or (args.input.rstrip("/\\") + "_hevc")
    summary = transcode.transcode_tree(
        args.input, out, encoder=args.encoder, crf=args.crf, cq=args.cq,
        preset=(args.preset or None), tag=args.tag, res_tag=args.res_tag,
        copy_nonvideo=args.copy_nonvideo, embed_metadata=args.embed_metadata,
        replace=args.replace, jobs=args.jobs, dry_run=args.dry_run)
    if summary.get("error"):
        return 1
    print(f"\nResumen: {summary['transcoded']} transcodificados, {summary['copied']} copiados, "
          f"{summary['skipped']} saltados, {len(summary['failed'])} fallidos -> {out}")
    return 1 if summary["failed"] else 0


def cmd_catalog(args):
    from kjsync import catalog
    entries = catalog.build_catalog(args.input)
    catalog.write_json(entries, args.json)
    catalog.write_csv(entries, args.csv)
    vids = sum(1 for e in entries if e["kind"] == "video")
    print(f"Catalogo: {len(entries)} ficheros ({vids} videos) -> {args.json} ; {args.csv}")
    return 0
