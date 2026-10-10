# Builder: Attempt-Ledger und Fehlergrenzen

Vorheriger Subject: `ce81efbababe08ca56e9f322b22e4c81efefd817`, Tree
`52f88e42a14b89bac4779f1f1f58040bddcf4e65`. Historisch, keine übertragene Evidence.
Gate: sauberer kanonischer Checkout auf `fix/v021-capture-start-diagnostics`;
origin/public branch identisch, main bei `05ae40615a5b62227857e3477cfd484a116f3a5a`.

## Anforderung und kleinster zusammenhängender Slice

Ein früher Diagnose-Attempt muss den vollständigen Weg von Launcher/Action über
Config, Target, vorhandene Confirmation, Full Frame, Run-Publikation, Crops,
Manifest, Button, genau einen Klick, View-Transition und Export erklären können.
Die Änderung instrumentiert die existierenden Grenzen und klassifiziert ihre
Fehler. Sie ändert weder die Guards noch Capture-Geometrie, Layout-Policy,
Navigationstoleranzen oder den produktiven Screenshot-Backend.

## Globaler Wirkungspfad / Boundary Audit

| Grenze | Produzent → Verbraucher / Quelle | Fehler, Transaktion, Wiederanlauf |
|---|---|---|
| Workflow-Einstieg | Launcher/Core → Diagnostic schema 1 | UUID-Attempt vor Config. Frühe Fehler behalten Journal/Summary. Temp-Fallback; Protokollfehler verdecken den Core-Fehler nicht. |
| Journal | Boundary → append-only events.jsonl | Ein Event je Grenze, flush/fsync. Journal ist Crash-Quelle; atomare attempt.json/SUMMARY-Snapshots können bei Abbruch zwischen Writes nachlaufen. Kein Resume, keine vorgetäuschte Completion. |
| Target | Windows-Auswahl/Live-HWND → bestehende Bindings/Guards | Gleiche Identitäts-, Prozess-, EXE-, DPI-, Monitor-, Bounds-, Fokus-, Titel- und WindowFromPoint-Prüfungen. Spezifischer Code plus technischer Guard-Name, keine privaten Titel. |
| Screenshot | Vor-Guard → Pillow ImageGrab → private Persistenz → Nach-Guard | Einmaliger erster Frame, physische Pixel, atomarer PNG-Replace, SHA-256/Dimensionen/Zeit. A: Guard vor Grab, B: Acquire-Exception, C: Nach-Guard bei vorhandenem PNG, D: Persist-Failure. |
| Calibration | HTML-Vorschlag / Editor → Live-Confirmation → Config-Transaction | Alte Single/Double/Profile/Backup-Verträge unverändert. Pixelgleichheit weiterhin exakt, kein zusätzlicher Legacy-Pflichtdialog. Kandidatenvalidierung nach Editor, damit noch unkalibrierte Configs bearbeitbar bleiben. |
| Run | vorhandene erfolgreiche Confirmation → versteckte Stage → initiales atomisches RUNNING Manifest → Rename | Erst danach normaler run_*. Fehler lassen nur private Stage zurück. Initiales Stage-Manifest und publiziertes Manifest getrennt. Bestehende Runs bleiben erhalten. |
| Capture | geordnete aktive Slots → Crops → Manifest-Append | Slot, Datei, Hash, Dimensionen; Crop- und Append-Fehler getrennt. Sparse-/Last-/Override-Verträge bleiben schema 4; Reihenfolge bleibt die geordnete Region-Liste. |
| Navigation | Button-Vorbereitung/State → Preclick-Guard → SendInput → View-Aggregate | Unknown bleibt Unknown, nie Ende. Zwei Input-Events, bei Teilannahme nur LEFTUP-Cleanup. Kein automatischer Wiederholungsklick. Polling bleibt im RAM, keine Journalzeile pro Frame. |
| Export | eingefrorenes Manifest/ExportPlan/PNG-Hashes → PDF/result.json | Separate atomare Ergebnisse, unveränderte Capture-Dateien. Partial-Capture-Export kann gelingen, während Workflow Exit 2 bleibt. Ursprüngliche technische Ursache bleibt primär. |
| GUI / CLI | Diagnostic → zentraler Dialog / ursprüngliche Exitcodes | Technical + Cancel behält Ursache, USER_CANCELLED ist terminal. Pure Cancel 2 ohne Crash-Dialog. Erfolgreicher Fallback 0 mit Warning-History. Keine doppelten Launcher/Entrypoint-Dialoge. |
| Packaging | sauberer Subject → erlaubte Ressourcen → ZIP | Allowlist, keine Runtime-Daten, expliziter Reject für private Frames in Ressourcenbäumen. CI uploadt ausschließlich die portable ZIP. Native Spike-Pixel bleiben lokal/ignoriert. |

