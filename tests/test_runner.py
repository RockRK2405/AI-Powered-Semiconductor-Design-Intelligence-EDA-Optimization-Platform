import os
import sys
import time

import pytest

from siliconai.eda.runner import build_env, gnu_time_available, parse_time_stats, run_tool

PY = sys.executable


def test_success_and_log_capture(tmp_path):
    res = run_tool(
        [PY, "-c", "print('hello')"], cwd=tmp_path, log_path=tmp_path / "a.log", timeout_s=30
    )
    assert res.ok and res.exit_code == 0 and not res.timed_out
    assert "hello" in (tmp_path / "a.log").read_text()
    assert res.wall_s > 0


def test_nonzero_exit(tmp_path):
    res = run_tool(
        [PY, "-c", "import sys; sys.exit(3)"],
        cwd=tmp_path,
        log_path=tmp_path / "b.log",
        timeout_s=30,
    )
    assert res.exit_code == 3 and not res.ok


def test_timeout_kills_whole_process_group(tmp_path):
    marker = tmp_path / "child_alive"
    # Parent spawns a grandchild that would write a marker after 3 s; both must die.
    code = (
        "import subprocess, sys, time;"
        f"subprocess.Popen([sys.executable, '-c', "
        f'\'import time; time.sleep(3); open(r"{marker}", "w").write("x")\']);'
        "time.sleep(60)"
    )
    start = time.monotonic()
    res = run_tool(
        [PY, "-c", code], cwd=tmp_path, log_path=tmp_path / "c.log", timeout_s=1, measure=False
    )
    assert res.timed_out
    assert time.monotonic() - start < 15
    time.sleep(4)
    assert not marker.exists(), "grandchild survived the timeout"


def test_missing_executable(tmp_path):
    res = run_tool(
        ["definitely-not-a-real-tool-xyz"],
        cwd=tmp_path,
        log_path=tmp_path / "d.log",
        timeout_s=5,
        measure=False,
    )
    assert res.exit_code is None and not res.ok


def test_rejects_shell_string(tmp_path):
    with pytest.raises(TypeError):
        run_tool("echo hi; rm -rf /", cwd=tmp_path, log_path=tmp_path / "e.log", timeout_s=5)


def test_rejects_nul_and_empty(tmp_path):
    with pytest.raises(ValueError):
        run_tool([], cwd=tmp_path, log_path=tmp_path / "f.log", timeout_s=5)
    with pytest.raises(ValueError):
        run_tool(["echo", "a\0b"], cwd=tmp_path, log_path=tmp_path / "f.log", timeout_s=5)


def test_env_is_allowlisted(tmp_path, monkeypatch):
    monkeypatch.setenv("SUPER_SECRET_API_KEY", "leak-me")
    res = run_tool(
        [PY, "-c", "import os; print(os.environ.get('SUPER_SECRET_API_KEY'))"],
        cwd=tmp_path,
        log_path=tmp_path / "g.log",
        timeout_s=30,
        env={"EXTRA": "1"},
    )
    assert res.ok
    assert "leak-me" not in (tmp_path / "g.log").read_text()


def test_build_env_rejects_bad_keys():
    with pytest.raises(ValueError):
        build_env({"A=B": "x"})


@pytest.mark.skipif(not gnu_time_available(), reason="GNU time not installed")
def test_peak_memory_is_measured(tmp_path):
    # allocate ~80 MB and touch it so it is resident
    code = "b = bytearray(80 * 1024 * 1024); b[::4096] = b'x' * len(b[::4096]); print(len(b))"
    res = run_tool([PY, "-c", code], cwd=tmp_path, log_path=tmp_path / "h.log", timeout_s=60)
    assert res.ok
    assert res.peak_rss_kb is not None and res.peak_rss_kb > 70 * 1024
    assert res.user_s is not None


@pytest.mark.skipif(os.name != "posix", reason="rlimit is POSIX-only")
def test_address_space_limit_causes_failure(tmp_path):
    code = "b = bytearray(2 * 1024 * 1024 * 1024)"
    res = run_tool(
        [PY, "-c", code],
        cwd=tmp_path,
        log_path=tmp_path / "i.log",
        timeout_s=60,
        measure=False,
        address_space_limit_mb=512,
    )
    assert res.exit_code != 0
    assert "MemoryError" in (tmp_path / "i.log").read_text()


def test_parse_time_stats():
    text = "Command exited with non-zero status 1\nSILICONAI_TIME 1.50 1.20 0.10 2048\n"
    assert parse_time_stats(text) == (1.5, 1.2, 0.1, 2048)
    assert parse_time_stats("garbage") is None
    assert parse_time_stats("SILICONAI_TIME x y z w") is None
