"""Spike-only suspended CreateProcess/Job supervisor; not a security sandbox."""
import ctypes as C
from ctypes import wintypes as W
import json
import msvcrt
import os
from pathlib import Path
import subprocess
import time

K = C.WinDLL('kernel32', use_last_error=True)

class Startup(C.Structure):
    _fields_ = [('cb',W.DWORD),('reserved',W.LPWSTR),('desktop',W.LPWSTR),('title',W.LPWSTR),
                ('x',W.DWORD),('y',W.DWORD),('xs',W.DWORD),('ys',W.DWORD),('xc',W.DWORD),('yc',W.DWORD),
                ('fill',W.DWORD),('flags',W.DWORD),('show',W.WORD),('reserved2len',W.WORD),
                ('reserved2',C.c_void_p),('stdin',W.HANDLE),('stdout',W.HANDLE),('stderr',W.HANDLE)]
class Process(C.Structure):
    _fields_ = [('process',W.HANDLE),('thread',W.HANDLE),('pid',W.DWORD),('tid',W.DWORD)]
class Basic(C.Structure):
    _fields_ = [('process_time',C.c_int64),('job_time',C.c_int64),('flags',W.DWORD),
                ('min_working',C.c_size_t),('max_working',C.c_size_t),('active',W.DWORD),
                ('affinity',C.c_size_t),('priority',W.DWORD),('scheduling',W.DWORD)]
class IO(C.Structure):
    _fields_ = [(name,C.c_uint64) for name in ('read_ops','write_ops','other_ops','read_bytes','write_bytes','other_bytes')]
class Extended(C.Structure):
    _fields_ = [('basic',Basic),('io',IO),('process_memory',C.c_size_t),('job_memory',C.c_size_t),
                ('peak_process',C.c_size_t),('peak_job',C.c_size_t)]
class Memory(C.Structure):
    _fields_ = [('cb',W.DWORD),('faults',W.DWORD)] + [(name,C.c_size_t) for name in
        ('peak_working','working','quota_peak_paged','quota_paged','quota_peak_nonpaged','quota_nonpaged','pagefile','peak_pagefile')]

K.CreateJobObjectW.argtypes=[C.c_void_p,W.LPCWSTR];K.CreateJobObjectW.restype=W.HANDLE
K.SetInformationJobObject.argtypes=[W.HANDLE,C.c_int,C.c_void_p,W.DWORD]
K.AssignProcessToJobObject.argtypes=[W.HANDLE,W.HANDLE]
K.CreateProcessW.argtypes=[W.LPCWSTR,W.LPWSTR,C.c_void_p,C.c_void_p,W.BOOL,W.DWORD,C.c_void_p,W.LPCWSTR,C.POINTER(Startup),C.POINTER(Process)]
K.CreateProcessW.restype=W.BOOL
K.ResumeThread.argtypes=[W.HANDLE];K.ResumeThread.restype=W.DWORD
K.WaitForSingleObject.argtypes=[W.HANDLE,W.DWORD];K.WaitForSingleObject.restype=W.DWORD
K.GetExitCodeProcess.argtypes=[W.HANDLE,C.POINTER(W.DWORD)]
K.TerminateJobObject.argtypes=[W.HANDLE,W.UINT]
K.TerminateProcess.argtypes=[W.HANDLE,W.UINT]
K.CloseHandle.argtypes=[W.HANDLE]
K.OpenProcess.argtypes=[W.DWORD,W.BOOL,W.DWORD];K.OpenProcess.restype=W.HANDLE
K.IsProcessInJob.argtypes=[W.HANDLE,W.HANDLE,C.POINTER(W.BOOL)]
K.GetCurrentProcess.restype=W.HANDLE
PS=C.WinDLL('psapi',use_last_error=True)
PS.GetProcessMemoryInfo.argtypes=[W.HANDLE,C.POINTER(Memory),W.DWORD]

def checked(value):
    if not value: raise C.WinError(C.get_last_error())
    return value

def in_job():
    result=W.BOOL();checked(K.IsProcessInJob(K.GetCurrentProcess(),None,C.byref(result)))
    return bool(result.value)

