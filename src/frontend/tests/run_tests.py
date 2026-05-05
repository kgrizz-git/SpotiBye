"""Thin wrapper around pytest for frontend integration tests.

All test classes are now standard pytest classes collected automatically.
Use this script for quick local runs; the pre-push hook calls pytest directly.
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

_TESTS_DIR = Path(__file__).parent


def main() -> int:
    args = [sys.executable, "-m", "pytest", str(_TESTS_DIR), "-v"]

    if len(sys.argv) > 1:
        test_type = sys.argv[1].lower()
        test_map = {
            "auth": "test_auth.py",
            "ui": "test_ui.py",
            "performance": "test_performance.py",
            "cache": "test_cache.py",
            "ui-responsiveness": "test_ui_responsiveness.py",
            "config": "test_configuration.py",
        }
        if test_type not in test_map:
            print(f"Unknown test type: {test_type}")
            print(f"Available: {', '.join(test_map)}")
            return 1
        args = [
            sys.executable,
            "-m",
            "pytest",
            str(_TESTS_DIR / test_map[test_type]),
            "-v",
        ]

    return subprocess.run(args).returncode


if __name__ == "__main__":
    sys.exit(main())