## Fehlervertrag

`failure_code` ist die stabile Diagnoseklassifikation. Bestehende öffentliche
Exception-Verträge bleiben kompatibel: OSError/ValueError-Unterklassen und
StopRun; CalibrationError.code behält bei Screenshotfehlern SCREENSHOT_FAILED,
während die Diagnose die präzise neue Klassifikation enthält. Originalursachen
werden verkettet, Stack enthält Dateiname/Zeile/Funktion ohne Quelltext/Locals.
KeyboardInterrupt bleibt KeyboardInterrupt für den bestehenden Export-Cancel-
Vertrag. Die Diagnose führt primary_failure, history, terminal_outcome, exit_code,
last_successful_checkpoint und failed_checkpoint. Der Dialog zeigt den Schritt
vor der Primärursache, auch wenn später noch ein Teil-PDF exportiert wird.

Codes: CFG_LOAD_FAILED / CFG_INVALID; TARGET_SELECTION_FAILED / TARGET_BIND_FAILED /
TARGET_CHANGED / TARGET_FOCUS_LOST / TARGET_OCCLUDED / TARGET_ENVIRONMENT_CHANGED;
CONFIRMATION_FAILED / USER_CANCELLED; SCREENSHOT_ACQUIRE_FAILED /
SCREENSHOT_DIMENSION_MISMATCH / SCREENSHOT_PERSIST_FAILED; PIXEL_GUARD_FAILED /
SELECTION_GUARD_FAILED; BUTTON_PREPARE_FAILED / BUTTON_STATE_UNKNOWN /
BUTTON_DISABLED; NAVIGATION_PRECLICK_GUARD_FAILED / NAVIGATION_CLICK_FAILED /
VIEW_TRANSITION_TIMEOUT / VIEW_CHANGE_NOT_DETECTED / VIEW_NOT_STABLE;
RUN_CREATE_FAILED / MANIFEST_WRITE_FAILED / RUN_PUBLISH_FAILED;
CAPTURE_CROP_FAILED / CAPTURE_MANIFEST_APPEND_FAILED / EXPORT_FAILED.
Vorzeitiges manuelles Ende und ein weiterhin aktives Next am Ansichtslimit werden
zusätzlich als CAPTURE_INCOMPLETE bzw. CAPTURE_LIMIT_REACHED klassifiziert.

## Was könnte trotz grünem Builder still scheitern?

Die gefährlichste Annahme wäre, API-Erfolg als korrektes Browserbild zu behandeln.
Der HWND-Spike widerlegt genau diese Annahme: PrintWindow kann erfolgreich
zurückkehren und schwarze bzw. fehlende Content-Flächen liefern. Deshalb bleibt
ImageGrab; siehe [WINDOW_CAPTURE_SPIKE.md](WINDOW_CAPTURE_SPIKE.md).

Weitere Grenzen: echte Klett-Compositor-/DOM-/UIA-Zustände und physische DPI/Zoom-
Kombinationen bleiben Owner-Scope. Plötzlicher Stromausfall ist stärker als die
getesteten os._exit-Abbrüche. Bei vollständig ausgefallenem lokalen Storage kann
auch die Diagnose nicht dauerhaft geschrieben werden; die ursprüngliche Exception
und der Dialog dürfen trotzdem nicht ersetzt werden. First-frame-Speicherfehler
werden ausdrücklich als SCREENSHOT_PERSIST_FAILED klassifiziert.

Keine OCR/Ingestion-, Steward-, Pause/Override- oder Orchestrierungsphase gebaut.
Die bestehenden reinen Slot-Resolver, replacebare Windows-Adapter und expliziten
Boundary-Funktionen bleiben anschlussfähig. Nach Neustart entsteht eine neue UUID;
abgebrochene Runs werden nicht automatisch fortgesetzt.

## Verifikation und Autoritätsgrenze

Neue Failure-Injection-Tests prüfen Startup, Confirmation, Pre-/Post-Screenshot,
Persistenz, Stage/Manifest/Publish, beide Crop-Slots, Append, Button und Navigation
sowie vier echte Prozessabbrüche. Die vollständige Suite, native Tk-Smokes,
Windows CI und genau das ausgelieferte relocierte Owner-ZIP werden erst nach
Commit auf den finalen Subject gebunden. Details im ignorierten SHA-Verzeichnis
unter `.build-v021/evidence/<subject>/`. Tests werden nicht entfernt/abgeschwächt.

Builder-Evidence ist keine unabhängige Review oder Owner Acceptance. Fachlicher
nächster Schritt: OWNER_RETEST_REQUIRED; Autoritätsstatus höchstens
INDEPENDENT_REVIEW_PENDING. Kein Fresh Breaker, Merge, Release oder Tag.
