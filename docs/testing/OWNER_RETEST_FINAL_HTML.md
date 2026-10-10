# Owner-Retest: finale Kontrolle, HTML-Import und 4×-Kalibrierung

Nur das neue SHA-gebundene Owner-Paket verwenden. `b9ad8cb…` bleibt historische
Owner-Evidence. Der neue Subject steht in `BUILD_METADATA.json` neben der EXE.
Reales Klett-/Edge-Verhalten: **OWNER_RETEST_PENDING**.

1. **Finale Kontrolle:** Edge/Klett auf der Hauptanzeige öffnen, vorhandene
   Kalibrierung laden und Aufnahme starten. Die Kontrolle zeigt unveränderte
   Bereiche, NEXT, optionalen Seitenwechsel-Bereich, Klickpunkt, Papierformat,
   Orientierung und Navigation. Sie hat ausschließlich „Aufnahme starten“,
   „Neu kalibrieren“ und „Abbrechen“. Pfeile/Maus ändern dort keine Geometrie.
   Eine unveränderte Auswahl muss starten. „Neu kalibrieren“ öffnet die
   Kalibrierung; anschließend separat neu starten. Legacy-Pfade ohne bisherige
   Pflichtkontrolle erhalten weiterhin keinen neuen Pflichtdialog.
2. **HTML First / Normal / Last:** Je eine neue HTML-Sitzung für die erste
   einseitige Ansicht rechts, eine normale Doppelseite und die letzte Ansicht
   links starten. Den neuen Code der Hilfsseite in den RectoFlow-Favoriten
   übernehmen; ein alter Favorit enthält eine alte Sitzung. Die sichtbare
   Favoritenleiste ist optional. Erwartung: **1 / 2 / 1** Seitenvorschläge.
   Unsichtbare alte Wrapper gehören nicht dazu. Die Vorschläge bleiben editierbar.
3. **Import und NEXT:** „Seiten fertig“ wählen und NEXT prüfen. Der Button
   „Nächste Seite“ soll vorgeschlagen werden; PROGRESS darf leer bleiben.
   Ergebnisdatei speichern und sofort in RectoFlow importieren. Nicht scrollen,
   zoomen, Fenstergröße oder Browserleisten zwischen Auswahl und Import ändern.
   Die Sitzung gilt 180 Sekunden. Bei einer unsicheren Abbildung „HTML-Auswahl
   erneut versuchen“ für eine neue Sitzung oder „Manuell fortfahren“ wählen.
   Erfolg heißt: Vorschläge stehen im normalen Editor und müssen dort und in
   der Live-Vorschau ausdrücklich bestätigt werden. Ein vorhandener NEXT-Button
   beweist keine weitere Buchseite; Windows-UIA-Erreichbarkeit bleibt separat.
4. **4× Fine-Tuning:** Im normalen Editor einen Bereich grob setzen. Tab und
   Shift+Tab wechseln NW → N → NE → E → SE → S → SW → W → MOVE. Pfeile ändern
   genau 1 physischen Pixel, Shift+Pfeile genau 10. Der Magnifier bleibt am
   Resize-Handle sichtbar und zeigt 4×, Crosshair und Koordinaten. Mit „Größe
   fixieren“ bewegen die Pfeile nur das ganze Rechteck. Speichern und neu öffnen:
   Geometrie bleibt exakt gleich.
5. **Echter Capture:** Für die gemeinsame Aufnahme auf einer normalen Doppelseite
   zwei Slots kalibrieren. Bestehende First/Middle/Last-Belegung und vorab
   gespeicherte Ausnahmen prüfen, anschließend zur Startansicht zurückkehren.
   Einseitige HTML-Kalibrierung liefert ausdrücklich nur einen Slot; sie erzeugt
   keinen erfundenen zweiten Slot. Bei einer geänderten Slot-Anzahl muss die
   Policy erneut ausdrücklich eingestellt werden. Standard-Seitenwechsel
   vergleicht die aktiven Buchseiten. „Seitenwechsel erkennen (optional)“ ist
   der Advanced-Modus. Finale Kontrolle bestätigen, echten Ablauf durchführen,
   PNG-/Manifest-/PDF-Reihenfolge und fehlende künstliche Leerseiten prüfen.
6. **Beim ersten Fehler nicht sofort erneut versuchen:** Dialogtext und
   Diagnose-ID sichern. `SUMMARY.txt`, `attempt.json` und `events.jsonl` aus dem
   genannten lokalen Diagnoseverzeichnis zurückgeben. Nur mitteilen, ob
   `first-frame.png`, `run_*`, `manifest.json` und PNG-Crops existieren.
   **Keine Buch-Screenshots teilen.** Ein technischer Fehler bleibt trotz späterem
   Cancel in der History; Exit 2 bleibt ein zulässiger fehlgeschlagener Ausgang.

Dieses Paket hat keine Owner Acceptance und keinen Fresh Breaker. Erst die
Owner-Rückmeldung führt zum nächsten Fix/Rerun oder zur Fresh-Breaker-Grenze.
