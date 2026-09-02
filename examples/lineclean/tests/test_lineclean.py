"""Focused tests for lineclean: function boundary + subprocess CLI boundary."""

import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

import lineclean

SCRIPT = PROJECT_ROOT / "lineclean.py"
PY = [sys.executable, "-I", "-S", "-B"]


def run_cli(args, stdin_bytes=None):
    return subprocess.run(
        PY + [str(SCRIPT)] + args,
        input=stdin_bytes,
        capture_output=True,
        timeout=60,
    )


class UniqueLinesFunctionTests(unittest.TestCase):
    def test_empty_input(self):
        self.assertEqual(lineclean.unique_lines(""), "")

    def test_first_occurrence_kept_in_original_order(self):
        self.assertEqual(lineclean.unique_lines("b\na\nb\na"), "b\na\n")

    def test_case_sensitive_comparison(self):
        self.assertEqual(
            lineclean.unique_lines("Apple\napple\nAPPLE\napple"), "Apple\napple\nAPPLE\n"
        )

    def test_whitespace_not_trimmed(self):
        self.assertEqual(
            lineclean.unique_lines("apple\n apple\napple \napple"), "apple\n apple\napple \n"
        )

    def test_duplicate_blank_lines_are_distinct_entries(self):
        # Blank lines are entries subject to dedup: the second blank is a
        # repeated entry of the same distinct line and is removed (R2).
        self.assertEqual(lineclean.unique_lines("a\n\n\nb"), "a\n\nb\n")

    def test_only_blank_lines(self):
        self.assertEqual(lineclean.unique_lines("\n\n"), "\n")

    def test_trailing_lf_does_not_add_phantom_entry(self):
        self.assertEqual(lineclean.unique_lines("a\n"), "a\n")

    def test_one_trailing_lf_only_when_lines_remain(self):
        self.assertEqual(lineclean.unique_lines("a"), "a\n")

    def test_crlf_normalized_to_lf(self):
        self.assertEqual(lineclean.unique_lines("pear\r\napple\r\npear"), "pear\napple\n")

    def test_lone_cr_normalized_to_lf(self):
        self.assertEqual(lineclean.unique_lines("a\rb\rc"), "a\nb\nc\n")

    def test_unicode_lines_preserved(self):
        self.assertEqual(
            lineclean.unique_lines("Яблоко\nяблоко\nЯблоко"), "Яблоко\nяблоко\n"
        )


class IdempotencePropertyTests(unittest.TestCase):
    CASES = [
        "",
        "a",
        "a\n",
        "a\nb\na\n",
        "a\r\nb\ra\n",
        "\n\n",
        "a\n\n\nb",
        " apple\napple\n",
        "Яблоко\nяблоко\n\nЯблоко",
        "a\u2028b\ra\rb",
        "mixed CASE\ncase\nmixed case\nMIXED CASE",
    ]

    def test_second_application_is_fixed_point(self):
        for case in self.CASES:
            with self.subTest(case=case):
                once = lineclean.unique_lines(case)
                self.assertEqual(lineclean.unique_lines(once), once)


class CliTests(unittest.TestCase):
    def test_file_argument_success(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "in.txt"
            path.write_bytes("pear\r\napple\npear\n".encode("utf-8"))
            proc = run_cli([str(path)])
        self.assertEqual(proc.returncode, 0, proc.stderr)
        self.assertEqual(proc.stdout, "pear\napple\n".encode("utf-8"))
        self.assertEqual(proc.stderr, b"")

    def test_stdin_when_argument_omitted(self):
        proc = run_cli([], stdin_bytes="a\nb\na\n".encode("utf-8"))
        self.assertEqual(proc.returncode, 0, proc.stderr)
        self.assertEqual(proc.stdout, "a\nb\n".encode("utf-8"))

    def test_missing_file_exit2_concise_stderr_no_stdout(self):
        proc = run_cli([str(PROJECT_ROOT / "no-such-file.txt")])
        self.assertEqual(proc.returncode, 2)
        self.assertNotIn(b"Traceback", proc.stderr)
        self.assertLessEqual(len(proc.stderr), 200)
        self.assertEqual(proc.stdout, b"")

    def test_invalid_utf8_exit2_no_partial_stdout(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "bad.txt"
            path.write_bytes(b"pear\n\xff\xfeapple\n")
            proc = run_cli([str(path)])
        self.assertEqual(proc.returncode, 2)
        self.assertNotIn(b"Traceback", proc.stderr)
        self.assertEqual(proc.stdout, b"")

    def test_cli_output_is_idempotent(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "in.txt"
            path.write_bytes("b\r\na\nb\nb\n".encode("utf-8"))
            first = run_cli([str(path)])
            second = run_cli([str(path)])
        self.assertEqual(first.returncode, 0, first.stderr)
        self.assertEqual(second.returncode, 0, second.stderr)
        self.assertEqual(second.stdout, first.stdout)


if __name__ == "__main__":
    unittest.main()
