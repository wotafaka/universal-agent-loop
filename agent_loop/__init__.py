"""Universal Agent Loop — provider-neutral runtime (work in progress).

This package is the owner-authorized full-runtime implementation task
UAL-RUNTIME-1. The public CLI entry point is ``python -m agent_loop``.
Every capability here operates on an explicit arbitrary project root,
never on this package's own source tree. All guarantees are
LOCAL_INTEGRITY, not an OS sandbox.
"""

__version__ = "0.1.0"
PACKAGE_SCHEMA = "universal-agent-loop/1"
