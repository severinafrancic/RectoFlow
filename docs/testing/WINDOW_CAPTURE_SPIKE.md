# Isolierter HWND-Capture-Spike

Produktentscheidung: **ImageGrab / Hauptmonitor bleibt aktiv.** Kein qualifizierter
WindowCaptureBackend in diesem Owner-Paket. Keine Extension, keine Session-
Änderung, keine neue Capture-Abhängigkeit oder neue Windows-Mindestversion.

## Verfahren

`tests/window_capture_spike.py` verwendet ausschließlich die eigene lokale
Edge-Testseite mit eigenem Guest-Profil aus `edge_fixture_smoke.py`. Es vergleicht
native GDI/PrintWindow-Aufnahmen des bekannten HWND mit der sichtbaren Testfläche
und erweitert die Testseite um Canvas 2D/WebGL. Standardflags und Flag 2 werden
dreimal gemessen. Eine eigene Abdeckung und Minimierung gehören zur isolierten
Qualifikation. Produkt-Guards werden dabei nicht gelockert. Private Fenster-PNGs
und Profile bleiben unter ignorierten `.build-window-spike/` bzw.
`.build-edge-fixture/`; Builder-Evidence übernimmt ausschließlich Zahlen/Hashes.

## Beobachtung und Bewertung

| Aspekt | Beobachtet / Grenze |
|---|---|
| Edge / klassische HTML-Flächen | Eigene lokale drei Ansichten bei 192 DPI: neun Standard-Aufnahmen vollständig schwarz trotz API-Erfolg; neun Aufnahmen mit Flag 2 enthielten die erwarteten je 216000 Seitenfarbpixel. |
| Pixelintegrität | Flag-2-Fenster gegenüber Desktop-Window-Crop hatte mittlere Differenz ca. 2,94; Window/DC/DWM-Ränder sind nicht automatisch identisch. Keine pauschale Guard-Toleranz daraus abgeleitet. |
| Canvas / WebGL / Hardware-Compositor | Erweiterter nativer Versuch lieferte Browser-Chrome ohne erwartete Seiten-/Canvas-/WebGL-Farbflächen, auch mit Flag 2. Der separate Produkt-Fokus-Test blockierte vor ImageGrab. Ob Content noch nicht präsentiert oder vom Capture nicht geliefert wurde, ist damit nicht sicher getrennt: keine Qualifikation. |
| Occlusion | Im erweiterten Versuch auch bei eigener Abdeckung keine erwarteten Content-Farben. Keine Freigabe für verdeckte Aufnahmen. |
| Minimized | Nur 160 × 28 Fensterfläche und keine Seitenfarbe statt 1110 × 1800. Produkt verweigert minimierte Targets weiterhin. |
| DPI / Browserzoom | 192 DPI tatsächlich gemessen; andere physische DPI/Zoom-Kombinationen nicht bewiesen. Geometrie bleibt Screen-Physical-Pixels. |
| Window / Client | Spike misst ganzes GetWindowRect; Client-only ist ein anderer Ursprung und benötigt ClientToScreen plus DWM-/DPI-Vertrag. Der Produkt-Crop darf diesen Ursprung nicht erraten. |
| Performance | Klassisches Flag 2 etwa 0–47 ms, erweiterte native Abfragen bis ca. 265 ms. PrintWindow ist synchron; API-Erfolg prüft keine Bildinhalte. Kein Produkt-Hang-/Timeout-Vertrag qualifiziert. |
| Frozen / Plattform | Spike läuft nur als isoliertes natives Testskript. HWND-Backend weder frozen noch auf weiteren Windows-Versionen qualifiziert. Produkt nutzt die vorhandenen gepinnten Dependencies. |

Diese Messungen entscheiden gegen einen ungesicherten Backend-Wechsel. Sie
bestimmen **nicht** die Root Cause des realen Klett-Findings. Der neue Attempt
soll dort erstmalig nachweisen, ob ImageGrab überhaupt erreicht wird und ob
vorher oder nachher ein Guard blockiert.

## Primärquellen und Alternativen

[Microsoft PrintWindow](https://learn.microsoft.com/en-us/windows/win32/api/winuser/nf-winuser-printwindow)
beschreibt den synchronen Aufruf und das Rendern durch die Zielanwendung, nicht
einen garantierten Compositor-Snapshot. Die dokumentierte Client-only-Option ist
vom ganzen Fenster zu unterscheiden. Flag 2 wird hier experimentell gemessen;
daraus entsteht kein allgemeiner Browservertrag.

[Windows Graphics Capture HWND-Interop](https://learn.microsoft.com/en-us/windows/win32/api/windows.graphics.capture.interop/nf-windows-graphics-capture-interop-igraphicscaptureiteminterop-createforwindow)
ist ein möglicher späterer Adapter ab Windows 10 1903 (Build 18362). D3D/WinRT-
Frame-Lifetime, Größenänderung, Content-Reife, Occlusion, Fehler/Timeout und
Frozen-Packaging brauchen eigene Qualifikation. Hier nicht implementiert.

[Pillow ImageGrab](https://pillow.readthedocs.io/en/stable/reference/ImageGrab.html)
unterscheidet Desktop-BBox und Windows-Fensteraufnahme. Das Vorhandensein eines
HWND-Parameters ersetzt ebenfalls keine Browser-/Pixelqualifikation.

Die Quelle des produktiven Frames bleibt die bestehende ImageGrab-Monitor-
Aufnahme mit unveränderten Ziel-Guards. Eine Backend-Abstraktion wird erst sinnvoll,
wenn ein zweiter Backend die erforderliche Integrität tatsächlich erfüllt.
