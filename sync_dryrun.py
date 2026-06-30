"""
Dry-run de solo lectura para validar la deteccion de delta (nuevo/cambiado/borrado).

NO descarga nada. NO mueve nada. Solo hace login, recorre la estructura del sitio
(cursos -> modulos -> lecciones), extrae la identidad estable (slug / category-id /
post-id) y escribe:
  - scan_manifest_dryrun.json : estado actual escaneado
  - sync_report_dryrun.md      : informe legible (incluye comparacion aproximada
                                 contra download_log.csv para marcar lo "probablemente nuevo")

Uso:
  uv run sync_dryrun.py --courses-only            # smoke test minimo: solo lista cursos
  uv run sync_dryrun.py --course piano-basico     # escanea un curso (substring del slug/titulo)
  uv run sync_dryrun.py                            # escanea todos los cursos (estructural)

Flags:
  --course <txt>   : filtra cursos cuyo slug o titulo contenga <txt> (repetible via coma)
  --courses-only   : no entra en los cursos, solo enumera la biblioteca
  --limit <n>      : limita el numero de cursos a escanear
  --headless       : Chrome sin ventana (no recomendado en la primera corrida)
"""

import os
import re
import sys
import csv
import json
import time
import argparse
from datetime import datetime, timezone

from dotenv import load_dotenv
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import NoSuchElementException
from webdriver_manager.chrome import ChromeDriverManager

if sys.platform == "win32":
    import codecs
    sys.stdout = codecs.getwriter("utf-8")(sys.stdout.detach())
    sys.stderr = codecs.getwriter("utf-8")(sys.stderr.detach())

load_dotenv()
EMAIL = os.getenv("KAJABI_EMAIL")
PASSWORD = os.getenv("KAJABI_PASSWORD")
KAJABI_URL = (os.getenv("KAJABI_URL") or "").rstrip("/")

MANIFEST_OUT = "scan_manifest_dryrun.json"
REPORT_OUT = "sync_report_dryrun.md"
LOG_FILE = "download_log.csv"


def log(msg):
    print(msg, flush=True)


def norm(s):
    """Normalizacion suave para comparar titulos entre el sitio y el CSV."""
    s = re.sub(r"^\s*\d+\s*[-.]\s*", "", s or "")          # quita prefijo numerico "01 - "
    s = "".join(c if c.isalnum() or c.isspace() else " " for c in s)
    return re.sub(r"\s+", " ", s).strip().lower()


def extract_post_id(href):
    """Intenta extraer un ID de post estable de la URL de la leccion."""
    if not href:
        return None
    for pat in (r"/posts/([A-Za-z0-9]+)", r"/posts/([A-Za-z0-9]+)/?", r"post[_-]?id=([A-Za-z0-9]+)"):
        m = re.search(pat, href)
        if m:
            return m.group(1)
    # Fallback: ultimo segmento no vacio de la ruta
    tail = [seg for seg in href.split("?")[0].split("/") if seg]
    return tail[-1] if tail else None


def extract_category_id(data_target, fallback):
    if data_target and data_target not in ("#", "#sidebar-modal"):
        return data_target.lstrip("#")
    return fallback


def build_driver(headless):
    options = Options()
    if headless:
        options.add_argument("--headless=new")
    options.add_argument("--start-maximized")
    options.add_experimental_option("prefs", {
        "profile.default_content_setting_values.notifications": 2,
    })
    return webdriver.Chrome(service=Service(ChromeDriverManager().install()), options=options)


def login(driver):
    log(f"Login en {KAJABI_URL}/login ...")
    driver.get(f"{KAJABI_URL}/login")
    WebDriverWait(driver, 30).until(EC.presence_of_element_located((By.ID, "member_email"))).send_keys(EMAIL)
    driver.find_element(By.ID, "member_password").send_keys(PASSWORD)
    driver.find_element(By.XPATH, "//button[@type='submit']").click()
    time.sleep(6)
    url = driver.current_url
    if any(k in url for k in ("library", "dashboard", "admin")) or "login" not in url:
        log(f"  OK login -> {url}")
        return True
    log(f"  AVISO: la URL tras login es {url} (puede requerir 2FA/captcha; resuelvelo en la ventana)")
    # Dar tiempo a resolver 2FA manualmente
    time.sleep(20)
    return "login" not in driver.current_url


