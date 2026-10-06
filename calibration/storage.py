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
    return os.path.normcase(final_path(path))


def windows_file(path):
    """Read file identity and final handle-resolved path; allow atomic replacement."""
    kernel=ctypes.WinDLL("kernel32",use_last_error=True)
    kernel.CreateFileW.argtypes=[W.LPCWSTR,W.DWORD,W.DWORD,ctypes.c_void_p,W.DWORD,W.DWORD,W.HANDLE]
    kernel.CreateFileW.restype=W.HANDLE
    kernel.CloseHandle.argtypes=[W.HANDLE]
    kernel.GetFinalPathNameByHandleW.argtypes=[W.HANDLE,W.LPWSTR,W.DWORD,W.DWORD]
    class Info(ctypes.Structure):
        _fields_=[("attributes",W.DWORD),("created",W.FILETIME),("accessed",W.FILETIME),("written",W.FILETIME),
                  ("volume",W.DWORD),("size_high",W.DWORD),("size_low",W.DWORD),("links",W.DWORD),("index_high",W.DWORD),("index_low",W.DWORD)]
    kernel.GetFileInformationByHandle.argtypes=[W.HANDLE,ctypes.POINTER(Info)]
    handle=kernel.CreateFileW(str(Path(path).absolute()),0,7,None,3,0x02000000,None)
    if handle==ctypes.c_void_p(-1).value:raise ctypes.WinError(ctypes.get_last_error())
    try:
        info=Info()
        if not kernel.GetFileInformationByHandle(handle,ctypes.byref(info)):raise ctypes.WinError(ctypes.get_last_error())
        buffer=ctypes.create_unicode_buffer(32768)
        length=kernel.GetFinalPathNameByHandleW(handle,buffer,len(buffer),0)
        if not 0<length<len(buffer):raise ctypes.WinError(ctypes.get_last_error())
        final=buffer.value
        if final.startswith("\\\\?\\UNC\\"):final="\\\\"+final[8:]
        elif final.startswith("\\\\?\\"):final=final[4:]
        identity=f"file:{info.volume:08x}:{info.index_high:08x}{info.index_low:08x}"
        return final,identity
    finally:kernel.CloseHandle(handle)


def final_path(path):
    path=Path(path).absolute()
    if os.name!="nt":return str(path.resolve())
    if path.exists():return windows_file(path)[0]
    if path.parent==path:raise ValueError("Nicht aufloesbarer Windows-Pfad.")
    return str(Path(final_path(path.parent))/path.name)


def lock_identity(path):
    path=Path(path).absolute()
    if path.exists():identity=windows_file(path)[1]
    else:identity="new:"+canonical(path.parent)+"\\"+os.path.normcase(path.name)
    return hashlib.sha256(identity.encode("utf-8")).hexdigest()


@contextmanager
def identity_mutex(path,timeout=2.0):
    kernel=ctypes.WinDLL("kernel32",use_last_error=True)
    kernel.CreateMutexW.argtypes=[ctypes.c_void_p,W.BOOL,W.LPCWSTR];kernel.CreateMutexW.restype=W.HANDLE
    kernel.WaitForSingleObject.argtypes=[W.HANDLE,W.DWORD];kernel.WaitForSingleObject.restype=W.DWORD
    kernel.ReleaseMutex.argtypes=[W.HANDLE];kernel.CloseHandle.argtypes=[W.HANDLE]
    handle=kernel.CreateMutexW(None,False,"Local\\RectoFlow-config-"+lock_identity(path))
    if not handle:raise ctypes.WinError(ctypes.get_last_error())
    acquired=False
    try:
        state=kernel.WaitForSingleObject(handle,round(timeout*1000))
        if state==258:raise LockBusy("Dieselbe Windows-Datei wird bereits verwendet.")
        if state not in (0,128):raise ctypes.WinError(ctypes.get_last_error())
        acquired=True;yield
    finally:
        if acquired:kernel.ReleaseMutex(handle)
        kernel.CloseHandle(handle)


def config_lock(path):
    path = Path(final_path(path))
    if path.parent.parent.name == "profiles":
        root = path.parent.parent.parent
        return root / ".locks" / ("config-" + hashlib.sha256(canonical(path).encode()).hexdigest() + ".lock")
    return path.with_name(path.name + ".lock")


@contextmanager
def config_exclusive(path):
    # Stable pathname lock survives os.replace; file-ID mutex also joins hard-link aliases.
    with exclusive(config_lock(path)):
        with identity_mutex(path):yield


@contextmanager
def config_transaction(path):
    path=Path(final_path(path))
    with ExitStack() as stack:
        if path.parent.parent.name=="profiles":
            lockroot=path.parent.parent.parent/".locks"
            stack.enter_context(exclusive(lockroot/"profiles.lock"))
            stack.enter_context(exclusive(lockroot/("profile-"+path.parent.name+".lock")))
        stack.enter_context(config_exclusive(path))
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
