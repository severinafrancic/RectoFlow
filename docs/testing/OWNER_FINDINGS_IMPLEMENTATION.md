# Builder: Wirkung und Grenzen der Owner-Finding-Fixes

Historischer Owner-Subject: `cf35c771d652480f162f46cbc7cc0e04cbf24352`.
Die realen Findings invalidieren dessen Finalität. Keine frühere Browser-/CI-/
Breaker-Evidence wird als Beleg des neuen Subjects verwendet.

## Anforderungen und Quellen

Owner bestätigt: Single-Page-Problem, fehlende/mehrdeutige Sitzungsmarker,
HTML-Fallback → Cancel → Exit 2, unzureichende Mauspräzision. Vorgabe:
explizite Slot-Policy, geordnete beliebig viele DOM-Kandidaten, sichere gemessene
Transformation, kausale Diagnosen, Keyboard/Tab und persistenter Magnifier.
Ausnahmen werden vor Capture nach Ansichtsnummer gespeichert; keine Laufdialoge.

## Globaler Wirkungspfad / Boundary Audit

| Grenze | Produzent → Verbraucher / Autorität | Fehler- und Restart-Verhalten |
|---|---|---|
| DOM schema 2 | Bookmarklet → Single-use DOMSession → gemessene Marker → Editor | Token/180 s/DPR/Viewport geprüft; kein Seitentext. Retry neue Sitzung, unsicheres Mapping bleibt Vorschlag ohne Geometrie. |
| Calibration | Editor → Live-Kontrolle → Config-Transaction | Physische Pixel, Fenster/Fokus/DPI/Binding unverändert strikt. Hash-Konflikt stoppt; Backup/atomarer Replace; keine Auto-Acceptance. |
| Slot-Policy schema 1 | Optionaler Launcher-Dialog → Config/Profile-Snapshot → reiner View-Resolver | Standard alle Slots; Masken nicht leer, eindeutige ordinale Reihenfolge. Overrides vorab; spätere explizite Pause-Adaption kann denselben Resolver nutzen. |
| Capture schema 4 | Stabile bestätigte Ansicht + terminaler Zustand → aktive Crops → Manifest | Nur echte Slots publiziert. Unbekanntes manuelles Ende puffert aktuelle Ansicht im RAM. Bei Abbruch kein geratenes Last, kein Resume. |
| Export | Eingefrorenes Manifest → hashgebundener ExportPlan → einmal gelesene/verifizierte PNG-Bytes → PDF | Slot/Dateiname/Größe/Hash/Reihenfolge geprüft; originale PNGs/Manifest bleiben unverändert. Schema 1–3 weiterhin lesbar. |
| Diagnostics | technische Ereignisse + Benutzerentscheidungen → History/Primärursache/terminal outcome → zentraler GUI-Dialog | Exit 2 unverändert bei nicht abgeschlossenem Workflow. Erfolgreicher Fallback Exit 0, Warning bleibt. Logfehler verdecken Original nicht. |
| Packaging | sauberer Git-Subject → Builder + Windows-CI → eigener SHA-Unterordner | Keine historischen Pakete überschrieben; Evidence und Binärhashes erst für exakt denselben Subject gültig. |

Reihenfolge hängt bewusst an der geordneten Region-Liste. Policy-Slots sind deren
sichtbare Nummern, keine dauerhaften Region-IDs. Reorder ändert die Slot-Reihenfolge,
keine Geometrie. Bei Count-Änderung wird eine vorhandene Policy explizit neu bestätigt.
Alte Single-/Double-/Multi-Configs ohne Policy behalten Schema 3 und alle Slots.
Ein Export mit Schema 4 wird von älteren Lesern bewusst abgewiesen statt falsch
als vollständiges Seitenpaar interpretiert. Rollback benötigt ursprüngliche Config/
Backup; Schema 4 mit dieser Version exportieren. Keine Ingestion-/OCR-Erweiterung.

## Root Causes und direkte Fixes

- **Single Page:** Vier feste DOM-Schritte LEFT/RIGHT/NEXT/PROGRESS und Vorschläge
  in bestehende zwei Slots verhinderten tatsächliche Candidate-Anzahl. Schema 2
  sammelt Seiten explizit geordnet, danach NEXT/PROGRESS. 1/2/>2 → normaler Editor.
