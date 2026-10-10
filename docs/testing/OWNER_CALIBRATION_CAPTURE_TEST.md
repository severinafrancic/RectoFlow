# RectoFlow: gemeinsamer Owner-Test unter Windows

Dieses unveröffentlichte Paket enthält Capture-Start, Diagnostik, Region-Editor
und HTML-Picker gemeinsam. Kein Release und keine unabhängige Abnahme.
Subject SHA und Tree stehen in `BUILD_METADATA.json` neben der EXE.

ZIP vollständig in einen beschreibbaren lokalen Ordner entpacken. Die EXE braucht
den gesamten Ordner inklusive `_internal`; nicht nur die EXE verschieben.
Vorhandene Profile/Configs vor dem Test sichern und anschließend bewusst auswählen.
Neue Pakete in einen neuen Ordner entpacken, damit alte Testdaten erkennbar bleiben.

Edge auf der Hauptanzeige verwenden. Während Kalibrierung und Aufnahme Fenster,
Monitor, DPI, Browserzoom und Seitenleisten unverändert lassen. Bei Kalibrierung
arbeitet der Editor mit einem eingefrorenen Screenshot in physischen Pixeln.
Die finale Live-Kontrolle bleibt verpflichtend, wo sie schon bisher verlangt wurde.
Alte Configs ohne bisherige Capture-Bestätigung erhalten keinen neuen Pflichtdialog.

## Test A — manueller Picker

1. „Bereiche kalibrieren“ und das passende Edge-Fenster auswählen.
2. „Manuell ohne HTML“ anklicken. Region in Liste auswählen oder „+ Bereich“
   wählen und ein Rechteck aufziehen.
3. Beim Aufziehen und beim Ziehen jeder Ecke/Kante den 8×-Magnifier prüfen:
   harte Pixel, Crosshair, X/Y und Handle-Bezeichnung. Am Rand muss er ausweichen.
4. „Groesse fixieren“ aktivieren. Breite und Höhe aus dem Rechtecklabel notieren.
5. Rechteck ziehen, auch bis an die Bounds. Breite/Höhe müssen exakt gleich bleiben;
   Handles und „Neu aufziehen“ dürfen es nicht verkleinern oder vergrößern.
6. Im Canvas Pfeil drücken: 1 px. Shift+Pfeil: 10 px. Am Rand wird die Bewegung
   begrenzt; die Größe bleibt gleich. Eingaben im Gap-Feld sind keine Region-Bewegung.
7. Entsperren und Ecke anklicken/ziehen. Danach Pfeile am aktiven Handle prüfen.
   Resize muss wieder möglich sein.
8. Ctrl+Z und Ctrl+Y bzw. Ctrl+Shift+Z für Move/Resize prüfen. Ein ganzer Drag
   ist ein Undo-Schritt. Lock ist editorlokal und wird nicht in Config geschrieben.
9. Live-Vorschau öffnen, ausdrücklich bestätigen und speichern.

## Test B — Adjacent

1. Einen kleinen Bereich mit Platz in allen vier Richtungen erstellen.
2. Ausgehend von diesem Bereich jeweils „+ Rechts“, „+ Links“, „+ Oben“,
   „+ Unten“ prüfen. Für jeden Schritt den ursprünglichen Bereich erneut auswählen.
3. Neue Region hat exakt dieselbe Breite/Höhe. Gap `0` bedeutet direkt angrenzend;
   Gap `10` bedeutet zehn physische Pixel Abstand.
4. Neue Region wird aktiv und direkt nach der Ausgangsregion eingefügt.
   Die Nummern müssen durchgehend sein; bestehende Geometrie bleibt unverändert.
5. Nahe einem Rand einen nicht passenden Nachbarn anfordern: verständliche Meldung,
   keine verschobene/verkleinerte neue Region und keine Änderung der Auswahl.
6. Mehr als zwei Regionen erstellen. Liste anklicken → passendes Rechteck aktiv;
   Rechteck anklicken → passende Liste aktiv.
7. „Duplizieren“ prüfen: sichtbare versetzte Kopie gleicher Größe oder Meldung,
   wenn kein Platz ist. „Loeschen“ prüfen: die letzte Region bleibt erhalten.
8. Add/Delete mit Undo/Redo prüfen.

## Test C — Reorder

1. Mindestens drei unterscheidbare Regionen anlegen und ihre Geometrie notieren.
2. Region 2 wählen und ↑ anklicken: ursprüngliche Reihenfolge `1,2,3` wird `2,1,3`.
   Sichtbare Nummern werden neu vergeben, Geometrien bleiben identisch.
3. Reorder mit Undo/Redo prüfen, danach gewünschte Reihenfolge einstellen.
4. Live-Vorschau bestätigen und speichern. Editor schließen und erneut öffnen:
   dieselbe Reihenfolge muss erhalten bleiben.
