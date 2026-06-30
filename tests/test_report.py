from kjsync import report


def sample_diff():
    return {
        "courses": {
            "curso": {"title": "Curso", "unchanged": 5,
                      "new": [{"module_title": "B1", "title": "Escalas", "post_id": "2", "url": "/posts/2"}],
                      "changed": [], "renamed": [], "removed": []},
        },
        "totals": {"new": 1, "changed": 0, "renamed": 0, "removed": 0, "lessons": 6},
    }


def test_report_has_summary_and_sections():
    md = report.render_report(sample_diff(), "2026-06-30T00:00:00Z", deep=False)
    assert "# Informe de sincronizacion" in md
    assert "Nuevas: 1" in md
    assert "## Curso" in md
    assert "Escalas" in md
    assert "estructural" in md.lower()


def test_report_deep_flag():
    md = report.render_report(sample_diff(), "t", deep=True)
    assert "profundo" in md.lower()
