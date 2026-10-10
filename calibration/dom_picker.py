"""Local file transport; single-use sessions, measured browser markers."""
import json
from .geometry import finite_number
from pathlib import Path
import time
import uuid
import threading
import html
import itertools
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
        path.write_text(helper_html(url),encoding="utf-8")
        return path


def helper_html(url):
    code=html.escape(url,quote=True)
    return '''<!doctype html><html lang="de"><meta charset="utf-8">
<title>RectoFlow HTML-Auswahl</title>
<style>body{font:17px system-ui;max-width:900px;margin:32px auto;padding:20px;color:#202634}
button,a{padding:10px}textarea{width:100%;height:130px}aside{background:#eef3ff;padding:16px}</style>
<h1>HTML-Auswahl als Vorschlag</h1>
<aside><strong>Manuell ohne HTML:</strong> Zurueck zu RectoFlow wechseln und
den Button „Manuell ohne HTML“ verwenden. Das funktioniert auch bei blockiertem Bookmarklet.</aside>
<h2>Edge: ohne sichtbare Favoritenleiste</h2>
<ol><li>„Bookmarklet kopieren“ anklicken.</li>
<li>Im Zielbrowser einen Favoriten anlegen. Im Favoritenmenue den Favoriten bearbeiten:
Name „RectoFlow Auswahl“, URL durch den vollstaendigen Code unten ersetzen (einschliesslich javascript:).</li>
<li>Zum Buch-/Zieltab wechseln und „RectoFlow Auswahl“ im Favoritenmenue auswaehlen.
Die Favoritenleiste muss dabei nicht sichtbar sein.</li>
<li>Bereiche auswaehlen, Ergebnisdatei speichern und in RectoFlow „Ergebnis importieren“ anklicken.</li></ol>
<p>Die Sitzung gilt 180 Sekunden ab Erstellung. Bei Ablauf eine neue Hilfsseite starten.
F8 / Abbrechen entfernt den Picker. Kein Code-Einfuegen in DevTools erforderlich.</p>
<button id="copy" type="button">Bookmarklet kopieren</button>
<span id="status" role="status"></span>
<p>Vollstaendiger Bookmarklet-Code (auch manuell auswaehlbar):</p>
<textarea id="code" readonly spellcheck="false">'''+code+'''</textarea>
<p>Optional bei sichtbarer Leiste: <a href="'''+code+'''">RectoFlow Auswahl</a> als Favoriten ablegen.</p>
<p>HTML wird nie automatisch akzeptiert. Danach folgen der normale Region-Editor,
Live-Vorschau und ausdrueckliche Bestaetigung.</p>
<script>
document.getElementById('copy').addEventListener('click', async function () {
  const code = document.getElementById('code');
  const status = document.getElementById('status');
  try {
    if (navigator.clipboard && navigator.clipboard.writeText) {
      await navigator.clipboard.writeText(code.value);
    } else {
      code.focus(); code.select();
      if (!document.execCommand('copy')) throw new Error('copy blocked');
    }
    status.textContent = 'Kopiert. Jetzt den Favoriten bearbeiten.';
  } catch (_) {
    code.focus(); code.select();
    status.textContent = 'Automatisches Kopieren blockiert. Markierten Code mit Strg+C kopieren.';
  }
});
</script></html>'''

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
        if type(data["schema"]) is not int or data["schema"] not in (1,2) or data["token"] != token:
            raise ValueError("Falsche oder alte Picker-Sitzung.")
        now = time.time() if now is None else now
        if not 0 <= now * 1000 - data["created_ms"] <= 180000:
            raise ValueError("DOM-Daten sind abgelaufen.")
        if not finite_number(data["visual_scale"]) or data["visual_scale"] != 1 or len(data["markers"]) != 3:
            raise ValueError("Pinch-Zoom/Marker nicht unterstuetzt.")
        if len(data["viewport"])!=2 or len(data["scroll"])!=2 or not .25 <= data["dpr"] <= 8:
            raise ValueError("Ungueltige DOM-Skalierung.")
        for v in [data["dpr"], *data["viewport"], *data["scroll"]]:
            if not finite_number(v):
                raise ValueError("Ungueltige DOM-Koordinaten.")
        if not 180 <= data["viewport"][0] <= 32000 or not 180 <= data["viewport"][1] <= 32000:
            raise ValueError("Ungueltiger Viewport.")
        expected_colors = [[239,17,131],[17,239,131],[131,17,239]]
        expected_centers = [[36,84],[data["viewport"][0]-36,84],[36,data["viewport"][1]-36]]
        for i, marker in enumerate(data["markers"]):
            if marker["color"] != expected_colors[i] or marker["css_center"] != expected_centers[i]:
                raise ValueError("Ungueltige Marker.")
        # Whitelist: kein Seitentext, URL, Cookies, IDs, Klassen oder DOM-Baum.
        if not isinstance(data["rects"],dict):raise ValueError("Ungueltige DOM-Rechtecke.")
        rects = {}
        candidates=data.get("candidates",[]) if data["schema"]==2 else []
        if not isinstance(candidates,list) or len(candidates)>64:
            raise ValueError("Zu viele oder ungueltige Seitenkandidaten.")
        inputs={f"PAGE_CANDIDATE_{i}":r for i,r in enumerate(candidates,1)}
        inputs.update({name:data["rects"].get(name) for name in (("LEFT","RIGHT","NEXT","PROGRESS") if data["schema"]==1 else ("NEXT","PROGRESS"))})
        for name,r in inputs.items():
            if r is not None:
                values=[r[k] for k in ("left","top","right","bottom","width","height")]
                if any(not finite_number(v) for v in values) or r["width"]<=0 or r["height"]<=0 or abs(r["right"]-r["left"]-r["width"])>.01 or abs(r["bottom"]-r["top"]-r["height"])>.01:
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


