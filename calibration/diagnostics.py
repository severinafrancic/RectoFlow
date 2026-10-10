"""Private local attempt ledger. Never upload this directory or its first frame."""
from contextlib import contextmanager
from contextvars import ContextVar
from datetime import datetime
import json
import hashlib
import os
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


def checkpoint(name, **values):
    diagnostic = current()
    if diagnostic:
        diagnostic.checkpoint(name, **values)


@contextmanager
def polling():
    """Only transition aggregates are journalled; not every screen/guard poll."""
    diagnostic = current()
    if diagnostic:
        diagnostic.poll_depth += 1
    try:
        yield
    finally:
        if diagnostic:
            diagnostic.poll_depth -= 1


@contextmanager
def first_snapshot_boundary():
    diagnostic=current()
    depth=diagnostic.poll_depth if diagnostic else 0
    if diagnostic and not diagnostic._first_requested:diagnostic.poll_depth=0
    try:
        yield
    finally:
        if diagnostic:diagnostic.poll_depth=depth


class Diagnostic:
    def __init__(self, root, version, mode):
        self.root = Path(root)
        self.log_path = None
        self.dialog_shown = False
        self.private_values = set()
        self._seen_errors = []
        self._error_events = {}
        self.attempt_dir = None
        self.poll_depth = 0
        self._first_requested = False
        self.data = dict(schema=1,kind="rectoflow-workflow-attempt",diagnostic_id=uuid.uuid4().hex, version=version, mode=mode,
                         phase="LAUNCHER", return_code=None, exception_type=None,
                         failure_phase=None,
                         exception_message=None, traceback=None, browser_name=None,
                         monitor=None, dpi=None, window_bounds=None, run_path=None,
                         manifest_created=False, capture_count=0)
        self.data.update(primary_failure=None, history=[], terminal_outcome=None, exit_code=None)
        self.data.update(last_successful_checkpoint=None, failed_checkpoint=None, active_checkpoint=None,
                         first_frame_acquired=False, first_frame_path=None, first_frame_sha256=None,
                         first_frame_width=None, first_frame_height=None, first_frame_timestamp=None,
                         target_bound=False, confirmation_accepted=False, screenshot_requested=False,
                         run_created=False, initial_manifest_created=False, stage_path=None, first_crop=False, button_preparation_reached=False,
                         navigation_reached=False, capture_backend="Pillow.ImageGrab/main-monitor")
        self._init_attempt()
        self.checkpoint("LAUNCHER_ENTER")
        try:
            build=json.loads((self.root/"BUILD_METADATA.json").read_bytes())
            for key in ("source_commit","source_tree"):
                value=build.get(key)
                if isinstance(value,str) and re.fullmatch(r"[0-9a-f]{40}",value):self.data[key]=value
            self.write()
        except Exception:
            pass

    def _init_attempt(self):
        for resolve in (lambda:self.root / "data" / "diagnostics" / "attempts",
                        lambda:Path(tempfile.gettempdir()) / "RectoFlow-diagnostics" / "attempts"):
            try:
                target = resolve() / self.data["diagnostic_id"]
                target.mkdir(parents=True, exist_ok=False)
                (target / "events.jsonl").touch()
                self.attempt_dir = target
                return
            except Exception:
                continue

    def checkpoint(self, name, **values):
        if self.poll_depth and name != "FAIL" and not name.startswith("FIRST_"):
            return
        self.data["active_checkpoint"] = name.removesuffix("_BEGIN")
        successful=(name.endswith(("_OK", "_ACQUIRED", "_ACCEPTED", "_SENT")) or name in ("LAUNCHER_ENTER", "CAPTURE_LOOP_ENTER", "WORKFLOW_COMPLETE"))
        if name=="NEXT_CLICK_SENT" and values.get("inserted_events")!=2:successful=False
        if successful:
            self.data["last_successful_checkpoint"] = name
        flags = {"TARGET_BIND_OK":"target_bound", "FINAL_CONFIRMATION_ACCEPTED":"confirmation_accepted",
                 "FIRST_SCREENSHOT_REQUESTED":"screenshot_requested", "RUN_PUBLISH_OK":"run_created",
                 "INITIAL_MANIFEST_WRITE_OK":"initial_manifest_created",
                 "FIRST_CROP_OK":"first_crop", "BUTTON_PREPARE_BEGIN":"button_preparation_reached",
                 "NAVIGATION_CHECK_BEGIN":"navigation_reached"}
        if name in flags:self.data[flags[name]] = True
        self._journal(dict(event=name, timestamp=datetime.now().astimezone().isoformat(), **values))
        self.write()

    def _journal(self, event):
        try:
            if self.attempt_dir:
                with (self.attempt_dir / "events.jsonl").open("a", encoding="utf-8") as stream:
                    stream.write(json.dumps(event, ensure_ascii=False) + "\n")
                    stream.flush()
                    # Small number of boundary events, never one fsync per polling frame.
                    os.fsync(stream.fileno())
        except Exception:
            self.data["journal_write_failed"] = True

    def first_frame(self, image):
        """Persist before dimension/post-screenshot guards. Failure is explicit."""
        if self.data["first_frame_acquired"]:
            return
        from .failures import boundary, StopRun
        self.data.update(first_frame_acquired=True, first_frame_width=image.width,
                         first_frame_height=image.height, first_frame_timestamp=datetime.now().astimezone().isoformat())
        self.checkpoint("FIRST_SCREENSHOT_ACQUIRED", width=image.width, height=image.height)
        with boundary("FIRST_FRAME_PERSIST", "SCREENSHOT_PERSIST_FAILED"):
            if self.attempt_dir is None:
                raise StopRun("Lokaler Diagnosepfad nicht verfuegbar.", "SCREENSHOT_PERSIST_FAILED")
            path = self.attempt_dir / "first-frame.png"
            temporary = path.with_suffix(".png.tmp")
            with temporary.open("wb") as stream:
                image.save(stream, format="PNG")
                stream.flush(); os.fsync(stream.fileno())
            os.replace(temporary, path)
            self.data.update(first_frame_path=str(path), first_frame_sha256=hashlib.sha256(path.read_bytes()).hexdigest())

    def redact(self, value):
        try:text = str(value)
        except Exception:text = "Fehlerdetail nicht lesbar ("+type(value).__name__+")."
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
                   "stage_path",
                   "manifest_created", "capture_count", "mode"}
        self.data.update({k: v for k, v in values.items() if k in allowed})
        self.write()

    def failure(self, error, recoverable=False):
        try:self._failure(error,recoverable)
        except Exception:
            self.data["diagnostic_recording_failed"]=True
            self.write()

    def _failure(self, error, recoverable=False):
        if any(error is seen or getattr(error,"diagnostic_origin",None) is seen for seen in self._seen_errors):
            if recoverable and id(error) in self._error_events:
                self._error_events[id(error)]["kind"]="warning"
                if self.data["terminal_outcome"]=="TECHNICAL_FAILURE":self.data["terminal_outcome"]=None
                self.write()
            return
        self._seen_errors.append(error)
        # Stack only: never capture locals or source lines (which can contain secrets).
        frames = traceback.extract_tb(error.__traceback__ or (error.__cause__.__traceback__ if error.__cause__ else None))
        stack = [dict(file=Path(f.filename).name, line=f.lineno, function=f.name) for f in frames]
        cancelled=getattr(error,"code",None) in ("CALIBRATION_CANCELLED","USER_CANCELLED") or isinstance(error,KeyboardInterrupt)
        code=str(getattr(error,"failure_code",getattr(error,"code",type(error).__name__)))
        checkpoint_name=getattr(error,"failed_checkpoint",None) or self.data["active_checkpoint"] or self.data["phase"]
        event=dict(timestamp=datetime.now().astimezone().isoformat(),code=code,exception_type=type(error).__name__,
                   message=self.redact(error),phase=self.data["phase"],traceback=stack,
                   checkpoint=checkpoint_name, failure_class="USER_CANCELLED" if cancelled else code.split("_")[0],
                   last_successful_checkpoint=self.data["last_successful_checkpoint"],
                   metadata=getattr(error,"metadata",{}),
                   kind="user_cancel" if cancelled else "warning" if recoverable else "technical_failure")
        # Original cause chain: no locals, source lines, config dumps or full titles.
        causes=[]; cause=error.__cause__
        while cause is not None and len(causes)<8:
            causes.append(dict(exception_type=type(cause).__name__,message=self.redact(cause)))
            cause=cause.__cause__
        event["causes"]=causes
        self.data["failed_checkpoint"] = checkpoint_name
        self._journal(dict(event="FAIL", **event))
        self.data["history"].append(event)
        self._error_events[id(error)]=event
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
            if self.data.get("active_checkpoint") != "WORKFLOW_COMPLETE":
                self.checkpoint("WORKFLOW_COMPLETE")
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
        self._snapshot()

    def _snapshot(self):
        try:
            if self.attempt_dir is None:return
            for name, contents in (("attempt.json",json.dumps(self.data,ensure_ascii=False,indent=2)),
                                   ("SUMMARY.txt",self.summary_text())):
                path=self.attempt_dir/name; tmp=path.with_suffix(path.suffix+".tmp")
                with tmp.open("w",encoding="utf-8") as stream:
                    stream.write(contents);stream.flush();os.fsync(stream.fileno())
                os.replace(tmp,path)
        except Exception:
            self.data["snapshot_write_failed"]=True

    def summary_text(self):
        d=self.data; primary=d["primary_failure"] or {}
        lines=[f"Diagnostic ID: {d['diagnostic_id']}",f"Mode: {d['mode']}",
               f"Build subject: {d.get('source_commit','source checkout; see builder receipt')}",
               f"Outcome: {d['terminal_outcome'] or 'IN_PROGRESS / interrupted if process has ended'}",f"Exit code: {d['exit_code']}",
               f"Last successful checkpoint: {d['last_successful_checkpoint']}",f"Failed checkpoint: {d['failed_checkpoint']}",
               f"Failure code: {primary.get('code','none')}",f"Detail: {primary.get('message','none')}",
               f"Primary failure checkpoint: {primary.get('checkpoint','none')}",
               f"Last success before primary failure: {primary.get('last_successful_checkpoint','none')}"]
        for label,key in (("Target bound","target_bound"),("Final confirmation accepted","confirmation_accepted"),
                          ("Screenshot requested","screenshot_requested"),("First full frame","first_frame_acquired"),
                          ("Run created","run_created"),("Manifest created","manifest_created"),("First crop","first_crop"),
                          ("Button preparation reached","button_preparation_reached"),("Navigation reached","navigation_reached")):
            lines.append(f"{label}: {'Yes' if d[key] else 'No'}")
        lines += [f"Private frame path: {d['first_frame_path'] or 'none'}",f"Run path: {d['run_path'] or 'none'}",
                  f"Hidden staging path: {d['stage_path'] or 'none'}",f"Initial manifest written in staging: {'Yes' if d['initial_manifest_created'] else 'No'}",
                  "first-frame.png is PRIVATE LOCAL DATA. Do not upload it."]
        return "\n".join(lines)+"\n"

    def _write(self):
        self.data["timestamp"] = datetime.now().astimezone().isoformat()
        filename = "rectoflow-" + self.data["diagnostic_id"] + ".jsonl"
        destinations = [lambda:self.root / "data" / "logs" / filename,
                        lambda:Path(tempfile.gettempdir()) / "RectoFlow-logs" / filename, lambda:self.log_path]
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
        primary=self.data["primary_failure"] or {}
        return (f"RectoFlow hat den Vorgang nicht erfolgreich abgeschlossen.\n"
                f"Returncode: {code}\nPhase: {self.data['failure_phase'] or self.data['phase']}\n"
                f"Ausgang: {self.data['terminal_outcome']}\n"
                f"Fehler: {(self.data['primary_failure'] or {}).get('code','Keine naeheren Fehlerdetails')}\n"
                f"Fehlgeschlagener Schritt: {primary.get('checkpoint') or self.data['failed_checkpoint'] or 'Unbekannt'}\n"
                f"Letzter erfolgreicher Schritt: {primary.get('last_successful_checkpoint') or self.data['last_successful_checkpoint'] or 'Unbekannt'}\n"
                f"Diagnose-ID: {self.data['diagnostic_id']}\n"
                f"Logpfad: {self.attempt_dir / 'events.jsonl' if self.attempt_dir else self.log_path or 'Nicht verfuegbar; lokale Protokollierung fehlgeschlagen.'}\n"
                f"Zusammenfassung: {self.attempt_dir / 'SUMMARY.txt' if self.attempt_dir else 'Nicht verfuegbar'}\n"
                f"Lokale Diagnoseaufnahme: {self.data['first_frame_path'] or 'Noch nicht vorhanden'}\n"
                f"Run: {self.data['run_path'] if self.data['run_created'] else 'noch nicht erzeugt'}\n"
                f"Manifest: {'vorhanden' if self.data['manifest_created'] else 'nicht vorhanden'}\n\n{detail}")

    def needs_error_dialog(self, code):
        return code != 0 and not (self.data["terminal_outcome"]=="USER_CANCELLED" and self.data["primary_failure"] is None)
