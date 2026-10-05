"""DOM-Daten aus lokaler Zwischenablage; Marker statt erfundener Chrome-Offsets."""
import json
import math
from pathlib import Path
import time

from PIL import Image, ImageChops
from .geometry import CalibrationError, css_to_screen, measured_mapping, validate_rect


def snippet(token):
    return Path(__file__).with_suffix(".js").read_text(encoding="utf-8").replace("__SESSION_TOKEN__", token)


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