def marker_candidates(image, color, dpr, bounds):
    """Narrow RGB distance + solid connected squares, never a union of clusters.

    The original size limits and measured_mapping scale/alignment limits remain.
    Eight channel levels cover small screenshot color rounding, not arbitrary hues.
    """
    delta=ImageChops.difference(image.convert("RGB"),Image.new("RGB",image.size,tuple(color)))
    masks=[channel.point(lambda p:255 if p<=8 else 0) for channel in delta.split()]
    mask=ImageChops.multiply(ImageChops.multiply(masks[0],masks[1]),masks[2])
    pixels=bytearray(mask.tobytes());width,height=image.size
    result=[];start=0
    while True:
        start=pixels.find(255,start)
        if start<0:break
        stack=[start];pixels[start]=0;left=right=start%width;top=bottom=start//width;area=0
        while stack:
            pos=stack.pop();x,y=pos%width,pos//width;area+=1
            left=min(left,x);right=max(right,x);top=min(top,y);bottom=max(bottom,y)
            for neighbor in ((pos-1 if x else -1),(pos+1 if x+1<width else -1),
                             (pos-width if y else -1),(pos+width if y+1<height else -1)):
                if neighbor>=0 and pixels[neighbor]:pixels[neighbor]=0;stack.append(neighbor)
        w,h=right-left+1,bottom-top+1
        if (18*dpr-3<=w<=22*dpr+3 and 18*dpr-3<=h<=22*dpr+3 and area>=.9*w*h
                and bounds[0]<=left and bounds[1]<=top and right+1<=bounds[2] and bottom+1<=bounds[3]):
            result.append((left,top,right+1,bottom+1))
            if len(result)>16:
                raise CalibrationError("COORDINATE_TRANSFORM_FAILED","Zu viele plausible Marker; neue HTML-Sitzung oder manuell auswaehlen.")
    return result


def suggestions(payload, screen, bounds):
    candidates=[marker_candidates(screen,m["color"],payload["dpr"],bounds) for m in payload["markers"]]
    mappings=[]
    for triple in itertools.product(*candidates):
        points=[[(r[0]+r[2])/2,(r[1]+r[3])/2] for r in triple]
        try:
            mapping=measured_mapping([m["css_center"] for m in payload["markers"]],points,payload["dpr"])
            sx,sy,ox,oy=mapping
            # The whole measured DOM viewport must fit the selected screen area.
            if ox<bounds[0]-2 or oy<bounds[1]-2 or ox+sx*payload["viewport"][0]>bounds[2]+2 or oy+sy*payload["viewport"][1]>bounds[3]+2:continue
            mappings.append(mapping)
        except CalibrationError:continue
    if len(mappings)!=1:
        raise CalibrationError("COORDINATE_TRANSFORM_FAILED", "Sitzungsmarker fehlen oder sind geometrisch mehrdeutig. HTML erneut versuchen oder manuell fortfahren.")
    mapping=mappings[0]
    rects = {}
    for name, rect in payload["rects"].items():
        result = css_to_screen(rect, mapping, payload["viewport"])
        validate_rect(result, bounds)
        rects[name] = result
    if not any(name.startswith("PAGE_CANDIDATE_") or name in ("LEFT","RIGHT") for name in rects):
        raise CalibrationError("DOM_PICKER_FAILED","Keine sichtbaren Seitenkandidaten. HTML erneut versuchen oder manuell fortfahren.")
    diagnostic = {k:payload[k] for k in ("dpr","viewport","scroll")}
    diagnostic.update(mapping=list(mapping), css_rects=payload["rects"])
    return rects, diagnostic
