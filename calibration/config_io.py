"""Atomare Aktualisierung, unbekannte Einstellungen erhalten, Konflikte stoppen."""
import copy
import hashlib
import json
import os
from pathlib import Path
import tempfile

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
    path = Path(path)
    tmp = None
    try:
        if hashlib.sha256(path.read_bytes()).hexdigest() != expected_digest:
            raise CalibrationError("CONFIG_WRITE_FAILED", "Config wurde waehrend der Kalibrierung geaendert; neu starten.")
        validator(cfg)
        data = json.dumps(cfg, ensure_ascii=False, indent=2, allow_nan=False).encode("utf-8")
        # Unique Temp im selben Verzeichnis => gleicher Datentraeger fuer replace.
        with tempfile.NamedTemporaryFile(dir=path.parent, prefix=path.name + ".", suffix=".tmp", delete=False) as stream:
            tmp = Path(stream.name)
            stream.write(data)
            stream.flush()
            os.fsync(stream.fileno())
        validator(json.loads(tmp.read_bytes()))
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
