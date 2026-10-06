# RectoFlow

**Status: frühe Windows-Vorabversion.** Edge ist nur für die
[dokumentierten Testpfade](docs/COMPATIBILITY.md) real geprüft. Die Unterstützung
für Chrome, Brave und Firefox ist implementiert und durch Vertragstests geprüft;
reale E2E-Läufe sind **nicht verifiziert**. Physische Desktop-Läufe mit 125 % und
150 % Skalierung sind ebenfalls nicht verifiziert. Eine Produktionszertifizierung
für sämtliche Browser-/DPI-Kombinationen wird nicht behauptet.

**Bereiche auswählen, Ansichten aufnehmen, eine PDF erstellen.**

RectoFlow nimmt einen, zwei oder beliebig viele frei wählbare Bildschirmbereiche
aus Brave, Edge, Firefox oder Chrome auf. Die Reihenfolge legst du selbst fest.
Du kannst automatisch mit einem Weiter-Button blättern, manuell weiterschalten
oder nur eine Ansicht aufnehmen. Das Papierformat kannst du am Ende wählen.

Ein, zwei, drei, vier und mehr Rechtecke sind möglich. Mit **+ Bereich** fügst du
weitere hinzu; es gibt keine feste Obergrenze für die Anzahl der Rechtecke.

## Warum es RectoFlow gibt

RectoFlow macht aus Dokumentansichten im Browser geordnete lokale PDFs, wenn ein
verlässlicher Export fehlt oder manuelle Screenshots viel Wiederholungsarbeit
und Fehler verursachen würden.

## UI-Demo mit synthetischen Daten

Die echten Auswahl- und Kontrollkomponenten zeigen hier ausschließlich künstliche
lokale Demobilder. Die Screenshots sind **keine Browser-/DPI-Laufzeitnachweise**.
[Erzeugung und Grenzen](docs/DEMO_ASSETS.md).

![Echte RectoFlow-Auswahl mit zwei synthetischen Bereichen und Weiter](docs/assets/rectoflow-calibration.png)

![Echte RectoFlow-Kontrolle mit synthetischer Ähnlichkeitswarnung und PDF-Optionen](docs/assets/rectoflow-review.png)

## Windows starten

Die portable Windows-ZIP aus den [Releases](https://github.com/severinafrancic/RectoFlow/releases)
vollständig in einen beschreibbaren Ordner entpacken. `RectoFlow.exe` öffnen.
Der Ordner `_internal` muss daneben bleiben. Eine zusätzliche Python-Installation
ist für diese Ausgabe nicht nötig. Version 0.2 bleibt eine unsignierte Vorabversion.

## Bereiche und Weiter einstellen

1. Die Startansicht im gewünschten Browser auf dem Hauptmonitor öffnen.
2. Ein Profil erstellen/importieren oder eine Config wählen. **Bereiche kalibrieren**
   öffnen und das gewünschte Browserfenster ausdrücklich auswählen.
3. **Manuell ohne DOM** funktioniert für alle Bereiche. Optional kann der lokale
   HTML-Picker per Bookmarklet und Ergebnisdatei die ersten zwei Bereiche, Weiter
   und Fortschritt grob vorschlagen. Die Zwischenablage bleibt unberührt.
4. Mit **+ Bereich** weitere Rechtecke hinzufügen. Mit **Löschen** reduzieren,
   zum Beispiel von zwei auf einen Bereich. **Früher / Später** ändert die Reihenfolge.
5. Rechtecke innen ziehen, um sie zu verschieben; über acht Griffe skalieren.
   Die Geometrie bleibt frei. Nur **Ausgewählten Bereich anpassen** ändert nach
   Bestätigung dessen Seitenverhältnis. **Duplizieren**, Referenz und **Direkt rechts**
   helfen bei gleich großen benachbarten Ausschnitten.
6. Navigation wählen: **Weiter-Button**, **Manuell** oder **Einmal**.
   Für Weiter einen Buttonbereich und einen Klickpunkt darin festlegen.
7. Die frische Live-Vorschau nochmals kontrollieren. Sie bleibt verschiebbar.
   Erst eine ausdrückliche Bestätigung speichert die Konfiguration.

Speichern startet die Aufnahme noch nicht. Danach **Aufnahme starten** wählen.
Die aktuelle Kontrollansicht muss erneut bestätigt werden. Bei geändertem
Bildinhalt stoppt der Start vor dem ersten Bildpaar beziehungsweise Aufnahmesatz.

## Papierformat am Ende

Nach der letzten Ansicht erscheint der PDF-Dialog. Wähle A4, A5, A3, A6, A2,
A1, A0, Letter, Legal oder Original sowie Hoch- oder Querformat. Eine PDF-Seite
je Bereich oder alle Bereiche je Ansicht nebeneinander sind möglich.

Die Kontrolle zeigt eine Vorschau der gewählten Ansicht. Ganze Ansichten können
ausgeschlossen und umgeordnet werden. Ähnlichkeits-/Kontrastwarnungen entfernen
nichts automatisch. Bilder werden proportional eingepasst. Ein
Formatwechsel verändert die gespeicherten Ausschnitte nicht. **Später / Abbrechen**
behält PNGs und Manifest. Mit **Gespeicherte Bilder als PDF** kannst du später
ein anderes Format exportieren, ohne erneut aufzunehmen.

Profile liegen unter `data/profiles/<uuid>/`, Aufnahmen getrennt unter
`data/captures/<profile-uuid>/`. **Config-Backups / Wiederherstellen** zeigt die zehn
neuesten Sicherungen; alle bleiben erhalten. Restore sichert zuerst die aktuelle Config.

Neue Exporte liegen im Lauf unter `exports/<export-id>/` mit ExportPlan, Ergebnis
und PDF. Ein nach hartem Abbruch verbliebener RUNNING-Lauf wird als unterbrochen
beziehungsweise ungeklärt angezeigt und nicht exportiert. Resume ist nicht enthalten.

## Manuell weiterblättern

Nach jeder Ansicht fragt RectoFlow, ob eine weitere aufgenommen werden soll.
**Ja** schließt den Dialog; blättere innerhalb des Countdowns im gebundenen
Browser weiter. **Nein** beendet die Aufnahme und öffnet die Formatwahl.
**Abbrechen** stoppt den Lauf mit Zwischenstand. RectoFlow klickt in diesem
Modus keinen Weiter-Button.

## Browser und Grenzen

Alle vier Browser werden vom Fensteradapter akzeptiert. Die echte automatische
Button-Erkennung hängt von der Seite und dem Browser-Anbieter ab. Bei fehlender
UIA-Erkennung gibt es den kalibrierten Vorlagenmodus oder die manuelle Navigation.
Die [Kompatibilitätsdokumentation](docs/COMPATIBILITY.md) nennt die tatsächlich
geprüften Wege und noch offene Live-Prüfungen.

ESC oder die Maus in der linken oberen Bildschirmecke bricht ab. Die Bereiche
müssen gleichzeitig auf dem Hauptmonitor liegen. Fensterposition, Monitor, DPI,
Zoom und Layout während der Aufnahme beibehalten. Bereits gespeicherte Bilder
bleiben bei einem Abbruch erhalten; `manifest.json` gehört zum Lauf.

Technische Details: [Bedienung](docs/USER_GUIDE.md), [Konfiguration](docs/CONFIGURATION.md),
[Entwicklung](docs/DEVELOPMENT.md). Quellcode: MIT-Lizenz, ohne Cloud-Übertragung.
