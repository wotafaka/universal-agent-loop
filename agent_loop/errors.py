"""Stable refusal codes and the runtime error type."""
from __future__ import annotations


class UALError(Exception):
    """One fail-closed runtime refusal with a stable machine code."""

    def __init__(self, code: str, detail: str = ""):
        self.code = code
        self.detail = detail
        super().__init__(f"{code}:{detail}" if detail else code)

    def refusal(self) -> str:
        return f"{self.code}:{self.detail}" if self.detail else self.code
