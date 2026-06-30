"""Escaneo de la biblioteca Kajabi a un manifiesto, reutilizando parsers puros."""
import time
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC

from kjsync import model, extract


def get_courses(driver, base_url):
    base_url = base_url.rstrip("/")
    driver.get(f"{base_url}/library")
    time.sleep(5)
    courses = []
    for card in driver.find_elements(By.CSS_SELECTOR, "div.product"):
        try:
            title = card.find_element(By.CSS_SELECTOR, "h4.product__title").text.strip()
        except Exception:
            title = card.text.strip().split("\n")[0]
        try:
            url = card.find_element(By.CSS_SELECTOR, "a[href*='/products/']").get_attribute("href")
        except Exception:
            continue
        if "/communities/" in url:
            continue
        slug = extract.extract_slug(url)
        if not slug:
            continue
        courses.append({"slug": slug, "title": title, "url": url})
    return courses


def scan_library(driver, base_url, scanned_at, course_filter=None, deep=False, progress=print):
    manifest = model.new_manifest(scanned_at)
    courses = get_courses(driver, base_url)
    progress(f"Biblioteca: {len(courses)} cursos")
    if course_filter:
        terms = [t.strip().lower() for t in course_filter if t.strip()]
        courses = [c for c in courses if any(t in c["slug"].lower() or t in c["title"].lower() for t in terms)]
        progress(f"Filtrados a {len(courses)} curso(s)")

    for c in courses:
        progress(f"Escaneando: {c['title']} ({c['slug']})")
        driver.get(c["url"])
        WebDriverWait(driver, 30).until(EC.presence_of_element_located((By.TAG_NAME, "body")))
        time.sleep(4)
        course_obj = model.add_course(manifest, c["slug"], c["title"], c["url"])
        modules = extract.parse_course_outline(driver.page_source)
        if not modules:
            progress(f"  AVISO: sin modulos en {c['slug']} (selectores?)")
            continue
        for mod in modules:
            module_obj = model.set_module(course_obj, mod["category_id"], mod["title"], mod["order"])
            for les in mod["lessons"]:
                url = les["url"]
                if url and url.startswith("/"):
                    url = base_url.rstrip("/") + url
                fp = None
                if deep and url:
                    try:
                        driver.get(url)
                        WebDriverWait(driver, 30).until(
                            EC.presence_of_element_located((By.TAG_NAME, "body")))
                        time.sleep(2)
                        fp = extract.lesson_fingerprint(driver.page_source)
                    except Exception as e:
                        progress(f"    AVISO: huella fallida en {les['title']}: {e}")
                model.set_lesson(module_obj, les["post_id"], les["title"],
                                 les["order"], url, fp)
    return manifest
