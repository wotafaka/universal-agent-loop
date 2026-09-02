"""lineclean: remove repeated entries from a text list without sorting or trimming.

Usage: python lineclean.py [input_file]

Reads strict UTF-8 from input_file, or stdin when the argument is omitted.
Writes the cleaned text as UTF-8 bytes with LF line endings to stdout.
Duplicate complete lines are removed, keeping each distinct line's first
occurrence and original order. Comparison is case-sensitive; whitespace is
not trimmed and blank lines count as distinct entries. Exits 0 on success
and 2 on missing/unreadable input or invalid UTF-8.
"""

import sys


def unique_lines(text: str) -> str:
    seen = set()
    kept = []
    for line in text.splitlines():
        if line not in seen:
            seen.add(line)
            kept.append(line)
    if not kept:
        return ""
    return "\n".join(kept) + "\n"


def main(argv=None) -> int:
    args = sys.argv[1:] if argv is None else list(argv)
    if len(args) > 1:
        sys.stderr.write("lineclean: usage: python lineclean.py [input_file]\n")
        return 2
    try:
        if args:
            with open(args[0], "rb") as handle:
                data = handle.read()
        else:
            data = sys.stdin.buffer.read()
        text = data.decode("utf-8", errors="strict")
    except OSError as exc:
        sys.stderr.write(f"lineclean: cannot read input: {exc.strerror or exc}\n")
        return 2
    except UnicodeDecodeError:
        sys.stderr.write("lineclean: input is not valid UTF-8\n")
        return 2
    sys.stdout.buffer.write(unique_lines(text).encode("utf-8"))
    sys.stdout.buffer.flush()
    return 0


if __name__ == "__main__":
    sys.exit(main())