- **Marker:** Der rechte obere Marker lag im Panel-Bereich, hatte aber keinen
  Z-Index oberhalb des Panels (Panel 3). Das ist eine reproduzierbare Quelle für
  fehlende Marker im Code. Marker liegen nun bei 5. Zusätzlich bildete exaktes RGB
  eine globale Bounding Box über getrennte Farbcluster. Nun enge Kanalabweichung
  ≤8, zusammenhängende zu ≥90 % gefüllte Quadrate in bestehenden Größenlimits;
  genau eine konsistente Dreierzuordnung. Mehrere plausible Transformationen werden
  weiterhin abgewiesen. Gemessene Scale-/Ausrichtungsgrenzen bleiben unverändert.
  Die exakte Ursache des ursprünglichen realen Screenshots ist ohne seine Pixel
  nicht bewiesen; Klett/Edge-Retest bleibt erforderlich.
- **Koordinaten:** `getBoundingClientRect` ist viewportbezogen; Scroll wird nicht
  nochmals addiert. Gemessene Marker bestimmen Content-Origin inklusive Browser-
  Chrome und physische Skalierung. DPR 1/1.25/1.5/2 sowie 1.875 (kombinierter Zoom)
  sind getestet; Pinch-Zoom wird weiterhin abgewiesen. Cross-origin iframe-Inhalte
  und innere Canvas-Seiten können nicht aus fremdem DOM ausgelesen werden: Host
  höchstens Vorschlag, manuelles präzises Editieren bleibt nötig.
- **Blank Pages:** Bisher wurde jeder kalibrierte Slot jeder Ansicht gespeichert.
  Der explizite Resolver wählt First/Middle/Last/Override, Last vor First bei einer
  Ansicht, Override vor allen. Keine heuristische Blank-Erkennung. Unsicheres Ende
  bleibt Stop, nie Last-Erfolg. PDF „spread“ verbindet nur aktivierte Seiten.
- **Cancel verdeckt Fehler:** HTML-Fehler wurde nur gedruckt und gezeigt; der
  spätere Cancel wurde zum einzigen Diagnosefehler. History und Primärursache sind
  jetzt von terminalem Ergebnis/Exitcode getrennt. Freiwilliges ESC, Maus-Failsafe
  und Calibration-Cancel sind explizit klassifiziert; technische Guards bleiben Fehler.
- **Editor:** Ein per Maus getroffener Griff konnte bereits per Pfeil verändert
  werden, aber es fehlte eine sichere Tastaturauswahl. Tab/Shift+Tab und Handle-
  Auswahlfeld geben deterministische Kontrolle, 12-px-Griffe/24-px-Hitboxes mit
  Corner-Priority unterstützen die Maus. Magnifier bleibt während aktiver Handles
  und aktualisiert sich nach Keyboard-Schritten. Direktfelder sind optional und
  nicht ergänzt; Undo/Redo bleibt editorlokal.

## Builder Assumption Challenge / offene Beweise

Die gefährlichste stille Annahme wäre eine falsch als terminal erkannte View oder
eine plausible, aber falsche Markerzuordnung. Guards/Timeout/Limits bleiben streng;
mehrere vollständige Marker-Dreiecke werden abgewiesen. Eine inaktive Region ist
weiter an die bestätigten Pixel gebunden. Schema 4 prüft auch Slot/Policy-Provenienz,
PNG-Größe/Hash/Name und echte PDF-Pixel. Bei Prozessende während manuellem RAM-Puffer
wird die aktuelle, noch nicht finalisierte View nicht als Seite publiziert; vorherige
Ansichten bleiben verifizierbar. Kein automatischer Retry von Next-Klicks.

Tests simulieren OS-/Browser-Grenzen; native Tk und Frozen-EXE prüfen die reale
Windows-Komposition. Der reale Edge-/Klett-Flow, Browserzoom/Viewer-Struktur und
Owner-Bedienbarkeit bleiben ausschließlich durch A–G im Retest zu belegen.
Kein unabhängiger Review wurde ausgeführt oder beansprucht.
