import os
import subprocess
import sys
from pathlib import Path

PLATFORM = Path(__file__).resolve().parents[1]


def import_config(**env):
    clean = {k: v for k, v in os.environ.items() if k not in ("SECRET_KEY", "REFRESH_SECRET_KEY")}
    return subprocess.run(
        [sys.executable, "-c", "import app.services.auth"],
        cwd=PLATFORM,
        env={**clean, **env},
        capture_output=True,
        text=True,
    )


def test_refuses_to_start_without_signing_keys():
    result = import_config()
    assert result.returncode != 0
    assert "SECRET_KEY" in result.stderr


def test_starts_with_signing_keys():
    assert import_config(SECRET_KEY="a", REFRESH_SECRET_KEY="b").returncode == 0
