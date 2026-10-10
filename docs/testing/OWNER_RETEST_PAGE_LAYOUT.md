# RectoFlow: Owner-Retest der realen Findings

Historischer Owner-Subject: `cf35c771d652480f162f46cbc7cc0e04cbf24352`.
Sein Paket und seine Evidence bleiben erhalten. Seine Tests belegen den neuen
Subject nicht. SHA/Tree des neuen Pakets stehen in `BUILD_METADATA.json` neben
der EXE; das neue ZIP liegt in einem eigenen Subject-Unterordner.

ZIP vollständig in einen neuen, beschreibbaren Ordner entpacken. EXE und
`_internal` zusammen lassen. Vorhandene Config/Profil bewusst auswählen.
Edge auf der Hauptanzeige; Fenster, DPI, Zoom und Seitenleisten während einer
Kalibrierung/Aufnahme unverändert lassen. Keine Screenshots des Buchinhalts
zurückgeben. Bei einem Fehler reichen Dialog und lokale Diagnose.

## A — Single Page HTML

1. Eine legitime einseitige erste oder letzte Buchansicht öffnen.
2. RectoFlow → Bereiche kalibrieren → Edge binden → HTML-Hilfsseite.
3. „Bookmarklet kopieren“ selbst anklicken. In Edge einen Favoriten anlegen,
   dessen URL durch den kompletten Code ersetzen, im Buchtab im Favoritenmenü
   starten. Die Favoritenleiste muss nicht sichtbar sein.
4. Die eine sichtbare Seite anklicken → „Seiten fertig / weiter“.
   NEXT/PROGRESS auswählen oder bewusst überspringen, falls Navigation Einmal
   bzw. Manuell verwendet werden soll. Ergebnisdatei speichern und importieren.
5. Genau ein Bereich muss im normalen Editor erscheinen. Keine erfundene zweite
   Region. Vorschlag bearbeiten, Live-Vorschau, ausdrücklich bestätigen/speichern.
6. Abbruchprobe: Eine erneute Kalibrierung abbrechen; Config muss unverändert bleiben.

## B — Double Page HTML / Retry

1. Eine mittlere Doppelseite öffnen. Für den Buchlauf mit zwei Slots hier
   kalibrieren, auch wenn A zuvor nur einen Slot gespeichert hat.
2. Neue Hilfsseite/Sitzung erstellen; beide Seiten in gewünschter Capture-Reihenfolge
   anklicken → Seiten fertig → NEXT/PROGRESS → Ergebnis importieren.
3. Zwei Regionen müssen erscheinen. Sie können gelöscht, geordnet, verschoben,
   vergrößert, gesperrt und ergänzt werden. Keine automatische Bestätigung.
4. Mehr als zwei bewusste Seitenkandidaten müssen ebenfalls in den Editor gelangen.
5. Falls Mapping scheitert: „HTML-Auswahl erneut versuchen“ erstellt eine neue
   Sitzung. Den neuen Bookmarklet-Code verwenden; alte Ergebnisdatei nicht importieren.
   Alternativ „Manuell fortfahren“ oder „Abbrechen“. Keine geratenen Koordinaten.

## C — Keyboard Fine-Tuning

1. Region mit der Maus grob aufziehen. Danach im Canvas Tab drücken.
2. Reihenfolge: NW → N → NE → E → SE → S → SW → W → MOVE → NW.
   Shift+Tab muss rückwärts gehen. Alternativ Handle im Auswahlfeld wählen.
3. Aktiven Handle und Status „Bereich … — Handle: …“ prüfen.
4. SE wählen: Rechts = Breite +1 px; Shift+Unten = Höhe +10 px.
   Der 8×-Magnifier bleibt nach Loslassen der Maus sichtbar und folgt jedem Schritt.
   Harte Pixel, Crosshair, physische X/Y und Handle-Bezeichnung prüfen.
5. N/S: Links/Rechts verändert keine Geometrie. E/W: Oben/Unten verändert nichts.
6. MOVE: Pfeile verschieben 1 px, Shift+Pfeile 10 px. „Groesse fixieren“ lässt nur
   MOVE zu; Breite/Höhe bleiben auch am Rand exakt gleich. Entsperren erlaubt Resize.
7. Magnifier am Bildschirmrand prüfen: Er darf den aktiven Punkt nicht verdecken.
8. Ctrl+Z / Ctrl+Y oder Ctrl+Shift+Z, speichern, neu öffnen: exakte Pixelgeometrie
   erhalten. Adjacent, Gap, Delete/Duplicate und Reorder aus dem bisherigen Guide
   erneut prüfen. Numerische Direktfelder wurden nicht ergänzt.

## D — Erste/Mitte/Letzte, ohne Blank Pages

1. Zwei Capture-Slots auf einer Doppelseite kalibrieren: Bereich 1 links, 2 rechts.
2. Im Launcher „Seitenbelegung / Ausnahmen vor Capture“ öffnen.
3. Erste: nur Rechts (2). Mittlere: beide (1,2). Letzte: nur Links (1).
   „Uebernehmen“ speichert atomar samt Backup; ohne diese Einstellung bleiben alle
   Slots aktiv. Die Policy verwendet Bereichsnummern, keine Geometrie-Heuristik.
