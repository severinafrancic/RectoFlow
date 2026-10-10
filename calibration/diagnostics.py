"""Per-workflow local diagnostics. No stdout, screenshots or config dumps."""
from contextlib import contextmanager
from contextvars import ContextVar
from datetime import datetime
import json
from pathlib import Path
import re
import tempfile
import traceback
import uuid

PHASES = ("LAUNCHER", "CONFIG_LOAD", "VALIDATION", "TARGET_BINDING", "CALIBRATION",
          "FINAL_CONFIRMATION", "RUN_CREATE", "MANIFEST_WRITE", "FIRST_CAPTURE",
          "CAPTURE_LOOP", "EXPORT", "COMPLETE")
_active = ContextVar("rectoflow_diagnostic", default=None)


def current():
    return _active.get()


@contextmanager
def scope(diagnostic):
    token = _active.set(diagnostic)
    try:
        yield diagnostic
    finally:
        _active.reset(token)


def phase(name, **values):
    diagnostic = current()
    if diagnostic:
        diagnostic.phase(name, **values)


def failure(error, recoverable=False):
    diagnostic = current()
    if diagnostic:
        diagnostic.failure(error, recoverable=recoverable)


class Diagnostic:
    def __init__(self, root, version, mode):
        self.root = Path(root)
        self.log_path = None
        self.dialog_shown = False
        self.private_values = set()
        self._seen_errors = []
        self.data = dict(diagnostic_id=uuid.uuid4().hex, version=version, mode=mode,
                         phase="LAUNCHER", return_code=None, exception_type=None,
                         failure_phase=None,
                         exception_message=None, traceback=None, browser_name=None,
                         monitor=None, dpi=None, window_bounds=None, run_path=None,
                         manifest_created=False, capture_count=0)
        self.data.update(primary_failure=None, history=[], terminal_outcome=None, exit_code=None)

    def redact(self, value):
        text = str(value)
        for private in sorted(self.private_values, key=len, reverse=True):
            if private:
                text = text.replace(private, "<private>")
        text = re.sub(r"(?:https?|file)://[^\s\"<>]+", "<url>", text, flags=re.I)
        text = re.sub(r"(?i)(password|passwd|cookie|authorization|token)\s*[:=]\s*[^\s,;]+", r"\1=<private>", text)
        return text

    def phase(self, name, **values):
        if name not in PHASES:
            raise ValueError("Unknown diagnostic phase")
        self.data["phase"] = name
        allowed = {"browser_name", "monitor", "dpi", "window_bounds", "run_path",
                   "manifest_created", "capture_count", "mode"}
        self.data.update({k: v for k, v in values.items() if k in allowed})
        self.write()

    def failure(self, error, recoverable=False):
        if any(error is seen for seen in self._seen_errors):return
        self._seen_errors.append(error)
        # Stack only: never capture locals or source lines (which can contain secrets).
        frames = traceback.extract_tb(error.__traceback__)
        stack = [dict(file=Path(f.filename).name, line=f.lineno, function=f.name) for f in frames]
        cancelled=getattr(error,"code",None) in ("CALIBRATION_CANCELLED","USER_CANCELLED") or isinstance(error,KeyboardInterrupt)
        event=dict(timestamp=datetime.now().astimezone().isoformat(),code=getattr(error,"code",type(error).__name__),exception_type=type(error).__name__,
                   message=self.redact(error),phase=self.data["phase"],traceback=stack,
                   kind="user_cancel" if cancelled else "warning" if recoverable else "technical_failure")
        self.data["history"].append(event)
        if cancelled:
            self.data["terminal_outcome"]="USER_CANCELLED"
        else:
            if self.data["primary_failure"] is None:self.data["primary_failure"]=event
            if not recoverable:self.data["terminal_outcome"]="TECHNICAL_FAILURE"
        self.sync_primary()
        self.write()

    def sync_primary(self):
        primary=self.data["primary_failure"]
        self.data.update(exception_type=primary["exception_type"] if primary else None,
                         failure_phase=primary["phase"] if primary else None,
                         exception_message=primary["message"] if primary else None,
                         traceback=primary["traceback"] if primary else None)

    def finish(self, code):
        self.data["return_code"] = code
        self.data["exit_code"] = code
        if code == 0:
            self.data["phase"] = "COMPLETE"
            self.data["terminal_outcome"]="SUCCESS"
            self.data["primary_failure"]=None
            self.sync_primary()
        elif self.data["terminal_outcome"] is None:
            self.data["terminal_outcome"]="TECHNICAL_FAILURE"
        self.write()
        return code

    def write(self):
        # Even unavailable temp resolution/serialization must not mask a workflow error.
        try:
            self._write()
        except Exception:
            self.log_path = None

    def _write(self):
        self.data["timestamp"] = datetime.now().astimezone().isoformat()
        filename = "rectoflow-" + self.data["diagnostic_id"] + ".jsonl"
        destinations = [lambda:self.log_path, lambda:self.root / "data" / "logs" / filename,
                        lambda:Path(tempfile.gettempdir()) / "RectoFlow-logs" / filename]
        attempted=set()
        for destination in destinations:
            try:
                path=destination()
                if path is None or path in attempted:continue
                attempted.add(path)
                path.parent.mkdir(parents=True, exist_ok=True)
                with path.open("a", encoding="utf-8") as stream:
                    stream.write(json.dumps(self.data, ensure_ascii=False) + "\n")
                self.log_path = path
                return
            except Exception:
                continue
        self.log_path = None

    def dialog_text(self, code):
        detail = self.data["exception_message"] or "Keine naeheren Fehlerdetails verfuegbar."
        return (f"RectoFlow hat den Vorgang nicht erfolgreich abgeschlossen.\n"
                f"Returncode: {code}\nPhase: {self.data['failure_phase'] or self.data['phase']}\n"
                f"Ausgang: {self.data['terminal_outcome']}\n"
                f"Diagnose-ID: {self.data['diagnostic_id']}\n"
                f"Logpfad: {self.log_path or 'Nicht verfuegbar; lokale Protokollierung fehlgeschlagen.'}\n\n{detail}")

    def needs_error_dialog(self, code):
        return code != 0 and not (self.data["terminal_outcome"]=="USER_CANCELLED" and self.data["primary_failure"] is None)