def get_courses(driver):
    log("Abriendo biblioteca ...")
    driver.get(f"{KAJABI_URL}/library")
    time.sleep(5)
    cards = driver.find_elements(By.CSS_SELECTOR, "div.product")
    courses = []
    for card in cards:
        try:
            title = card.find_element(By.CSS_SELECTOR, "h4.product__title").text.strip()
        except NoSuchElementException:
            title = card.text.strip().split("\n")[0]
        try:
            url = card.find_element(By.CSS_SELECTOR, "a[href*='/products/']").get_attribute("href")
        except NoSuchElementException:
            continue
        if "/communities/" in url:
            continue
        slug_m = re.search(r"/products/([^/?#]+)", url)
        courses.append({"title": title, "url": url, "slug": slug_m.group(1) if slug_m else url})
    return courses


def scan_course(driver, course):
    log(f"\n== Curso: {course['title']}  ({course['slug']})")
    driver.get(course["url"])
    WebDriverWait(driver, 30).until(EC.presence_of_element_located((By.TAG_NAME, "body")))
    time.sleep(4)

    headers = driver.find_elements(By.CSS_SELECTOR, "h3.product-outline-category")
    if not headers:
        log("  AVISO: no se encontraron modulos (h3.product-outline-category). Selectores pueden haber cambiado.")
        with open(f"debug_outline_{course['slug']}.html", "w", encoding="utf-8") as f:
            f.write(driver.page_source)
        log(f"  HTML guardado en debug_outline_{course['slug']}.html para inspeccion.")
        return {"title": course["title"], "url": course["url"], "modules": {}}

    modules = {}
    seen_pids = set()   # dedupe por curso: una leccion solo cuenta en su modulo real
    mod_order = 0
    for header in headers:
        try:
            try:
                mtitle = header.find_element(By.CSS_SELECTOR, "div.media-body a").text.strip()
            except NoSuchElementException:
                mtitle = header.text.strip().split("\n")[0]
            cat_id = extract_category_id(header.get_attribute("data-target"), None)
            # Saltar cabecera fantasma: sin contenedor de categoria resoluble
            # (su data-target es "#"/"#sidebar-modal"), que de usar fallback recogeria
            # TODAS las lecciones del curso y duplicaria los totales.
            if not cat_id:
                continue
            links = driver.find_elements(By.CSS_SELECTOR, f"div#{cat_id} a.product-outline-post")
            if not links:
                continue
            lessons = {}
            order = 0
            for link in links:
                href = link.get_attribute("href")
                try:
                    ltitle = link.find_element(By.CSS_SELECTOR, "div.media-body").text.strip()
                except NoSuchElementException:
                    ltitle = link.text.strip()
                if not href or not ltitle:
                    continue
                pid = extract_post_id(href)
                key = pid or href
                if key in seen_pids:
                    continue
                seen_pids.add(key)
                order += 1
                lessons[pid or f"_pos{order}"] = {"title": ltitle, "order": order, "url": href, "post_id": pid}
            if not lessons:
                continue
            mod_order += 1
            modules[cat_id] = {"title": mtitle, "order": mod_order, "lessons": lessons}
            log(f"  Modulo {mod_order:02d}: {mtitle}  ({len(lessons)} lecciones)")
        except Exception as e:
            log(f"  ERROR modulo: {e}")
    return {"title": course["title"], "url": course["url"], "modules": modules}


def load_known_from_csv():
    """Devuelve {curso_norm: set(titulo_leccion_norm)} desde download_log.csv (baseline aproximado)."""
    known = {}
    if not os.path.exists(LOG_FILE):
        return known
    with open(LOG_FILE, "r", encoding="utf-8") as f:
        for row in csv.DictReader(f):
            c = norm(row.get("Course", ""))
            known.setdefault(c, set()).add(norm(row.get("Lesson", "")))
    return known


