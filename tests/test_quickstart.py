"""The offline quickstart must really pass: full CLI cycle, then cleanup.

This runs `examples/offline_quickstart.py` as a child process so the
packaged one-command path is itself a regression-tested artifact, not a
documented hope. Synthetic actors only; no provider or credential.
"""
from __future__ import annotations

import subprocess
import sys
import unittest
from pathlib import Path

import _harness as h


class OfflineQuickstartTests(unittest.TestCase):
    def test_quickstart_passes_and_cleans_up(self):
        proc = subprocess.run(
            [sys.executable, str(h.CHECKOUT / "examples"
                                 / "offline_quickstart.py")],
            capture_output=True, text=True, encoding="utf-8",
            errors="replace", timeout=300, cwd=str(h.CHECKOUT))
        self.assertEqual(proc.returncode, 0,
                         f"stdout:\n{proc.stdout}\nstderr:\n{proc.stderr}")
        self.assertIn("OFFLINE_QUICKSTART: PASS", proc.stdout)
        self.assertIn("SYNTHETIC", proc.stdout)
        scratch = h.CHECKOUT / "examples" / ".scratch"
        leftovers = [p.name for p in scratch.iterdir()
                     if p.name.startswith("quickstart-")] \
            if scratch.is_dir() else []
        self.assertEqual(leftovers, [])


if __name__ == "__main__":
    unittest.main()
