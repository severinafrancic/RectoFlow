"""Windows cross-process locks and byte-preserving atomic persistence."""
import ctypes
from ctypes import wintypes as W
from contextlib import contextmanager
from contextlib import ExitStack
import hashlib
import json
import os
from pathlib import Path
import tempfile
import time


class LockBusy(RuntimeError):
    pass


def canonical(path):
    return os.path.normcase(str(Path(path).resolve()))


def config_lock(path):
    path = Path(path).resolve()
    if path.parent.parent.name == "profiles":
        root = path.parent.parent.parent
        return root / ".locks" / ("config-" + hashlib.sha256(canonical(path).encode()).hexdigest() + ".lock")
    return path.with_name(path.name + ".lock")


@contextmanager
def config_transaction(path):
    path=Path(path).resolve()
    with ExitStack() as stack:
        if path.parent.parent.name=="profiles":
            lockroot=path.parent.parent.parent/".locks"
            stack.enter_context(exclusive(lockroot/"profiles.lock"))
            stack.enter_context(exclusive(lockroot/("profile-"+path.parent.name+".lock")))
        stack.enter_context(exclusive(config_lock(path)))
        yield


@contextmanager
def exclusive(path, timeout=2.0):
    """Sharing=0; crash releases the HANDLE, never delete a lock pathname."""
    if os.name != "nt":
        raise RuntimeError("RectoFlow locks require native Windows.")
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    kernel = ctypes.WinDLL("kernel32", use_last_error=True)
    kernel.CreateFileW.argtypes = [W.LPCWSTR, W.DWORD, W.DWORD, ctypes.c_void_p, W.DWORD, W.DWORD, W.HANDLE]
    kernel.CreateFileW.restype = W.HANDLE
    kernel.CloseHandle.argtypes = [W.HANDLE]
    deadline = time.monotonic() + timeout
    while True:
        handle = kernel.CreateFileW(str(path.resolve()), 0xC0000000, 0, None, 4, 0x80, None)
        if handle != ctypes.c_void_p(-1).value:
            break
        code = ctypes.get_last_error()
        if code not in (32, 33):
            raise ctypes.WinError(code)
        if time.monotonic() >= deadline:
            raise LockBusy("Datei wird bereits von einem anderen RectoFlow-Prozess verwendet.")
        time.sleep(min(.05, max(0, deadline-time.monotonic())))
    try:
        yield
    finally:
        kernel.CloseHandle(handle)


def atomic_bytes(path, data):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = None
    try:
        with tempfile.NamedTemporaryFile(dir=path.parent, prefix=path.name+".", suffix=".tmp", delete=False) as stream:
            tmp = Path(stream.name)
            stream.write(data)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(tmp, path)
    finally:
        if tmp is not None:
            tmp.unlink(missing_ok=True)


def atomic_json(path, value):
    atomic_bytes(path, json.dumps(value, ensure_ascii=False, indent=2, allow_nan=False).encode("utf-8"))
