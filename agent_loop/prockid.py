"""OS-native process start identity (birth identity) probes.

A PID alone is reusable and never proves identity. Windows uses
``GetProcessTimes`` creation time through ctypes; Linux uses procfs
``starttime`` plus the boot time; macOS uses the process start time from
``ps`` under a fixed locale. Any other platform, or an
unobtainable probe, returns ``None`` and the caller must fail closed
instead of guessing.
"""
from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path


def process_start_identity(pid: int) -> dict | None:
    if not isinstance(pid, int) or isinstance(pid, bool) or pid <= 0:
        return None
    if os.name == "nt":
        return _windows_identity(pid)
    if sys.platform == "darwin":
        return _darwin_identity(pid)
    if Path("/proc/self/stat").exists():
        return _procfs_identity(pid)
    return None


def process_alive(pid: int) -> bool:
    if not isinstance(pid, int) or isinstance(pid, bool) or pid <= 0:
        return False
    if os.name == "nt":
        return _windows_alive(pid)
    if sys.platform == "darwin":
        return _posix_alive(pid)
    return Path(f"/proc/{pid}").exists()


def _darwin_identity(pid: int) -> dict | None:
    try:
        result = subprocess.run(
            ["/bin/ps", "-o", "lstart=", "-p", str(pid)],
            capture_output=True, text=True, timeout=2,
            env={"LC_ALL": "C", "PATH": "/usr/bin:/bin"})
    except (OSError, subprocess.SubprocessError):
        return None
    value = " ".join(result.stdout.split())
    if result.returncode != 0 or not value:
        return None
    return {"method": "darwin-ps-lstart", "value": value}


def _posix_alive(pid: int) -> bool:
    try:
        os.kill(pid, 0)
    except ProcessLookupError:
        return False
    except PermissionError:
        return True
    except OSError:
        return False
    return True


def _windows_identity(pid: int) -> dict | None:
    import ctypes
    import ctypes.wintypes as wt

    kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
    PROCESS_QUERY_LIMITED_INFORMATION = 0x1000
    STILL_ACTIVE = 259
    handle = kernel32.OpenProcess(
        PROCESS_QUERY_LIMITED_INFORMATION, False, pid)
    if not handle:
        return None

    class LARGE_INTEGER(ctypes.Structure):
        _fields_ = [("Value", ctypes.c_longlong)]

    class FILETIME(ctypes.Structure):
        _fields_ = [("dwLowDateTime", wt.DWORD),
                    ("dwHighDateTime", wt.DWORD)]

        def value(self):
            return (self.dwHighDateTime << 32) | self.dwLowDateTime

    creation = FILETIME()
    exit_time = FILETIME()
    kernel_time = FILETIME()
    user_time = FILETIME()
    try:
        if not kernel32.GetProcessTimes(
                handle, ctypes.byref(creation), ctypes.byref(exit_time),
                ctypes.byref(kernel_time), ctypes.byref(user_time)):
            return None
        exit_code = wt.DWORD()
        if not kernel32.GetExitCodeProcess(handle, ctypes.byref(exit_code)):
            return None
        if exit_code.value != STILL_ACTIVE:
            return None
        return {"method": "win-getprocesstimes-filetime",
                "value": str(creation.value())}
    finally:
        kernel32.CloseHandle(handle)


def _windows_alive(pid: int) -> bool:
    import ctypes
    import ctypes.wintypes as wt

    kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
    PROCESS_QUERY_LIMITED_INFORMATION = 0x1000
    STILL_ACTIVE = 259
    handle = kernel32.OpenProcess(
        PROCESS_QUERY_LIMITED_INFORMATION, False, pid)
    if not handle:
        return False
    try:
        exit_code = wt.DWORD()
        if not kernel32.GetExitCodeProcess(handle, ctypes.byref(exit_code)):
            return False
        return exit_code.value == STILL_ACTIVE
    finally:
        kernel32.CloseHandle(handle)


def _procfs_identity(pid: int) -> dict | None:
    try:
        stat = Path(f"/proc/{pid}/stat").read_text(encoding="utf-8")
    except OSError:
        return None
    tail = stat.rpartition(")")[2].split()
    if len(tail) < 20:
        return None
    starttime = tail[19]
    btime = None
    try:
        for line in Path("/proc/stat").read_text(encoding="utf-8").splitlines():
            if line.startswith("btime "):
                btime = line.split(None, 1)[1].strip()
                break
    except OSError:
        return None
    if not btime:
        return None
    return {"method": "linux-procfs-starttime",
            "value": f"{starttime}@{btime}"}