def write_report(manifest, known):
    lines = ["# Informe dry-run de sincronizacion", "",
             f"Escaneado: {manifest['scanned_at']}", ""]
    total_lessons = 0
    total_new = 0
    no_pid_courses = []

    for slug, c in manifest["courses"].items():
        known_titles = known.get(norm(c["title"]), set())
        course_new = []
        course_total = 0
        pid_ok = 0
        pid_total = 0
        for mod in c["modules"].values():
            for pid, les in mod["lessons"].items():
                course_total += 1
                pid_total += 1
                if les.get("post_id"):
                    pid_ok += 1
                if known_titles and norm(les["title"]) not in known_titles:
                    course_new.append(f"{mod['title']} / {les['title']}")
        total_lessons += course_total
        total_new += len(course_new)
        if pid_total and pid_ok == 0:
            no_pid_courses.append(slug)

        lines.append(f"## {c['title']}  ({slug})")
        lines.append(f"- Modulos: {len(c['modules'])} | Lecciones: {course_total} | "
                     f"post_id extraido: {pid_ok}/{pid_total}")
        if not known_titles:
            lines.append("- (sin baseline en CSV para este curso; no se puede marcar 'nuevo')")
        elif course_new:
            lines.append(f"- PROBABLEMENTE NUEVAS ({len(course_new)}):")
            lines += [f"    - {x}" for x in course_new]
        else:
            lines.append("- Sin lecciones nuevas respecto al CSV.")
        lines.append("")

    summary = ["## Resumen", "",
               f"- Cursos escaneados: {len(manifest['courses'])}",
               f"- Lecciones totales: {total_lessons}",
               f"- Probablemente nuevas (vs CSV): {total_new}"]
    if no_pid_courses:
        summary.append(f"- AVISO: sin post_id en: {', '.join(no_pid_courses)} "
                       f"(revisar extract_post_id / formato de URL)")
    summary.append("")
    lines = lines[:3] + summary + lines[3:]

    with open(REPORT_OUT, "w", encoding="utf-8") as f:
        f.write("\n".join(lines))
    log(f"\nInforme escrito en {REPORT_OUT}")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--course", action="append", default=[], help="substring de slug/titulo (repetible)")
    ap.add_argument("--courses-only", action="store_true")
    ap.add_argument("--limit", type=int, default=0)
    ap.add_argument("--headless", action="store_true")
    args = ap.parse_args()

    if not (EMAIL and PASSWORD and KAJABI_URL):
        log("ERROR: faltan KAJABI_EMAIL / KAJABI_PASSWORD / KAJABI_URL en .env")
        return 1

    driver = build_driver(args.headless)
    try:
        if not login(driver):
            log("ERROR: login fallido.")
            return 1

        courses = get_courses(driver)
        log(f"\nCursos encontrados en la biblioteca: {len(courses)}")
        for c in courses:
            log(f"  - {c['title']}  ({c['slug']})")

        if args.course:
            filt = [t.strip().lower() for t in ",".join(args.course).split(",") if t.strip()]
            courses = [c for c in courses if any(t in c["slug"].lower() or t in c["title"].lower() for t in filt)]
            log(f"\nFiltrados a {len(courses)} curso(s) por {filt}")
        if args.limit:
            courses = courses[:args.limit]

        manifest = {"scanned_at": datetime.now(timezone.utc).isoformat(), "courses": {}}
        if not args.courses_only:
            for c in courses:
                manifest["courses"][c["slug"]] = scan_course(driver, c)

        with open(MANIFEST_OUT, "w", encoding="utf-8") as f:
            json.dump(manifest, f, ensure_ascii=False, indent=2)
        log(f"\nManifiesto escrito en {MANIFEST_OUT}")

        if not args.courses_only:
            write_report(manifest, load_known_from_csv())
    finally:
        driver.quit()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
