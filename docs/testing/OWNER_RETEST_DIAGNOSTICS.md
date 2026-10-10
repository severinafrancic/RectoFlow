# Nächster Owner-Test: Klett / Edge

Nur das neue Paket verwenden. `ce81efbababe08ca56e9f322b22e4c81efefd817`
ist historische Builder-Evidence und wird nicht erneut als finaler Build getestet.
Der neue Subject steht in `BUILD_METADATA.json` neben der neuen EXE und im
SHA-gebundenen Builder-Bericht. Der portable Build bleibt unveröffentlicht.

1. Die Klett-Seite in Edge auf der Hauptanzeige wie bisher öffnen.
2. Die neue `RectoFlow.exe` starten und bei Bedarf deine gespeicherte Config wählen.
3. Den normalen Ablauf durchführen: kalibrieren, speichern, neu starten,
   Vorschau/Seitenbelegung prüfen, Aufnahme starten und die vorhandene finale
   Kontrolle bestätigen. Legacy-Pfade erhalten keinen neuen Pflichtdialog.
4. Beim **ersten Fehler nicht sofort erneut versuchen**. Dialogtext und Diagnose-ID
   festhalten. Ein freiwilliger Abbruch ohne technischen Fehler zeigt keinen
   Crash-Dialog; auch dafür entsteht ein Attempt.
5. Aus dem im Dialog genannten Diagnoseverzeichnis zurückgeben:
   `SUMMARY.txt`, `attempt.json`, `events.jsonl` und den exakten Dialogtext mit ID.
   Zusätzlich nur angeben: Existiert `first-frame.png`? Existiert `run_*`?
   Existiert dessen `manifest.json`? Sind PNG-Crops vorhanden? War der Run leer?

Die Diagnose liegt normalerweise neben der EXE unter
`data/diagnostics/attempts/<Diagnose-ID>/`. Falls dieser Pfad nicht beschreibbar
ist, verwendet RectoFlow den lokalen Windows-Temp-Pfad
`RectoFlow-diagnostics/attempts/<Diagnose-ID>/`. Ein Attempt ist kein Capture-Run.

`first-frame.png` bleibt privat auf deinem Rechner. **Keine Buch-Screenshots
teilen.** Auch bei einem Fehler direkt nach der Aufnahme kann dieses Bild bereits
vorhanden sein. Seine Existenz, Abmessungen und der Hash stehen in `attempt.json`.

Für den gemeinsamen Funktions-Retest weiterhin A–G aus
[OWNER_RETEST_PAGE_LAYOUT.md](OWNER_RETEST_PAGE_LAYOUT.md) durchführen:
Single/Double HTML, Keyboard/Tab mit dauerhaftem Magnifier, First/Middle/Last,
vorab gespeicherte Ausnahmen, technische Ursache trotz späterem Cancel und
anschließend der ursprüngliche Capture-Flow. Inaktive Slots dürfen weder PNGs
noch Manifest-Seiten oder PDF-Leerseiten erzeugen.

„Seitenwechsel erkennen (optional)“ markiert einen kleinen Bereich, der sich beim
Weiterblättern zuverlässig ändert, etwa die Seitenzahl. Leer lassen bedeutet:
RectoFlow vergleicht die Aufnahmebereiche. Es ist kein Pflichtfeld.

Erwartung bei einem technischen Fehler: Exit Code 2, sichtbarer zentraler Dialog,
technische Primärursache plus letzter erfolgreicher Schritt und Fehler-Checkpoint.
Ein späterer manueller Cancel wird als `USER_CANCELLED` protokolliert; ein früherer
HTML-Fehler bleibt erhalten. Erfolgreicher Fallback endet mit 0 und Warning-History.

Die Owner-Rückmeldung begründet erst den nächsten Fix oder Retest. Dieser Build
hat noch keinen Fresh Breaker und keine Owner Acceptance, Merge oder Release.
