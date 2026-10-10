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


def failure(error):
    diagnostic = current()
    if diagnostic:
        diagnostic.failure(error)


class Diagnostic:
    def __init__(self, root, version, mode):
        self.root = Path(root)
        self.log_path = None
        self.dialog_shown = False
        self.private_values = set()
        self.data = dict(diagnostic_id=uuid.uuid4().hex, version=version, mode=mode,
                         phase="LAUNCHER", return_code=None, exception_type=None,
                         failure_phase=None,
                         exception_message=None, traceback=None, browser_name=None,
                         monitor=None, dpi=None, window_bounds=None, run_path=None,
                         manifest_created=False, capture_count=0)

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

    def failure(self, error):
        if self.data["exception_type"]:
            return  # a cleanup/logging error must never replace the original failure
        # Stack only: never capture locals or source lines (which can contain secrets).
        frames = traceback.extract_tb(error.__traceback__)
        stack = [dict(file=Path(f.filename).name, line=f.lineno, function=f.name) for f in frames]
        self.data.update(exception_type=type(error).__name__,
                         failure_phase=self.data["phase"],
                         exception_message=self.redact(error), traceback=stack)
        self.write()

    def finish(self, code):
        self.data["return_code"] = code
        if code == 0:
            self.data["phase"] = "COMPLETE"
        self.write()
        return code

    def write(self):
        self.data["timestamp"] = datetime.now().astimezone().isoformat()
        filename = "rectoflow-" + self.data["diagnostic_id"] + ".jsonl"
        destinations = [self.log_path] if self.log_path else []
        destinations += [self.root / "data" / "logs" / filename,
                         Path(tempfile.gettempdir()) / "RectoFlow-logs" / filename]
        for path in dict.fromkeys(destinations):
            try:
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
                f"Diagnose-ID: {self.data['diagnostic_id']}\n"
                f"Logpfad: {self.log_path or 'Nicht verfuegbar; lokale Protokollierung fehlgeschlagen.'}\n\n{detail}")
