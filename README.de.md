# RectoFlow

**Bereiche auswählen, Ansichten aufnehmen, eine PDF erstellen.**

RectoFlow nimmt einen, zwei oder beliebig viele frei wählbare Bildschirmbereiche
aus Brave, Edge, Firefox oder Chrome auf. Die Reihenfolge legst du selbst fest.
Du kannst automatisch mit einem Weiter-Button blättern, manuell weiterschalten
oder nur eine Ansicht aufnehmen. Das Papierformat kannst du am Ende wählen.

Ein, zwei, drei, vier und mehr Rechtecke sind möglich. Mit **+ Bereich** fügst du
weitere hinzu; es gibt keine feste Obergrenze für die Anzahl der Rechtecke.

## Windows starten

Die portable Windows-ZIP aus den [Releases](https://github.com/severinafrancic/RectoFlow/releases)
vollständig in einen beschreibbaren Ordner entpacken. `RectoFlow.exe` öffnen.
Der Ordner `_internal` muss daneben bleiben. Eine zusätzliche Python-Installation
ist für diese Ausgabe nicht nötig. Die erste Ausgabe ist eine unsignierte Vorabversion.

## Bereiche und Weiter einstellen

1. Die Startansicht im gewünschten Browser auf dem Hauptmonitor öffnen.
2. **Bereiche kalibrieren** wählen und während des Countdowns den Browser aktivieren.
3. **Manuell ohne DOM** funktioniert für alle Bereiche. Optional kann der lokale
   DOM-Picker die ersten zwei Bereiche, Weiter und Fortschritt grob vorschlagen.
4. Mit **+ Bereich** weitere Rechtecke hinzufügen. Mit **Löschen** reduzieren,
   zum Beispiel von zwei auf einen Bereich. **Früher / Später** ändert die Reihenfolge.
5. Rechtecke innen ziehen, um sie zu verschieben; über acht Griffe skalieren.
   Papierformat und Hoch-/Querformat einstellen. Die erste Papier-Anpassung kann
   die Auswahl verkleinern: Inhalt kontrollieren und die Box bei Bedarf vergrößern.
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

Die Vorschau zeigt die erste PDF-Seite. Die Ausgabe enthält alle gespeicherten
Ansichten in ihrer Reihenfolge. Bilder werden proportional eingepasst. Ein
Formatwechsel verändert die gespeicherten Ausschnitte nicht. **Später / Abbrechen**
behält PNGs und Manifest. Mit **Gespeicherte Bilder als PDF** kannst du später
ein anderes Format exportieren, ohne erneut aufzunehmen.

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
