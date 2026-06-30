"""Render del resultado del diff a markdown."""


def _section(lines, label, refs):
    if not refs:
        return
    lines.append(f"- {label} ({len(refs)}):")
    for r in refs:
        extra = f"  (antes: {r['old_title']})" if r.get("old_title") else ""
        lines.append(f"    - {r.get('module_title', '')} / {r['title']}{extra}")


def render_report(diff_result, scanned_at, deep):
    t = diff_result["totals"]
    mode = "profundo (huellas de contenido)" if deep else "estructural (solo altas/bajas/renombrados)"
    lines = [
        "# Informe de sincronizacion",
        "",
        f"Escaneado: {scanned_at}",
        f"Modo: {mode}",
        "",
        "## Resumen",
        "",
        f"- Lecciones en el sitio: {t['lessons']}",
        f"- Nuevas: {t['new']}",
        f"- Cambiadas: {t['changed']}",
        f"- Renombradas: {t['renamed']}",
        f"- Borradas (solo informe): {t['removed']}",
        "",
    ]
    for slug, b in diff_result["courses"].items():
        if not (b["new"] or b["changed"] or b["renamed"] or b["removed"]):
            continue
        lines.append(f"## {b['title']}  ({slug})")
        _section(lines, "NUEVAS", b["new"])
        _section(lines, "CAMBIADAS", b["changed"])
        _section(lines, "RENOMBRADAS", b["renamed"])
        _section(lines, "BORRADAS", b["removed"])
        lines.append("")
    return "\n".join(lines)
