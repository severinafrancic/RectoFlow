"""Local file transport; single-use sessions, measured browser markers."""
import json
import math
from pathlib import Path
import time
import uuid
import threading
import html
from urllib.parse import quote

_sessions = {}
_session_lock = threading.Lock()


class DOMSession:
    def __init__(self):
        self.token = uuid.uuid4().hex
        self.created_ms = int(time.time()*1000)
        self.started = time.monotonic()
        with _session_lock:
            _sessions[self.token] = self

    def cancel(self):
        with _session_lock:
            _sessions.pop(self.token,None)

    def import_file(self,path):
        with _session_lock:
            if _sessions.get(self.token) is not self or not 0 <= time.monotonic()-self.started <= 180:
                raise CalibrationError("DOM_PICKER_FAILED","Sitzung abgelaufen oder bereits verwendet.")
            with Path(path).open("r",encoding="utf-8") as stream:
                text = stream.read(32001)
            payload = parse_payload(text,self.token)
            if payload["created_ms"] != self.created_ms:
                raise CalibrationError("DOM_PICKER_FAILED","Falscher Sitzungsbeginn.")
            del _sessions[self.token]
            return payload

    def write_helper(self,folder):
        folder=Path(folder); folder.mkdir(parents=True,exist_ok=True)
        path=folder/("session-"+self.token+".html")
        url="javascript:"+quote(snippet(self.token,self.created_ms),safe="")
        path.write_text('<!doctype html><meta charset="utf-8"><title>RectoFlow HTML-Auswahl</title>'
            '<h1>Experimentelle HTML-Auswahl</h1><p>Diesen Link in die Lesezeichenleiste ziehen. '
            'Dann im gewaehlten Browserfenster auf das Lesezeichen klicken. Sitzung: 180 Sekunden.</p>'
            '<p><a href="'+html.escape(url,quote=True)+'">RectoFlow Auswahl</a></p>'
            '<p>Bereiche auswaehlen, Ergebnisdatei speichern und in RectoFlow importieren. '
            'F8 entfernt die Auswahl. Bei blockiertem Bookmarklet manuell fortfahren.</p>',encoding="utf-8")
        return path

from PIL import Image, ImageChops
from .geometry import CalibrationError, css_to_screen, measured_mapping, validate_rect


def snippet(token,created_ms=None):
    if not token.isalnum():
        raise ValueError("Invalid session token.")
    created_ms=int(time.time()*1000) if created_ms is None else int(created_ms)
    return Path(__file__).with_suffix(".js").read_text(encoding="utf-8").replace("__SESSION_TOKEN__",token).replace("__SESSION_STARTED__",str(created_ms))


def parse_payload(text, token, now=None):
    if len(text) > 32000:
        raise CalibrationError("DOM_PICKER_FAILED", "DOM-Metadaten sind zu gross.")
    try:
        data = json.loads(text)
        if data["schema"] != 1 or data["token"] != token:
            raise ValueError("Falsche oder alte Picker-Sitzung.")
        now = time.time() if now is None else now
        if not 0 <= now * 1000 - data["created_ms"] <= 180000:
            raise ValueError("DOM-Daten sind abgelaufen.")
        if data["visual_scale"] != 1 or len(data["markers"]) != 3:
            raise ValueError("Pinch-Zoom/Marker nicht unterstuetzt.")
        if len(data["viewport"])!=2 or len(data["scroll"])!=2 or not .25 <= data["dpr"] <= 8:
            raise ValueError("Ungueltige DOM-Skalierung.")
        for v in [data["dpr"], *data["viewport"], *data["scroll"]]:
            if isinstance(v, bool) or not isinstance(v, (int, float)) or not math.isfinite(v):
                raise ValueError("Ungueltige DOM-Koordinaten.")
        if not 180 <= data["viewport"][0] <= 32000 or not 180 <= data["viewport"][1] <= 32000:
            raise ValueError("Ungueltiger Viewport.")
        expected_colors = [[239,17,131],[17,239,131],[131,17,239]]
        expected_centers = [[36,84],[data["viewport"][0]-36,84],[36,data["viewport"][1]-36]]
        for i, marker in enumerate(data["markers"]):
            if marker["color"] != expected_colors[i] or marker["css_center"] != expected_centers[i]:
                raise ValueError("Ungueltige Marker.")
        # Whitelist: kein Seitentext, URL, Cookies, IDs, Klassen oder DOM-Baum.
        rects = {}
        for name in ("LEFT", "RIGHT", "NEXT", "PROGRESS"):
            r = data["rects"].get(name)
            if r is not None:
                values=[r[k] for k in ("left","top","right","bottom","width","height")]
                if any(isinstance(v,bool) or not isinstance(v,(int,float)) or not math.isfinite(v) for v in values) or r["width"]<=0 or r["height"]<=0 or abs(r["right"]-r["left"]-r["width"])>.01 or abs(r["bottom"]-r["top"]-r["height"])>.01:
                    raise ValueError("Ungueltiges DOM-Rechteck.")
                rects[name] = {k:r[k] for k in ("left","top","right","bottom","width","height")}
        return {k:data[k] for k in ("schema","token","created_ms","dpr","viewport","scroll","visual_scale","markers")} | {"rects":rects}
    except (ValueError, TypeError, KeyError, IndexError) as error:
        raise CalibrationError("DOM_PICKER_FAILED", str(error)) from error


def marker_bounds(image, color):
    delta = ImageChops.difference(image.convert("RGB"), Image.new("RGB", image.size, tuple(color)))
    masks = [channel.point(lambda p: 255 if p == 0 else 0) for channel in delta.split()]
    mask = ImageChops.multiply(ImageChops.multiply(masks[0], masks[1]), masks[2])
    return mask.getbbox()


def suggestions(payload, screen, bounds):
    points = []
    for marker in payload["markers"]:
        r = marker_bounds(screen, marker["color"])
        dpr = payload["dpr"]
        if r is None or not (18*dpr-3 <= r[2]-r[0] <= 22*dpr+3 and 18*dpr-3 <= r[3]-r[1] <= 22*dpr+3):
            raise CalibrationError("COORDINATE_TRANSFORM_FAILED", "Sitzungsmarker fehlen oder sind mehrdeutig.")
        validate_rect([r[0],r[1],r[2]-r[0],r[3]-r[1]], bounds)
        points.append([(r[0]+r[2])/2,(r[1]+r[3])/2])
    mapping = measured_mapping([m["css_center"] for m in payload["markers"]], points, payload["dpr"])
    rects = {}
    for name, rect in payload["rects"].items():
        result = css_to_screen(rect, mapping, payload["viewport"])
        validate_rect(result, bounds)
        rects[name] = result
    diagnostic = {k:payload[k] for k in ("dpr","viewport","scroll")}
    diagnostic.update(mapping=list(mapping), css_rects=payload["rects"])
    return rects, diagnostic
