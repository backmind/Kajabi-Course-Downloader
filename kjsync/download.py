"""Descarga de los assets de una leccion a un directorio (reusa parsers puros)."""
import os
import re
import time
import requests
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC

from kjsync import extract

_HEADERS = {"User-Agent": "Mozilla/5.0"}


def _safe(name, maxlen=200):
    return "".join(c if c.isalnum() or c in " ._-" else "_" for c in name)[:maxlen].strip()


def wistia_mp4_url(wistia_id, referer):
    api = f"https://fast.wistia.net/embed/medias/{wistia_id}.json"
    resp = requests.get(api, headers={"Referer": referer, "User-Agent": "Mozilla/5.0"}, timeout=60)
    if resp.status_code != 200:
        return None
    assets = resp.json().get("media", {}).get("assets", [])
    mp4s = [a for a in assets if (a.get("type") == "original" or a.get("container") == "mp4")
            and a.get("type") != "still_image"]
    if not mp4s:
        return None
    mp4s.sort(key=lambda x: x.get("size", 0), reverse=True)
    url = mp4s[0].get("url", "")
    return url.replace(".bin", ".mp4") if url.endswith(".bin") else url


def download_file(url, dest_path, timeout=60, retries=3):
    for attempt in range(retries):
        try:
            with requests.get(url, stream=True, headers=_HEADERS, timeout=timeout) as r:
                r.raise_for_status()
                with open(dest_path, "wb") as f:
                    for chunk in r.iter_content(chunk_size=8192):
                        if chunk:
                            f.write(chunk)
            if os.path.getsize(dest_path) > 0:
                return True
        except Exception:
            time.sleep(3)
    return False


def download_lesson(driver, lesson, dest_dir, timeout=60):
    os.makedirs(dest_dir, exist_ok=True)
    base = _safe(f"{lesson['order']:02d} - {lesson['title']}")
    status = {"video": "Failed", "materials": "None", "description": "None"}

    driver.get(lesson["url"])
    WebDriverWait(driver, 30).until(EC.presence_of_element_located((By.TAG_NAME, "body")))
    time.sleep(2)
    page = driver.page_source

    # Descripcion
    if extract.has_description(page):
        try:
            from bs4 import BeautifulSoup
            text = BeautifulSoup(page, "html.parser").select_one("div.kjb-rte").get_text("\n", strip=True)
            with open(os.path.join(dest_dir, "description.txt"), "w", encoding="utf-8") as f:
                f.write(text)
            status["description"] = "Success"
        except Exception:
            status["description"] = "Failed"

    # Video (Wistia)
    wid = extract.extract_wistia_id(page)
    if wid:
        url = wistia_mp4_url(wid, lesson["url"])
        if url and download_file(url, os.path.join(dest_dir, f"{base}.mp4"), timeout=timeout):
            status["video"] = "Success"
    else:
        status["video"] = "None"

    # Materiales
    mats = extract.parse_materials(page)
    if mats:
        ok = True
        for m in mats:
            ext = os.path.splitext(m["url"].split("?")[0])[1] or ".bin"
            path = os.path.join(dest_dir, _safe(m["name"]) + ext)
            if not download_file(m["url"], path, timeout=timeout):
                ok = False
        status["materials"] = "Success" if ok else "Failed"

    return status
