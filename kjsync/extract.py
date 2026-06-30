"""Parsers PUROS (sin red, sin Selenium) para identidad y contenido de Kajabi."""
import re

from bs4 import BeautifulSoup


def norm(s):
    """Normaliza un titulo para comparaciones tolerantes."""
    s = re.sub(r"^\s*\d+\s*[-.]\s*", "", s or "")
    s = "".join(c if c.isalnum() or c.isspace() else " " for c in s)
    return re.sub(r"\s+", " ", s).strip().lower()


def extract_post_id(href):
    """Extrae el ID de post estable de una URL de leccion de Kajabi."""
    if not href:
        return None
    m = re.search(r"/posts/([A-Za-z0-9]+)", href)
    if m:
        return m.group(1)
    m = re.search(r"post[_-]?id=([A-Za-z0-9]+)", href)
    if m:
        return m.group(1)
    tail = [seg for seg in href.split("?")[0].split("/") if seg]
    return tail[-1] if tail else None


def extract_slug(url):
    """Extrae el slug de producto (curso) de una URL de Kajabi."""
    if not url:
        return None
    m = re.search(r"/products/([^/?#]+)", url)
    return m.group(1) if m else None


def extract_category_id(data_target):
    """Devuelve el id de categoria (modulo) o None si es una cabecera fantasma."""
    if not data_target:
        return None
    cid = data_target.lstrip("#").strip()
    if not cid or cid == "sidebar-modal":
        return None
    return cid


def parse_course_outline(page_source):
    """Parsea el indice de un curso (modulos + lecciones) de forma pura."""
    soup = BeautifulSoup(page_source, "html.parser")
    modules = []
    seen_pids = set()
    order = 0
    for header in soup.select("h3.product-outline-category"):
        cat_id = extract_category_id(header.get("data-target"))
        if not cat_id:
            continue
        container = soup.find(id=cat_id)
        if container is None:
            continue
        link_nodes = container.select("a.product-outline-post")
        if not link_nodes:
            continue
        title_node = header.select_one("div.media-body a") or header.select_one("div.media-body")
        mtitle = title_node.get_text(strip=True) if title_node else header.get_text(strip=True).split("\n")[0]
        lessons = []
        for link in link_nodes:
            href = link.get("href")
            body = link.select_one("div.media-body")
            ltitle = (body.get_text(strip=True) if body else link.get_text(strip=True))
            if not href or not ltitle:
                continue
            pid = extract_post_id(href)
            key = pid or href
            if key in seen_pids:
                continue
            seen_pids.add(key)
            lessons.append({"post_id": pid, "title": ltitle, "order": len(lessons) + 1, "url": href})
        if not lessons:
            continue
        order += 1
        modules.append({"category_id": cat_id, "title": mtitle, "order": order, "lessons": lessons})
    return modules


_WISTIA_PATTERNS = (
    r"wistia_async_([a-z0-9]+)",
    r"wistia\.com/medias/([a-z0-9]+)",
    r"embed/medias/([a-z0-9]+)\.",
)


def extract_wistia_id(page_source):
    for pat in _WISTIA_PATTERNS:
        m = re.search(pat, page_source or "")
        if m:
            return m.group(1)
    return None


def parse_materials(page_source):
    soup = BeautifulSoup(page_source or "", "html.parser")
    items = []
    for section in soup.select("section.sage-sortable__item--card"):
        title_node = section.select_one("h1.sage-sortable__item-title")
        link = section.select_one("a.sage-btn--icon-only-download")
        if not title_node or not link or not link.get("href"):
            continue
        items.append({"name": title_node.get_text(strip=True), "url": link.get("href")})
    items.sort(key=lambda x: x["name"])
    return items


def has_description(page_source):
    soup = BeautifulSoup(page_source or "", "html.parser")
    node = soup.select_one("div.kjb-rte")
    return bool(node and node.get_text(strip=True))


def lesson_fingerprint(page_source):
    return {
        "wistia_id": extract_wistia_id(page_source),
        "materials": [m["name"] for m in parse_materials(page_source)],
        "has_description": has_description(page_source),
    }
