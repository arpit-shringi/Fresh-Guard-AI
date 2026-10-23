# tests/test_app_and_platform.py — dashboard + Windows/launcher regression tests
# Covers the failures seen on Windows / Python 3.12 / Git Bash:
#   * `python streamlit_app.py` (VS Code Run button) must start the real app
#   * console output must not crash on a cp1252 terminal
#   * image paths with non-ASCII characters must be readable
import os
import shutil
import subprocess
import sys
import time
import urllib.request

import pytest

import config
from tests.test_pipeline import FakeDetector, FakeRipeness, FakeVGG
from main_engine import ShelfInventoryPipeline

ROOT = config.PROJECT_ROOT
PIC = ROOT / "sample_data" / "pic.png"


# dashboard (AppTest)
@pytest.fixture
def app(tmp_path, monkeypatch):
    import streamlit as st
    from streamlit.testing.v1 import AppTest
    st.cache_resource.clear()          # never reuse an engine built by another test
    monkeypatch.setattr(config, "UPLOAD_DIR", tmp_path / "uploads")
    monkeypatch.setattr(config, "OUTPUT_DIR", tmp_path / "outputs")
    return AppTest.from_file(str(ROOT / "streamlit_app.py"), default_timeout=60)


def _html(at):
    return "\n".join(m.value for m in at.markdown)


def test_dashboard_full_flow_sample_mode(app, monkeypatch):
    monkeypatch.setattr(config, "USE_SAMPLE_INVENTORY", True)
    at = app.run()
    assert not at.exception
    assert "Scan a produce bin" in _html(at)
    assert not at.toggle and not at.selectbox                 # no settings panel any more

    at.file_uploader[0].upload("pic.png", PIC.read_bytes(), "image/png").run()
    at.button[0].click().run()

    assert not at.exception and not at.error
    assert [t.label for t in at.tabs] == ["Inventory", "Store actions", "Promotions", "Bundles", "Raw output"]
    page = _html(at)
    assert '<span class="fg-prod">Apple</span>' in page and "Mark down now" in page and "Healthy" in page
    assert "<b>43</b><span>items counted</span>" in page and "<b>3</b><span>rotten units to remove</span>" in page
    assert page.count('class="fg-action"') == 2
    assert page.count('<article class="fg-tag') == 2           # 2 promotions as shelf tags
    assert page.count('class="fg-bundle"') == 1                # 1 bundle

    approve = next(b for b in at.button if "Approve" in b.label)
    approve.click().run()
    assert at.success and (config.OUTPUT_DIR / "approved_promotions.json").exists()


def test_dashboard_shows_error_instead_of_crashing(app, monkeypatch):
    """Vision mode with no weights must show st.error, not a traceback."""
    monkeypatch.setattr(config, "PRODUCE_WEIGHTS", ROOT / "does_not_exist.h5")
    import slm_engine
    def boom(self):
        raise FileNotFoundError("Missing produce classifier model: vgg.h5")
    monkeypatch.setattr(slm_engine.SLMEngine, "pipeline", property(boom))
    at = app.run()
    at.file_uploader[0].upload("pic.png", PIC.read_bytes(), "image/png").run()
    at.button[0].click().run()
    assert not at.exception
    assert "Analysis failed" in at.error[0].value


#  launcher
def test_plain_python_launch_starts_streamlit_server():
    """`python streamlit_app.py` used to exit; it must now hand off to `streamlit run`."""
    port = "8599"
    env = {**os.environ, "STREAMLIT_SERVER_HEADLESS": "true", "STREAMLIT_SERVER_PORT": port,
           "STREAMLIT_BROWSER_GATHER_USAGE_STATS": "false"}
    # Launch from a DIFFERENT folder to prove the absolute-path handoff works.
    proc = subprocess.Popen([sys.executable, str(ROOT / "streamlit_app.py")], cwd=str(ROOT.parent),
                            env=env, stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
    try:
        deadline, ok = time.time() + 45, False
        while time.time() < deadline and proc.poll() is None:
            try:
                with urllib.request.urlopen(f"http://127.0.0.1:{port}/_stcore/health", timeout=2) as r:
                    ok = r.status == 200
                    break
            except OSError:
                time.sleep(0.5)
        assert ok, f"server did not start (exit={proc.poll()})"
    finally:
        proc.kill()
        proc.wait(timeout=10)


# - Windows console / paths
@pytest.mark.parametrize("script,args", [("run_pipeline.py", ["--sample"]), ("init_db.py", [])])
def test_cli_survives_cp1252_console(script, args, tmp_path):
    env = {**os.environ, "PYTHONIOENCODING": "cp1252", "FRESHGUARD_DB_PATH": str(tmp_path / "t.db"),
           "GROQ_API_KEY": ""}
    res = subprocess.run([sys.executable, str(ROOT / script), *args], cwd=str(ROOT), env=env,
                         capture_output=True, timeout=60)
    assert res.returncode == 0, res.stderr.decode(errors="replace")[-500:]


def test_non_ascii_image_path(tmp_path):
    folder = tmp_path / "Bilder_München_फल"
    folder.mkdir()
    img = folder / "शेल्फ.png"
    shutil.copy(PIC, img)
    pipe = ShelfInventoryPipeline(batch_size=4, detector_model=FakeDetector(),
                                  produce_model=FakeVGG(), ripeness_model=FakeRipeness())
    assert pipe.process_shelf_image(str(img))["Apple"]["Product_Count"] == 6


#  bare mode (no script context)
def test_bare_mode_does_not_crash_without_upload():
    """Regression: `AttributeError: 'NoneType' object has no attribute 'getvalue'`.
    Without `streamlit run`, st.stop() is a no-op, so the old script fell through to
    save_upload(None). Executing the body without a context must now finish cleanly."""
    import runpy
    import warnings
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        runpy.run_path(str(ROOT / "streamlit_app.py"), run_name="bare_mode_check")


#  pic.png -> vision -> Groq -> UI
def test_dashboard_pic_png_vision_mode_with_groq_shows_promos_and_bundles(app, monkeypatch):
    """Full UI path with pic.png: vision pipeline (fake models) -> decision engine ->
    Groq copy (fake client) -> promo and bundle cards rendered in the frontend."""
    import slm_engine
    from tests.conftest import FakeGroqClient
    from tests.test_pipeline import GROQ_REPLY
    fake_vision = ShelfInventoryPipeline(batch_size=4, detector_model=FakeDetector(),
                                         produce_model=FakeVGG(), ripeness_model=FakeRipeness())
    monkeypatch.setattr(slm_engine.SLMEngine, "pipeline", property(lambda self: fake_vision))
    monkeypatch.setattr(config, "GROQ_API_KEY", "test-key")
    client = FakeGroqClient(GROQ_REPLY)
    monkeypatch.setattr(slm_engine.GroqBackend, "_get_client", lambda self: client)

    at = app.run()
    at.file_uploader[0].upload("pic.png", PIC.read_bytes(), "image/png").run()
    at.button[0].click().run()

    assert not at.exception and not at.error and not at.warning
    page = _html(at)
    assert "Copy written by Groq SLM" in page
    assert '<article class="fg-tag' in page and 'class="fg-bundle"' in page, "no promotions or bundles rendered"
    assert "Crisp apples are 50% off" in page                             # Groq text reached the UI
    assert "Pull the 3 rotten apples" in page
    assert len(client.calls) == 1 and client.calls[0]["model"] == "qwen/qwen3.8-27b"
