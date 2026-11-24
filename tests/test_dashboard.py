"""Dashboard smoke test with Streamlit's headless AppTest (skips if streamlit is missing)."""

from __future__ import annotations

from pathlib import Path

import pytest

st_testing = pytest.importorskip("streamlit.testing.v1")

DATA = Path(__file__).resolve().parents[1] / "data" / "d1" / "registry"


@pytest.mark.skipif(not (DATA / "runs.jsonl").exists(), reason="no committed registry snapshot")
def test_dashboard_renders_from_committed_snapshot(monkeypatch):
    monkeypatch.setenv("SILICONAI_DASHBOARD_DATA", str(DATA))
    app = st_testing.AppTest.from_file(
        str(Path(__file__).resolve().parents[1] / "dashboard" / "app.py"), default_timeout=300
    )
    app.run()
    assert not app.exception, app.exception
    assert app.metric[0].label == "Runs" and int(app.metric[0].value) > 0
