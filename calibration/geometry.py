"""Pure Geometrie: CSS, Screen und UI-Canvas bleiben getrennte Raeume."""
import math


def finite_number(value):
    """Only numbers representable as finite runtime floats; never raise on JSON ints."""
    if isinstance(value,bool) or not isinstance(value,(int,float)):return False
    try:return math.isfinite(value)
    except (OverflowError,ValueError):return False

PAPER_MM = {"A0": (841,1189), "A1": (594,841), "A2": (420,594), "A3": (297,420), "A4": (210,297), "A5": (148,210), "A6": (105,148), "Letter": (215.9,279.4), "Legal": (215.9,355.6)}


def paper_ratio(paper, orientation):
    if paper == "Original":
        return None
    if paper not in PAPER_MM or orientation not in ("portrait", "landscape"):
        raise CalibrationError("INVALID_RECTANGLE", "Ungueltiges Papierformat.")
    w, h = PAPER_MM[paper]
    return w / h if orientation == "portrait" else h / w


def fit_aspect(rect, ratio, bounds):
    """Groesste passende Papierbox innerhalb der gegebenen Box, Mittelpunkt bleibt."""
    if ratio is None:
        return list(rect)
    x, y, w, h = rect
    validate_rect(rect,bounds)
    # Ein physischer Pixel ist unteilbar. Beide moeglichen gerundeten
    # Achsenpaare gelten als passend; sonst kann erneutes Einpassen
    # abwechselnd Breite und Hoehe um einen Pixel verkleinern.
    if abs(w-h*ratio)<=.5+1e-9 or abs(h-w/ratio)<=.5+1e-9:
        return list(rect)
    if w / h > ratio:
        ww, hh = max(1, round(h * ratio)), h
    else:
        ww, hh = w, max(1, round(w / ratio))
    result = [x + (w - ww) // 2, y + (h - hh) // 2, ww, hh]
    validate_rect(result, bounds)
    return result


def resize_aspect(rect,handle,dx,dy,bounds,ratio):
    """Papierseitenverhaeltnis auch beim Ziehen einzelner Seiten vergroessern.

    Gegenueberliegende Seite/Ecke bleibt verankert; die andere Achse waechst
    um den Mittelpunkt. Skalierung wird an den Bildschirmgrenzen begrenzt.
    """
    if ratio is None:
        return resize_rect(rect,handle,dx,dy,bounds)
    x,y,w,h=rect
    l,t,r,b=bounds
    cx,cy=x+w/2,y+h/2
    rw=w+(dx if "e" in handle else -dx if "w" in handle else 0)
    rh=h+(dy if "s" in handle else -dy if "n" in handle else 0)
    horizontal="e" in handle or "w" in handle
    vertical="n" in handle or "s" in handle
    wanted=rw if horizontal and (not vertical or abs(rw/w-1)>=abs(rh/h-1)) else rh*ratio
    maxw=r-x if "e" in handle else x+w-l if "w" in handle else 2*min(cx-l,r-cx)
    maxh=b-y if "s" in handle else y+h-t if "n" in handle else 2*min(cy-t,b-cy)
    ww=max(1,min(math.floor(maxw),round(min(max(1,wanted),maxw,maxh*ratio))))
    hh=max(1,min(math.floor(maxh),round(ww/ratio)))
    xx=x if "e" in handle else x+w-ww if "w" in handle else round(cx-ww/2)
    yy=y if "s" in handle else y+h-hh if "n" in handle else round(cy-hh/2)
    result=[max(l,min(r-ww,xx)),max(t,min(b-hh,yy)),ww,hh]
    validate_rect(result,bounds)
    return result


class CalibrationError(RuntimeError):
    def __init__(self, code, message):
        self.code = code
        super().__init__(f"{code}: {message}")


def right_rect(cfg):
    if "right_rect" in cfg:
        return cfg["right_rect"]
    x, y, w, h = cfg["left_rect"]
    return [x + w, y, w, h]


def center(rect):
    x, y, w, h = rect
    return [x + w // 2, y + h // 2]


def contains(rect, point):
    x, y, w, h = rect
    return x <= point[0] < x + w and y <= point[1] < y + h


def validate_rect(rect, bounds):
    if not isinstance(rect, (list, tuple)) or len(rect) != 4 or any(type(v) is not int for v in rect):
        raise CalibrationError("INVALID_RECTANGLE", "[x,y,Breite,Hoehe] muss vier ganze Zahlen enthalten.")
    x, y, w, h = rect
    l, t, r, b = bounds
    if min(w, h) <= 0 or x < l or y < t or x + w > r or y + h > b:
        raise CalibrationError("INVALID_RECTANGLE", "Rechteck ausserhalb des Zielbereichs oder ohne Flaeche.")


def overlap(a, b):
    x = max(0, min(a[0] + a[2], b[0] + b[2]) - max(a[0], b[0]))
    y = max(0, min(a[1] + a[3], b[1] + b[3]) - max(a[1], b[1]))
    return x * y / min(a[2] * a[3], b[2] * b[3])


def validate_selection(rects, point, bounds, navigation_mode="next_button"):
    from .regions import capture_names, NAVIGATION
    names=capture_names(rects)
    if not names or navigation_mode not in NAVIGATION:
        raise CalibrationError("INVALID_RECTANGLE", "Mindestens einen Bereich und gueltige Navigation waehlen.")
    if "LEFT" in names or "RIGHT" in names:
        names=["LEFT","RIGHT"]  # legacy selections require the original pair
    for name in names + (["NEXT"] if navigation_mode=="next_button" else []):
        if rects.get(name) is None:
            raise CalibrationError("INVALID_RECTANGLE", f"{name} fehlt.")
    for rect in rects.values():
        if rect is not None:
            validate_rect(rect, bounds)
    captures=[rects[name] for name in names]
    if len({tuple(r) for r in captures}) != len(captures):
        raise CalibrationError("INVALID_RECTANGLE", "Aufnahmebereiche sind identisch.")
    if navigation_mode!="next_button":
        return any(overlap(a,b)>=.3 for i,a in enumerate(captures) for b in captures[i+1:])
    if min(rects["NEXT"][2:]) < 5:
        raise CalibrationError("INVALID_RECTANGLE", "NEXT muss mindestens 5 x 5 Pixel gross sein.")
    if not isinstance(point, (list, tuple)) or len(point) != 2 or any(type(v) is not int for v in point) or not contains(rects["NEXT"], point):
        raise CalibrationError("INVALID_RECTANGLE", "Klickpunkt muss innerhalb NEXT liegen.")
    return any(overlap(a,b)>=.3 for i,a in enumerate(captures) for b in captures[i+1:])


def move_rect(rect, dx, dy, bounds):
    x, y, w, h = rect
    l, t, r, b = bounds
    return [max(l, min(r - w, x + dx)), max(t, min(b - h, y + dy)), w, h]


def resize_rect(rect, handle, dx, dy, bounds):
    x, y, w, h = rect
    l, t, r, b = bounds
    rr, bb = x + w, y + h
    if "w" in handle:
        x = max(l, min(rr - 1, x + dx))
    if "e" in handle:
        rr = min(r, max(x + 1, rr + dx))
    if "n" in handle:
        y = max(t, min(bb - 1, y + dy))
    if "s" in handle:
        bb = min(b, max(y + 1, bb + dy))
    return [x, y, rr - x, bb - y]


def new_rect(a, b, bounds):
    l, t, r, bb = bounds
    ax, ay = max(l, min(r - 1, a[0])), max(t, min(bb - 1, a[1]))
    bx, by = max(l, min(r, b[0])), max(t, min(bb, b[1]))
    return [min(ax, bx), min(ay, by), max(1, abs(ax - bx)), max(1, abs(ay - by))]


def align_rect(rect,reference,operation,bounds,gap=0):
    if type(gap) is not int or gap<0:
        raise CalibrationError("INVALID_RECTANGLE","Abstand muss eine nichtnegative ganze Pixelzahl sein.")
    result=list(rect)
    if operation=="left":result[0]=reference[0]
    elif operation=="top":result[1]=reference[1]
    elif operation=="size":result[2:]=reference[2:]
    elif operation=="right":result[:2]=[reference[0]+reference[2]+gap,reference[1]]
    else:raise CalibrationError("INVALID_RECTANGLE","Unbekannte Geometrieaktion.")
    validate_rect(result,bounds)
    return result


def canvas_transform(image_size, canvas_size):
    scale = min(canvas_size[0] / image_size[0], canvas_size[1] / image_size[1])
    return scale, (canvas_size[0] - image_size[0] * scale) / 2, (canvas_size[1] - image_size[1] * scale) / 2


def to_screen(point, transform):
    scale, ox, oy = transform
    return [round((point[0] - ox) / scale), round((point[1] - oy) / scale)]


def measured_mapping(css_centers, screen_centers, dpr):
    """Drei sichtbar gemessene Marker: Browser-Chrome-Offset nie erraten."""
    if not finite_number(dpr) or not 0.25 <= dpr <= 8:
        raise CalibrationError("COORDINATE_TRANSFORM_FAILED", "Ungueltiges devicePixelRatio.")
    try:
        sx = (screen_centers[1][0] - screen_centers[0][0]) / (css_centers[1][0] - css_centers[0][0])
        sy = (screen_centers[2][1] - screen_centers[0][1]) / (css_centers[2][1] - css_centers[0][1])
        ox = screen_centers[0][0] - sx * css_centers[0][0]
        oy = screen_centers[0][1] - sy * css_centers[0][1]
    except (ZeroDivisionError, IndexError, TypeError, OverflowError):
        raise CalibrationError("COORDINATE_TRANSFORM_FAILED", "Marker-Geometrie ist ungueltig.")
    if not all(finite_number(v) for v in (sx, sy, ox, oy)) or sx<=0 or sy<=0 or abs(sx / dpr - 1) > .025 or abs(sy / dpr - 1) > .025 or abs(sx / sy - 1) > .025:
        raise CalibrationError("COORDINATE_TRANSFORM_FAILED", "Gemessene Skalierung passt nicht zu DPR.")
    for css, screen in zip(css_centers, screen_centers):
        if abs(ox + sx * css[0] - screen[0]) > 2 or abs(oy + sy * css[1] - screen[1]) > 2:
            raise CalibrationError("COORDINATE_TRANSFORM_FAILED", "Marker sind nicht konsistent ausgerichtet.")
    return sx, sy, ox, oy


def css_to_screen(rect, mapping, viewport):
    sx, sy, ox, oy = mapping
    values = [rect[k] for k in ("left", "top", "width", "height")]
    if any(not finite_number(v) for v in values):
        raise CalibrationError("COORDINATE_TRANSFORM_FAILED", "DOM-Rechteck ist ungueltig.")
    x, y, w, h = values
    if w <= 0 or h <= 0:
        raise CalibrationError("COORDINATE_TRANSFORM_FAILED", "DOM-Rechteck hat keine Flaeche.")
    # Nur der sichtbare Teil ist ein brauchbarer Screenshot-Vorschlag.
    l, t = max(0, x), max(0, y)
    r, b = min(viewport[0], x + w), min(viewport[1], y + h)
    if r <= l or b <= t:
        raise CalibrationError("COORDINATE_TRANSFORM_FAILED", "DOM-Auswahl liegt ausserhalb des Viewports.")
    left, top = math.floor(ox + sx * l), math.floor(oy + sy * t)
    right, bottom = math.ceil(ox + sx * r), math.ceil(oy + sy * b)
    return [left, top, right - left, bottom - top]
def assert_same_selection(confirmed,current,rects):
    """Die bestaetigten ausgewaehlten Pixel binden auch den ersten Capture."""
    from PIL import ImageChops
    if confirmed.size!=current.size:
        raise CalibrationError("SCREENSHOT_FAILED","Bildgroesse seit der Kontrollvorschau geaendert.")
    for rect in rects.values():
        if rect:
            x,y,w,h=rect
            crop=(x,y,x+w,y+h)
            if ImageChops.difference(confirmed.crop(crop),current.crop(crop)).getbbox() is not None:
                raise CalibrationError("SCREENSHOT_FAILED","Zielbild hat sich seit der Kontrollvorschau geaendert. Neu kontrollieren/kalibrieren.")
