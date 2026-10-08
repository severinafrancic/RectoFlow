"""Read-only current-session lock flag. Never inspects or operates authentication/private UI."""
import ctypes
from ctypes import wintypes as W
from datetime import datetime,timezone
import json
import os
from pathlib import Path

k=ctypes.WinDLL('kernel32',use_last_error=True)
w=ctypes.WinDLL('wtsapi32',use_last_error=True)
k.ProcessIdToSessionId.argtypes=[W.DWORD,ctypes.POINTER(W.DWORD)];k.ProcessIdToSessionId.restype=W.BOOL
session=W.DWORD()
if not k.ProcessIdToSessionId(os.getpid(),ctypes.byref(session)):raise ctypes.WinError(ctypes.get_last_error())
class LEVEL1(ctypes.Structure):
    _fields_=[('session_id',W.ULONG),('state',ctypes.c_int),('flags',W.LONG),
      ('station',W.WCHAR*33),('username',W.WCHAR*21),('domain',W.WCHAR*18),
      ('times',ctypes.c_longlong*5),('counts',W.DWORD*6)]
class INFO(ctypes.Structure):_fields_=[('level',W.DWORD),('data',LEVEL1)]
w.WTSQuerySessionInformationW.argtypes=[W.HANDLE,W.DWORD,ctypes.c_int,ctypes.POINTER(ctypes.c_void_p),ctypes.POINTER(W.DWORD)]
w.WTSQuerySessionInformationW.restype=W.BOOL
w.WTSFreeMemory.argtypes=[ctypes.c_void_p]
buffer=ctypes.c_void_p();size=W.DWORD()
record={'observed_utc':datetime.now(timezone.utc).isoformat(),'session_id':session.value,
 'scope':'current-session public lock/connection flags only; no names stored',
 'official_reference':'https://learn.microsoft.com/en-us/windows/win32/api/wtsapi32/ns-wtsapi32-wtsinfoex_level1_w'}
if not w.WTSQuerySessionInformationW(None,session,25,ctypes.byref(buffer),ctypes.byref(size)):
    record.update({'result':'UNKNOWN','win32_error':ctypes.get_last_error()})
else:
    try:
        if size.value<ctypes.sizeof(INFO):raise RuntimeError('Session information buffer too small')
        value=ctypes.cast(buffer,ctypes.POINTER(INFO)).contents
        record.update({'level':value.level,'reported_session_id':value.data.session_id,
        'connection_state':value.data.state,'session_flags':value.data.flags,
        'result':{0:'LOCKED',1:'UNLOCKED'}.get(value.data.flags,'UNKNOWN')})
    finally:w.WTSFreeMemory(buffer)
root=Path(__file__).resolve().parent
(root/'.build-closure-session.json').write_text(json.dumps(record,indent=2),encoding='utf-8')
print(json.dumps(record,indent=2))
