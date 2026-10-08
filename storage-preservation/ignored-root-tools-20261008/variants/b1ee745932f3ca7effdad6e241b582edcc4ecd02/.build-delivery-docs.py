from pathlib import Path
root=Path(__file__).resolve().parent; out=root.parent
start='''# RectoFlow 0.2 – Windows-Kandidat starten

Dieser Kandidat gehört zu Commit e7627a6a3fcee822236c82777d451fbed963b9ea und PR https://github.com/severinafrancic/RectoFlow/pull/7.
Er ist zum Prüfen vorbereitet. Die finale Freigabe und Veröffentlichung von 0.2 stehen wegen der noch offenen Browser-/DPI-/interaktiven Kalibrierungsnachweise aus.

1. RectoFlow-0.2.0-candidate-e7627a6-windows-x64.zip vollständig in einen beschreibbaren Ordner entpacken.
2. RectoFlow.exe starten. Den benachbarten Ordner _internal mit allen Dateien behalten. Python muss nicht zusätzlich installiert werden.
3. Die erste gewünschte Ansicht im Browser auf dem Hauptmonitor öffnen.
4. Ein Profil erstellen/importieren oder eine Config auswählen. „Bereiche kalibrieren“ öffnen und das Browserfenster ausdrücklich wählen.
5. „Manuell ohne DOM“ verwenden. Einen Bereich markieren, weitere mit „+ Bereich“ hinzufügen. Ein, zwei oder mehr Bereiche sind möglich; es gibt keine fest programmierte Obergrenze. Alle Bereiche müssen gleichzeitig sichtbar sein und in den verfügbaren Bildschirm-/Speicherbereich passen.
6. Bereiche ziehen und an den Griffen skalieren; die Reihenfolge mit „Früher / Später“ ändern. „Duplizieren“ und „Direkt rechts“ helfen bei gleich großen Ausschnitten. Papierformatwechsel verändert keine Ausschnitte. Das Anpassen eines ausgewählten Bereichs an ein Seitenverhältnis ist eine eigene bestätigte Aktion.
7. Navigation auswählen: „Weiter-Button“, „Manuell“ oder „Einmal“. Für automatische Navigation UIA oder kalibrierte Button-Vorlagen einstellen; der Klickpunkt muss im Button liegen.
8. Die frische Auswahlvorschau kontrollieren und das Speichern ausdrücklich bestätigen. Danach „Aufnahme starten“ wählen und die aktuelle Kontrollansicht nochmals bestätigen.
9. Nach Abschluss die gespeicherten Ansichten prüfen, bei Bedarf ganze Ansichten ausschließen oder umordnen. Warnungen entfernen nichts automatisch.
10. A4/A5/A0–A6/Letter/Legal/Original, Hoch-/Querformat und eine Seite je Bereich oder nebeneinander wählen. PDF-Vorschau kontrollieren und Export ausdrücklich bestätigen.

ESC oder die Maus in der linken oberen Bildschirmecke stoppt die Aufnahme. Fenster, Monitor, DPI, Zoom und Layout während eines Laufs unverändert lassen. Eine unklare Button-Erkennung oder ein unsicherer Übergang stoppt; ein fehlgeschlagener Weiter-Klick wird nicht automatisch wiederholt.

Profile liegen unter data/profiles/<uuid>/, Aufnahmen getrennt unter data/captures/<profile-uuid>/. Config-Backups lassen sich über „Config-Backups / Wiederherstellen“ auswählen; Restore sichert vorher den aktuellen Stand. Bereits gespeicherte PNGs und das Capture-Manifest bleiben beim Review unverändert. Jeder neue Export bekommt im Lauf exports/<export-id>/export_plan.json, result.json und document.pdf.

„Gespeicherte Bilder als PDF“ kann einen abgeschlossenen/gestoppten Lauf später erneut exportieren. Ein nach Prozess-Kill oder Stromausfall verbliebener RUNNING-Lauf wird nicht automatisch abgeschlossen/exportiert; Fortsetzen/Resume ist in 0.2 nicht enthalten.

Browser: Edge, Chrome, Brave und Firefox sind im Fensteradapter implementiert. Echt geprüft wurden hier Edge-Aufnahmewege mit UIA und Bildvorlagen bei 96 DPI (100%). Vollständige Live-Prüfung der weiteren Browser, 125/150% physischer Skalierung und interaktiver Kalibrierung ist noch offen. Das ist eine fehlende Verifikation, keine festgestellte Inkompatibilität.

README.de.md und docs/ im entpackten Paket enthalten die ausführliche Bedienung, Konfiguration und Entwicklung. MIT-Lizenz; lokal, ohne Cloud-Übertragung. FireShot wird nicht benötigt.

Lokaler Quellcode:
C:\\Users\\sever\\Documents\\Codex\\2026-10-05\\referenced-chatgpt-conversation-this-is-an\\outputs\\RectoFlow

Windows-ZIP SHA-256:
febf2e1184ac8cdaeec8e952ef8726f7c78356721abfed3fe074d1f93baaa4f6
'''
with (out/'RectoFlow-0.2.0-START-e7627a6.de.md').open('x',encoding='utf-8') as f:f.write(start)
release='''RectoFlow 0.2 – Calibration & Workflow UX

Candidate source: e7627a6a3fcee822236c82777d451fbed963b9ea
Integration PR: https://github.com/severinafrancic/RectoFlow/pull/7
Status: prepared candidate, not a published release or owner acceptance.

Choose one or more free capture regions in an explicitly selected browser window. Reuse isolated profiles, duplicate/align regions, and restore atomically published config backups. Capture binds in-memory config/template snapshots with provenance and finalizes its schema-3 manifest before review.

Review saved views with thumbnails, reorder or exclude whole views, inspect similarity/contrast warnings, then choose paper format/orientation. Exports preserve originals and use persisted ExportPlan bytes plus linked manifest/plan/PDF digests. Interrupted RUNNING runs stay recovery-required. Legacy rebuild remains supported.

Windows x64 portable package includes Python/Tcl/native dependencies, MIT source license and original dependency notices. Fully extract the ZIP and keep _internal next to RectoFlow.exe.

Verification: 124 source tests, 12 independently written adversarial checks, native Tk checks, both owned Edge modes at 96 DPI, successful Windows CI and 11 actual downloaded EXE invocations. Forty paper/orientation/layout combinations passed renderer checks; three representative output layouts were visually inspected.

The independent review is BREAKER_BLOCKED because complete Chrome/Brave/Firefox, physical 125/150% scaling and interactive calibration proof remains outstanding. All three earlier confirmed product findings are repaired. Main merge, resulting-tree verification, owner acceptance and final release remain gated. Do not publish these notes as an accepted final 0.2 release without completing those steps.
'''
with (out/'RectoFlow-0.2.0-release-notes-e7627a6.txt').open('x',encoding='utf-8') as f:f.write(release)
print('Start instructions and reviewable release notes saved.')