4. Vier passende Ansichten aufnehmen: rechts → beide → beide → links.
   Erwartung: 6 PNGs und 6 PDF-Seiten bei PDF-Layout „separate“, in derselben Folge.
   Im Manifest Schema 4: `slots` je Ansicht `[2]`, `[1,2]`, `[1,2]`, `[1]`.
   Keine PNG/Manifest-Bildentry/PDF-Seite für deaktivierte Slots.
5. Bekannte Länge: In der gewählten Config `expected_spreads: 4` verwenden.
   Der Weiter-Guard bleibt streng: an Ansicht 4 muss das bestätigte Ende passen.
6. Unbekannte Länge: `expected_spreads: null`. Der sicher deaktivierte Weiter-Button
   bestimmt die letzte Ansicht. Bei Navigation Manuell entscheidet der bestehende
   Weiter-/Ende-Dialog; der aktuelle Screenshot wird bis dahin im RAM gehalten.
   Ein Timeout, unsicherer Button oder Limit wird nicht als normales Ende geraten.
7. First Links / Last Rechts und Beide/Beide/Beide gegenprüfen.
   Bei genau einer Ansicht gilt Letzte vor Erste; eine Ausnahme hat immer Vorrang.
8. Bei PDF-Layout „spread“ werden nur die aktivierten Slots einer Ansicht zu einer
   PDF-Seite zusammengefügt. „separate“ erzeugt eine PDF-Seite pro tatsächlichem Slot.

## E — Vorab gespeicherte Ausnahme

1. Seitenbelegung öffnen. Ansichtsnummer `2`, nur Rechts (2), „Ausnahme setzen/ersetzen“.
2. „Uebernehmen“, RectoFlow neu starten, Einstellung erneut öffnen: Ausnahme erhalten.
3. Capture: Ansicht 2 liefert nur Slot 2. Keine Zusatzdialoge/Fokuswechsel dafür.
   Ausnahmen ändern keine Kalibrierungsgeometrie und gelten nur für ihre Ansichtsnummer.
4. Ausnahme entfernen/ersetzen, erneut speichern und kontrollieren.
5. Reorder: mindestens drei Regionen 1,2,3 → Region 2 hoch → 2,1,3; speichern/neu öffnen.
   Die Policy bezieht sich anschließend auf die neue sichtbare Capture-Reihenfolge.
   Bei veränderter Slot-Anzahl muss eine vorhandene Policy ausdrücklich neu eingestellt
   werden; alte Config bleibt bis erfolgreichem Speichern erhalten.

## F — Failure-/Exit-Code-Kausalität

1. Wenn ein echter HTML-Fehler auftritt, danach manuell abbrechen.
2. Exit 2 bleibt korrekt. Erwartet: `primary_failure.code = COORDINATE_TRANSFORM_FAILED`,
   `terminal_outcome = USER_CANCELLED`, `exit_code = 2`; beide Ereignisse in `history`.
   Zentraler GUI-Dialog nennt technische Ursache, Phase, Diagnose-ID und Logpfad genau einmal.
3. HTML-Fehler → manueller Fallback erfolgreich: Exit 0, `SUCCESS`, `primary_failure = null`,
   HTML-Fehler bleibt Warning/History. Kein abschließender Fehlerdialog.
4. Reiner freiwilliger Abbruch ohne technischen Fehler: Exit 2, `USER_CANCELLED`,
   `primary_failure = null`; kein irreführender Crash-Dialog.
5. Technischer Fehler ohne erfolgreichen Fallback: Exit 2, Primärursache erhalten.
   Nicht extra echte Fehler erzwingen; reproduzierbare Builder-Tests decken die Fälle ab.

## G — ursprünglicher Klett-Flow

1. Den ursprünglichen realen Ablauf vollständig wiederholen: kalibrieren → speichern
   → RectoFlow neu starten → Aufnahme starten → vorhandene finale Kontrolle bestätigen.
   Legacy-Pfade ohne bisherigen Pflichtdialog bekommen durch diesen Fix keinen neuen.
2. Prüfen: kein Silent Exit; Next-Navigation; sechs bzw. erwartete tatsächliche Seiten;
   Run, `manifest.json`, PNGs, Reihenfolge, finaler Status und PDF-Reihenfolge.
3. Bei Abbruch vor finaler Bestätigung darf kein neuer normaler `run_*` entstehen.
   Bei Fehler nach Run-Start müssen Manifest/Diagnose den Zwischenstand erklären.

Bei Fehler zurückgeben: exakter Dialogtext, Diagnose-ID, Logdatei
(`data/logs`, sonst lokaler Temp-Pfad), `manifest.json` falls vorhanden, PNG-Anzahl,
ob Run leer/nicht leer war, und Nummer dieses Retests. Kein Buchinhalt erforderlich.

Lifecycle nach Builder-Verifikation: **OWNER_RETEST_REQUIRED**.
Danach Findings → Fix/Regression/neues Paket → Owner-Retest. Fresh Breaker und
Owner Acceptance sind spätere eigenständige Grenzen; kein Merge/Release/Tag hier.
