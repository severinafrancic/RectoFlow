"""Atomare Aktualisierung, unbekannte Einstellungen erhalten, Konflikte stoppen."""
import copy
import hashlib
import json
import os
from pathlib import Path
import tempfile
from datetime import datetime, timezone
import uuid
from .storage import config_transaction, LockBusy, final_path

from .geometry import CalibrationError, contains, validate_selection
from .regions import capture_names


def updated_config(original, rects, point, target, dom, navigation_mode=None):
    mode=navigation_mode or original.get("navigation_mode","next_button")
    validate_selection(rects, point, target["selection_bounds"],mode)
    cfg = copy.deepcopy(original)
    cfg.update(button_rect=list(rects["NEXT"]) if rects.get("NEXT") else None, next_point=list(point) if point else None,
               progress_rect=list(rects["PROGRESS"]) if rects.get("PROGRESS") else None)
    if capture_names(rects)==["LEFT","RIGHT"]:
        cfg.update(left_rect=list(rects["LEFT"]),right_rect=list(rects["RIGHT"]))
    else:
        cfg["regions"]=[list(rects[name]) for name in capture_names(rects)]
    cfg["navigation_mode"]=mode
    cfg["confirm_pdf_export"]=True
    # Ein durch die neue Auswahl ueberdeckter Parkpunkt wird sichtbar korrigiert.
    choices = [cfg["park_point"]] + [[x, y] for y in range(target["selection_bounds"][1] + 10, target["selection_bounds"][3], 20)
                                  for x in range(target["selection_bounds"][0] + 10, target["selection_bounds"][2], 20)]
    cfg["park_point"] = next((p for p in choices if 2 < p[0] < target["screen_size"][0] - 2 and 2 < p[1] < target["screen_size"][1] - 2 and not any(contains(r, p) for r in rects.values() if r)), None)
    if cfg["park_point"] is None:
        raise CalibrationError("INVALID_RECTANGLE", "Kein freier Maus-Parkpunkt vorhanden.")
    cfg["calibration"] = {"schema": 1, "coordinate_space": "primary_screen_physical_pixels",
                          "target": copy.deepcopy(target), "dom": copy.deepcopy(dom),
                          "requires_visual_confirmation": True}
    return cfg


def atomic_update(path, cfg, expected_digest, validator):
    try:
        path=Path(final_path(path))
        with config_transaction(path):
            return _atomic_update(path, cfg, expected_digest, validator)
    except (OSError, LockBusy) as error:
        raise CalibrationError("CONFIG_WRITE_FAILED", str(error)) from error


def _atomic_update(path, cfg, expected_digest, validator, exact_bytes=None):
    path = Path(path)
    tmp = None
    try:
        original = path.read_bytes()
        if hashlib.sha256(original).hexdigest() != expected_digest:
            raise CalibrationError("CONFIG_WRITE_FAILED", "Config wurde waehrend der Kalibrierung geaendert; neu starten.")
        validator(cfg)
        data = exact_bytes if exact_bytes is not None else json.dumps(cfg, ensure_ascii=False, indent=2, allow_nan=False).encode("utf-8")
        # Unique Temp im selben Verzeichnis => gleicher Datentraeger fuer replace.
        with tempfile.NamedTemporaryFile(dir=path.parent, prefix=path.name + ".", suffix=".tmp", delete=False) as stream:
            tmp = Path(stream.name)
            stream.write(data)
            stream.flush()
            os.fsync(stream.fileno())
        validator(json.loads(tmp.read_bytes()))
        stamp = datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S-%f")
        backup = path.with_name(path.stem + ".backup." + stamp + "." + uuid.uuid4().hex[:8] + path.suffix)
        backup_tmp=backup.with_suffix(backup.suffix+".tmp")
        try:
            with backup_tmp.open("xb") as stream:
                stream.write(original)
                stream.flush()
                os.fsync(stream.fileno())
            if backup_tmp.read_bytes()!=original:
                raise CalibrationError("CONFIG_WRITE_FAILED", "Backup konnte nicht verifiziert werden.")
            os.replace(backup_tmp,backup)
        finally:
            backup_tmp.unlink(missing_ok=True)
        if hashlib.sha256(path.read_bytes()).hexdigest() != expected_digest:
            raise CalibrationError("CONFIG_WRITE_FAILED", "Config-Konflikt unmittelbar vor dem Speichern.")
        os.replace(tmp, path)
    except CalibrationError:
        raise
    except Exception as error:
        raise CalibrationError("CONFIG_WRITE_FAILED", str(error)) from error
    finally:
        if tmp is not None and tmp.exists():
            tmp.unlink()


def backups(path):
    path = Path(final_path(path))
    return sorted(path.parent.glob(path.stem + ".backup.*" + path.suffix), reverse=True)


def restore(path, backup, validator):
    path, backup = Path(final_path(path)), Path(backup)
    with config_transaction(path):
        if backup.resolve() not in [p.resolve() for p in backups(path)]:
            raise CalibrationError("CONFIG_WRITE_FAILED", "Backup gehoert nicht zu dieser Config.")
        data = backup.read_bytes()
        cfg = json.loads(data.decode("utf-8-sig"))
        validator(cfg)
        _atomic_update(path, cfg, hashlib.sha256(path.read_bytes()).hexdigest(), validator,exact_bytes=data)


def record_template(path, state, data, expected_digest):
    """Publish a complete new template while holding the snapshot reader's locks."""
    from io import BytesIO
    from PIL import Image
    from .storage import atomic_bytes
    if state not in ("enabled","disabled"):raise ValueError("Unbekannte Button-Vorlage.")
    path=Path(final_path(path))
    with config_transaction(path):
        raw=path.read_bytes()
        if hashlib.sha256(raw).hexdigest()!=expected_digest:
            raise CalibrationError("CONFIG_WRITE_FAILED","Config wurde vor der Vorlagenaufnahme geaendert; neu starten.")
        cfg=json.loads(raw.decode("utf-8-sig"))
        with Image.open(BytesIO(data)) as image:
            image.load()
            if image.format!="PNG" or image.size!=tuple(cfg["button_rect"][2:]):
                raise ValueError("Button-Vorlage hat ungueltiges Format oder Abmessungen.")
        target=path.parent/f"button_{state}.png"
        if target.exists():raise ValueError(f"Vorlage existiert bereits: {target}. Fuer Neukalibrierung manuell umbenennen.")
        atomic_bytes(target,data)
        return target
