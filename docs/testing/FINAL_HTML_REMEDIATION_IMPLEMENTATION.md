# Builder-Slice: finale Kontrolle und HTML-Import

Ausgangspunkt: Subject `b9ad8cb32a871abca3a36e26ae11924bc835a3e5`, Tree
`5a030878fc71a7a69874c2ece078e897aaaa4510`. Kanonischer Branch:
`fix/v021-capture-start-diagnostics`. Alte Builds/Evidence bleiben historisch.

## Befund und Beweisgrenze

Der reale Capture-Attempt erreichte `FIRST_FRAME_GUARD_OK`, danach
`CONFIRMATION_FAILED`, ohne Run/Manifest. Die alte Sammelprüfung meldete
`INVALID_RECTANGLE`, protokollierte aber keine Vergleichswerte. Der genaue
damals geänderte Wert ist **nicht rekonstruierbar**. Nachweisbare Architektur-
Ursache: Die Startkontrolle verwendete den vollständigen mutierbaren Editor.
Maus, Pfeile, Format-/Navigationsauswahl und Klickpunkt konnten dort geändert
werden; der Konstruktor normalisierte außerdem fehlende/ungeeignete Klickpunkte.
Diese Eigenschaften sind für eine Kontrolle gespeicherter Autorität falsch.
Papieranpassung findet nur nach expliziter Editoraktion statt; kein Nachweis für
eine automatische Papier-Zentrierung im realen Attempt.

Die Owner-HTML-Strukturen enthalten semantische `section[data-page-wrapper]`
mit `img[alt="Seite …"]`. First: eine rechts; Normal: zwei; Last: eine links und
zwei alte Wrapper mit `opacity:0`. Die bisherigen manuellen Element-Klicks
prüften diese Sichtbarkeit nicht. Drei Farbfelder belegten weder die Sitzung
pixelweise noch einen unabhängig geprüften vierten Anker. Bisherige gemalte
Unit-Fixtures prüften die echte Browser-Export-/Raster-Komposition nicht.
Eine fehlende reale Markeraufnahme beweist keine spezifische RGB-, DPR- oder
Browserzoom-Ursache; diese bleibt im Owner-Retest zu unterscheiden.

## Global Impact / Boundary Audit

Config/ProfileStore liefert die persistierte Auswahl. `regions.selection` erhält
Legacy Single/Double und die explizite Listenreihenfolge. Capture bestätigt
eine unveränderte Momentaufnahme vor hidden Stage/Manifest/Run-Publikation.
Die read-only Kontrolle kopiert Geometrie/Klickpunkt ohne Normalisierung.
Start, Neukalibrierung und Abbruch sind ihre einzigen Aktionen. Editierports und
Shortcuts sind gesperrt; normale Auswahl/Nummernanzeige ist weiterhin möglich.
Neukalibrierung führt explizit zum bestehenden Calibration-Workflow und erzeugt
keinen Capture-Run. Das anschließende Capture bleibt ein separater Neustart.

Die Prüfung trennt Region-Reihenfolge, jede Region-Geometrie, NEXT, PROGRESS,
Klickpunkt, Papier, Orientierung und Navigation. `CONFIRMATION_FIELD_MISMATCH`
protokolliert alte/neue technische Werte; `CONFIRMATION_STATE_MISMATCH` stoppt
fail-closed. Der Legacy-Ausnahmetyp/-Code `INVALID_RECTANGLE` bleibt für API-
Kompatibilität erhalten, die Diagnostik benutzt den spezifischen failure_code.
Eine zweite Prüfung erkennt Config-Mutationen nach der zweiten Aufnahme.
Auf der Dateigrenze prüft ein kurzer Config-Lock vor/nach der Kontrolle die
originalen Bytes; externe Änderungen können den geladenen Subject nicht
unbemerkt ersetzen. Andere Config-Änderungen werden nur mit Hashes protokolliert.
Kein Lock bleibt während GUI-Wartezeit gehalten; Calibration-Speicherung besitzt
weiter ihren eigenen atomaren Digest-/Backup-Vertrag.

DOM-Producer ist das lokale Bookmarklet. Es ermittelt Computed Styles inklusive
Vorfahrensichtbarkeit, Clip-/Viewport-Schnitt und tatsächliche Hit-Test-Sichtbarkeit.
Es traversiert offene Shadow Roots; Cross-Origin-Frames und geschlossene fremde
Roots bleiben eine manuelle Grenze. Ein eindeutiger horizontaler Satz wird links
nach rechts vorgeschlagen, geometrische Mehrdeutigkeit behält DOM-Reihenfolge.
Explizite Klick-Reihenfolge wird nicht automatisch umsortiert. NEXT wird aus einem
eindeutigen sichtbaren semantischen Button vorgeschlagen; PROGRESS nicht erraten.
NEXT-Existenz verändert weder Policy noch terminales Navigationsergebnis.

Der neue Transport ist schema 3: vier 32-CSS-px Fiducials mit farbigem Außenring
und Schwarz/Weiß-Innenraster (Orientierungspräfix plus je 32 Bits der 128-Bit-
Session-ID). Import bleibt token-/zeit-/single-use-gebunden und whitelisted.
Schema 1/2 bleiben lesbar. Die Pixel-Erkennung verifiziert Ringgröße, Form,
schmale bestehende Farbdistanz und sämtliche Innenbits; ein Farbfleck reicht
nicht. Vier Anker müssen eine einzige konsistente Achsenabbildung liefern;
DPR-/Alignment-/Bounds-Grenzen bleiben unverändert. CSS-Koordinaten bleiben
viewportrelativ, Scroll wird nicht addiert. Chrome-Origin wird gemessen.
Pinch-Zoom bleibt fail-closed. DOM-Metadaten besitzen picker_schema/marker_count;
Config-/Profile-/Manifest-Schema werden nicht geändert.