5. Bei Test E die PNG-/Manifest-/PDF-Reihenfolge mit dieser Auswahl vergleichen.

## Test D — HTML Picker

1. Kalibrierung starten und „HTML-Hilfsseite“ öffnen.
2. Vollständigen Bookmarklet-Code und „Bookmarklet kopieren“ prüfen. Die
   Zwischenablage darf sich erst durch den Klick ändern.
3. In Edge einen Favoriten anlegen und bearbeiten: seine URL durch den gesamten
   Code inklusive `javascript:` ersetzen. Im Zieltab über das Favoritenmenü ausführen.
   Eine sichtbare Favoritenleiste ist nicht erforderlich.
4. Wenn Kopieren blockiert ist, markierten Code mit Strg+C kopieren. Wenn Ausführung
   blockiert ist, in RectoFlow „Manuell ohne HTML“ verwenden. Keine DevTools-Umgehung.
5. Sitzung gilt 180 Sekunden ab Hilfsseiten-Erstellung. Bei Ablauf neu starten.
6. Ergebnisdatei speichern und importieren. Vorschlag im normalen Editor bearbeiten:
   Move, Resize, Lock, Magnifier, Adjacent und Reorder müssen verfügbar sein.
7. Vorschlag darf niemals automatisch gespeichert werden. Live-Vorschau und explizite
   Bestätigung prüfen. Abbrechen und ungültigen Import prüfen; manuell fortfahren können.
8. F8 / Abbrechen entfernt den Browser-Picker; dessen Marker dürfen nicht mit aufgenommen werden.

## Test E — echter Capture

1. Mit Edge auf Hauptanzeige kalibrieren und speichern.
2. RectoFlow schließen und neu starten. Dieselbe Config/dasselbe Profil auswählen.
3. „Aufnahme starten“, anschließend die verlangte finale Kontrolle bestätigen.
   Änderungen an gespeicherter Auswahl erfordern erneute Kalibrierung.
4. Vor erfolgreicher Kontrolle darf kein neuer normaler `run_*`-Ordner entstehen.
   Ein separater `preview_*`-Ordner gehört nur zur Vorschau.
5. Prüfen: Silent Exit? Fehlerdialog? Phase, Diagnose-ID und Logpfad?
6. Im Ausgabeordner prüfen: Run-Verzeichnis, `manifest.json`, PNGs und Reihenfolge.
   Profile schreiben unter `data/captures/<Profil-UUID>`, direkte Configs unter
   ihren konfigurierten Ausgabeordner.
7. Next-Navigation prüfen: ein Klick je bestätigtem Übergang, kein blindes Retry.
8. Finalen Status prüfen: `COMPLETE` bei Erfolg, `STOPPED` bei Capture-Fehler.
   Bei frühem Capture-Fehler darf ein Run ohne PNGs existieren, aber mit Manifest.
9. PDF aus gespeicherten Bildern erstellen und Region-/Seitenreihenfolge prüfen.
   Nach Export bleiben PNGs und Capture-Manifest unverändert.
10. Erneut starten und finale Kontrolle abbrechen: kein neuer normaler Run.

## Test F — ursprünglicher Fehlerfall

Genau den bisherigen realen Klett-Ablauf wiederholen:
Start → zuvor verschwand RectoFlow und ließ einen leeren Run zurück.

Mit diesem Paket darf entweder Capture funktionieren oder ein sichtbarer Fehler
mit Phase, Diagnose-ID und Logpfad erscheinen. Kein irreführender leerer Run vor
erfolgreicher Kontrolle. Scheitert die initiale Manifest-Publikation, kann ein
versteckter `.pending-run_*`-Ordner zurückbleiben; kein normaler Run wird veröffentlicht.
Keine bestehenden Runs löschen. Bei fehlgeschlagener lokaler Protokollierung muss
der Dialog dies ausdrücklich sagen und trotzdem den Originalfehler zeigen.

Bei Fehler bitte zurückgeben:

1. Exakten Dialogtext.
2. Diagnose-ID.
3. Die genannte lokale Logdatei (`data/logs/`, sonst lokaler Temp-Pfad).
4. `manifest.json`, falls vorhanden.
5. Ob PNGs vorhanden waren.
6. Ob der Run leer oder nicht leer war; gegebenenfalls ob nur ein Pending-Ordner existierte.

Keine Screenshots des Buchinhalts erforderlich. Das bestehende Capture-Manifest
kann Dokument-Fenstertitel enthalten; vor Weitergabe auf private Angaben prüfen.

Erst danach: Findings beheben → Regression → gegebenenfalls neues Paket und
Owner-Retest → Fresh Breaker → Owner Acceptance → Merge → Releaseentscheidung.
