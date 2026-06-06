"""Thin wrapper around pytest for frontend integration tests.

All test classes are now standard pytest classes collected automatically.
Use this script for quick local runs; the pre-push hook calls pytest directly.
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

_TESTS_DIR = Path(__file__).parent

_TEST_FILES: dict[str, str] = {
    "auth": "test_auth.py",
    "ui": "test_ui.py",
    "performance": "test_performance.py",
    "cache": "test_cache.py",
    "ui-responsiveness": "test_ui_responsiveness.py",
    "config": "test_configuration.py",
}


def _run_pytest(target: Path) -> int:
    # args are fully controlled: executable + hardcoded flags + resolved Path
    cmd = [sys.executable, "-m", "pytest", str(target), "-v"]
    # cmd contains only sys.executable, hardcoded flags, and a Path derived from _TEST_FILES values
    return subprocess.run(
        cmd
    ).returncode  # nosemgrep: dangerous-subprocess-use-tainted-env-args


def main() -> int:
    if len(sys.argv) < 2:
        return _run_pytest(_TESTS_DIR)

    test_type = sys.argv[1].lower()
    filename = _TEST_FILES.get(test_type)
    if filename is None:
        print(f"Unknown test type: {test_type!r}")
        print(f"Available: {', '.join(_TEST_FILES)}")
        return 1

    # filename comes from the controlled dict above, never from raw user input
    return _run_pytest(_TESTS_DIR / filename)


if __name__ == "__main__":
    sys.exit(main())