Checkpoint-Ports: `DOM_HELPER_WRITE`, `DOM_IMPORT_FILE`, `DOM_SESSION_VALIDATE`,
`DOM_PAYLOAD_VALIDATE`, `DOM_SCREENSHOT`, `DOM_MARKER_DETECT`,
`DOM_MAPPING_SOLVE`, `DOM_RECT_TRANSFORM`, `DOM_PROPOSAL_ADAPT` und
`DOM_EDITOR_PROPOSAL_READY`. Spezifische failure_codes unterscheiden
`DOM_MARKERS_MISSING`, `DOM_MARKERS_AMBIGUOUS`, `DOM_MAPPING_INVALID` und
`DOM_RECT_TRANSFORM_FAILED`. Originalcause/Fallback/Cancel bleiben im Attempt;
Retry startet eine neue Session. Keine private HTML-/Text-/URL-Payload im Journal.
Ein Vorschlag besitzt keine Akzeptanzautorität: Editor und explizite Livekontrolle
bleiben erforderlich. Eine bestehende Policy wird nur bei explizit bestätigter
Slot-Änderung neu eingestellt.

Der Magnifier verwendet standardmäßig 4× mit nearest-neighbor. Der sichtbare
Ausschnitt umfasst mehr Quellpixel bei ähnlicher Panelgröße. Physical-Pixel-
Geometrie, Handle-Tab-Reihenfolge, persistente Lupe und 1/10-px-Schritte bleiben
unverändert. Der bisherige 8×-Pixeltest prüft explizit zoom=8; zusätzliche Tests
prüfen 4× und die halbierte sichtbare Schrittweite.

Der Capture-Poll vergleicht aktive Slots der tatsächlichen View-Policy.
Ein Full-Frame vor Navigation bleibt nur im Speicher als Vergleichsquelle;
für die nächste View werden beide Vergleichsseiten auf denselben aktiven
Slot-Satz projiziert. So erzeugt ein Maskenwechsel keinen Größenfehler oder
künstlichen Change. Bei unbekannter Länge bestimmt der bestätigte disabled-
Zustand die Last-Maske; Overrides haben Vorrang. Inaktive Animationen erzeugen
keinen Seitenwechsel. Ein ausdrücklich gespeicherter Progress-Bereich bleibt
Advanced-Quelle. Erste Confirmation-/Pixelbindung und Window-/Fokus-/DPI-/
Navigation-Guards behalten ihre bestehenden strikten Grenzen.

## Tests und Assumption Challenge

Native Tk prüft die unveränderten technischen Owner-Geometrien, inert bleibende
Editierports und den echten Start-Button ohne zusätzlichen Bestätigungsdialog.
Gezielte In-Memory-/Dateiänderungen prüfen field-specific fail-closed und kein Run.
Der vollständige bisherige Testsatz bleibt bestehen.

Browser-E2E rendert eigene synthetische HTML-Fixtures in frischen Headless-Edge-
Profilen. Standard-Loopback-Testinstrumentation steuert nur die eigene PID/den
eigenen Blank-Tab; kein Owner-Profil, keine Security-Policy-Flags, kein produktiver
DevTools-Workflow. Die echte Bookmarklet-Download-Datei wird importiert und
die Marker im tatsächlich gerenderten Raster dekodiert. First/Normal/Last laufen
bei DPR 1/1.25/1.5/2; weitere Cases prüfen opacity/display/visibility/Vorfahren,
Offscreen, Scroll, offene Shadow Roots, >2 Candidates, NEXT und spezifische Fehler.
Ein künstlicher Screen-Origin testet die Offset-Rekonstruktion; dies ist kein
Nachweis der echten Desktop-/ImageGrab-/Windows-DPI-Komposition.

Der zuerst verwendete Headless-CLI-Screenshot änderte den Viewport nach Export
und entfernte dadurch korrekt die Marker. Der Test verwendet deshalb Export
und Screenshot im selben unveränderten Viewport. Produkt-Resize-/Scroll-Guards
wurden nicht gelockert. Wiederholte/gestohlene Payloads, zwei komplette Fiducial-
Sätze, falsche Sessionbits, vierter Anker versetzt und ungültige Rechtecke werden
abgewiesen. Ein JSON-Parse allein gilt ausdrücklich nicht als Import-PASS.

Restliche Annahmen: reale Klett-Styles/Compositing, tatsächliche Windows-DPI-
Varianten, Browser-Chrome/Zoom, Owner-UIA und echter Seitenwechsel bleiben
**OWNER_RETEST_PENDING**. Insbesondere Preview `BUTTON_STATE_UNKNOWN` aus
historischer lokaler Evidence ist separat; Final Confirmation belegt keinen
Button-/Navigationsfehler. ImageGrab bleibt das Produktbackend.
Der Builder stellt keine unabhängige Review-/Acceptance-Autorität aus.

API-Grundlagen: [Computed Styles](https://developer.mozilla.org/en-US/docs/Web/API/Window/getComputedStyle),
[Viewport-Rechtecke](https://developer.mozilla.org/en-US/docs/Web/API/Element/getBoundingClientRect),
[Chromium Headless](https://developer.chrome.com/docs/chromium/headless).