class Child:
    def __init__(self, command, request, folder, memory=2*1024**3, clean_path=False):
        self.job=None;self.proc=Process();self.fds=[];self.resumed=False
        self.started=time.perf_counter();self.peak=0
        try:
            self.job=checked(K.CreateJobObjectW(None,None))
            limits=Extended();limits.basic.flags=0x2000|0x100  # KILL_ON_JOB_CLOSE | PROCESS_MEMORY
            limits.process_memory=memory
            checked(K.SetInformationJobObject(self.job,9,C.byref(limits),C.sizeof(limits)))
            ir,iw=os.pipe();orr,ow=os.pipe();er,ew=os.pipe()
            self.fds=[ir,iw,orr,ow,er,ew]
            for fd in (ir,ow,ew):os.set_inheritable(fd,True)
            start=Startup();start.cb=C.sizeof(start);start.flags=0x100
            start.stdin=msvcrt.get_osfhandle(ir);start.stdout=msvcrt.get_osfhandle(ow);start.stderr=msvcrt.get_osfhandle(ew)
            env=dict(os.environ)
            for key in ('PYTHONPATH','PYTHONHOME','VIRTUAL_ENV'):env.pop(key,None)
            if clean_path:env['PATH']=str(Path(env['WINDIR'])/'System32')+os.pathsep+env['WINDIR']
            block=C.create_unicode_buffer('\0'.join(k+'='+v for k,v in sorted(env.items()))+'\0\0')
            cmd=C.create_unicode_buffer(subprocess.list2cmdline([str(x) for x in command]))
            checked(K.CreateProcessW(str(command[0]),cmd,None,None,True,4|0x08000000|0x400,
                                    block,str(folder),C.byref(start),C.byref(self.proc)))
            for fd in (ir,ow,ew):self._close_fd(fd)
            # No native provider may execute until this assignment succeeds.
            checked(K.AssignProcessToJobObject(self.job,self.proc.process))
            previous=K.ResumeThread(self.proc.thread)
            if previous != 1:raise RuntimeError('Unexpected suspended-thread count')
            self.resumed=True
            raw=json.dumps(request,allow_nan=False).encode()+b'\n'
            assert len(raw)<16384
            with os.fdopen(iw,'wb',closefd=True) as stream:stream.write(raw)
            self.fds.remove(iw)
            self.outfd=orr;self.errfd=er
        except BaseException:
            if self.proc.process:K.TerminateProcess(self.proc.process,91)
            self.close();raise

    def _close_fd(self,fd):os.close(fd);self.fds.remove(fd)
    def wait(self,timeout=60,cancel_after=None):
        stopped=None
        while K.WaitForSingleObject(self.proc.process,20)==258:
            info=Memory();info.cb=C.sizeof(info)
            if PS.GetProcessMemoryInfo(self.proc.process,C.byref(info),C.sizeof(info)):
                self.peak=max(self.peak,int(info.peak_working))
            elapsed=time.perf_counter()-self.started
            if elapsed>=timeout or (cancel_after is not None and elapsed>=cancel_after):
                stopped='CANCELLED' if cancel_after is not None and elapsed>=cancel_after else 'TIMEOUT'
                checked(K.TerminateJobObject(self.job,92))
                if K.WaitForSingleObject(self.proc.process,10000)!=0:raise RuntimeError('Own worker did not terminate')
                break
        code=W.DWORD();checked(K.GetExitCodeProcess(self.proc.process,C.byref(code)))
        with os.fdopen(self.outfd,'rb') as stream:out=stream.read(16385)
        self.fds.remove(self.outfd)
        with os.fdopen(self.errfd,'rb') as stream:err=stream.read(16385)
        self.fds.remove(self.errfd)
        assert len(out)<=16384 and len(err)<=16384
        result={'pid':int(self.proc.pid),'exit_code':int(code.value),'termination':stopped,
                'elapsed_seconds':time.perf_counter()-self.started,'peak_working_set_bytes':self.peak,
                'assigned_before_resume':True,'stderr':err.decode(errors='replace')}
        result['response']=json.loads(out) if out else None
        return result
    def close(self):
        if self.job:K.CloseHandle(self.job);self.job=None
        for fd in list(self.fds):self._close_fd(fd)
        for name in ('thread','process'):
            handle=getattr(self.proc,name)
            if handle:K.CloseHandle(handle);setattr(self.proc,name,None)
    def __enter__(self):return self
    def __exit__(self,*args):self.close()

def handle_for_owned_pid(pid):return checked(K.OpenProcess(0x100000,False,pid))
