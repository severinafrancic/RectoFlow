"""Stable boundary classifications without discarding the original exception."""
from contextlib import contextmanager
from functools import wraps
from contextvars import ContextVar

_boundaries=ContextVar("rectoflow_boundaries",default=())


def instrument(name, code):
    def decorate(function):
        @wraps(function)
        def call(*args, **kwargs):
            with boundary(name, code):
                return function(*args, **kwargs)
        return call
    return decorate


class StopRun(RuntimeError):
    def __init__(self, message, code=None, **metadata):
        super().__init__(message)
        if code:
            self.code = self.failure_code = code
        self.metadata = metadata


class UserCancelled(StopRun):
    code = failure_code = "USER_CANCELLED"


class BoundaryIOError(OSError, StopRun):
    pass


class BoundaryValueError(ValueError):
    pass


def classified(error, code, checkpoint, metadata):
    # Existing domain errors remain intact (including legacy CalibrationError.code).
    if isinstance(error, KeyboardInterrupt):
        result = error
        result.failure_code = "USER_CANCELLED"
    elif getattr(error, "failure_code", None) or getattr(error, "code", None):
        result = error
        if not getattr(result, "failure_code", None):
            result.failure_code = ("USER_CANCELLED" if result.code == "CALIBRATION_CANCELLED"
                                   else code if result.code in ("SCREENSHOT_FAILED", "INVALID_RECTANGLE") else result.code)
    else:
        cls = BoundaryIOError if isinstance(error, OSError) else BoundaryValueError if isinstance(error, ValueError) else StopRun
        result = cls(("SCREENSHOT_FAILED: " if code=="SCREENSHOT_ACQUIRE_FAILED" else "")+str(error))
        result.failure_code = code
    if not getattr(result, "failed_checkpoint", None):
        result.failed_checkpoint = checkpoint
    result.metadata = {**metadata, **getattr(result, "metadata", {})}
    return result


@contextmanager
def boundary(name, code, *, ok=None, **metadata):
    from .diagnostics import checkpoint, failure
    parents=_boundaries.get()
    token=_boundaries.set((*parents,name))
    duplicate=name in parents
    if not duplicate:checkpoint(name + "_BEGIN", **metadata)
    try:
        yield metadata
    except (Exception, KeyboardInterrupt) as error:
        failed_name=name
        if name=="TARGET_GUARD" and "FIRST_FRAME_GUARD" in parents:
            failed_name="FIRST_FRAME_GUARD"
            metadata["guard_checkpoint"]=name
        result = classified(error, code, failed_name, metadata)
        if result is not error:result.__cause__ = error
        failure(result)
        if result is error:
            raise
        raise result from error
    else:
        if not duplicate:checkpoint(ok or name + "_OK", **metadata)
    finally:
        _boundaries.reset(token)
