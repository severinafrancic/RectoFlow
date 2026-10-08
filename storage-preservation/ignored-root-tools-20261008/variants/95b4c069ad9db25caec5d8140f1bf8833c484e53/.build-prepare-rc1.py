from pathlib import Path
import hashlib,json,subprocess
root=Path.cwd();out=root.parent;stage=root/'.build-release-rc1'
sha='e7627a6a3fcee822236c82777d451fbed963b9ea'
assert subprocess.check_output(['git','rev-parse','HEAD'],text=True).strip()==sha
assert not subprocess.check_output(['git','status','--porcelain'],text=True).strip()
stage.mkdir(exist_ok=False)
files={
 'RectoFlow-0.2.0-rc.1-windows-x64.zip':('RectoFlow-0.2.0-candidate-e7627a6-windows-x64.zip','febf2e1184ac8cdaeec8e952ef8726f7c78356721abfed3fe074d1f93baaa4f6'),
 'RectoFlow-0.2.0-rc.1-source.zip':('RectoFlow-0.2.0-candidate-e7627a6-source.zip','a92adc75e35f15208d423f50ca797c34d5229a59e5c5840276abb87e3c3dc415')}
for name,(original,digest) in files.items():
 data=(out/original).read_bytes();assert hashlib.sha256(data).hexdigest()==digest
 with (stage/name).open('xb') as f:f.write(data)
 assert hashlib.sha256((stage/name).read_bytes()).hexdigest()==digest
start='''RectoFlow v0.2.0-rc.1 – Windows starten

Dies ist eine Vorabversion zum Testen, keine vollständig abgenommene stabile Ausgabe.
Quellstand: e7627a6a3fcee822236c82777d451fbed963b9ea
Repository: https://github.com/severinafrancic/RectoFlow
Release: https://github.com/severinafrancic/RectoFlow/releases/tag/v0.2.0-rc.1

1. RectoFlow-0.2.0-rc.1-windows-x64.zip vollständig in einen beschreibbaren Ordner entpacken.
2. RectoFlow.exe starten; den Ordner _internal daneben behalten. Eine zusätzliche Python-Installation ist nicht nötig.
3. Im gewünschten Browser die erste Ansicht auf dem Hauptmonitor öffnen. Ein Profil anlegen/importieren oder eine Config wählen.
4. Bereiche kalibrieren: Browserfenster ausdrücklich auswählen und Manuell ohne DOM verwenden. Einen Bereich auswählen, weitere über + Bereich hinzufügen. Bereiche lassen sich verschieben, skalieren, duplizieren und umordnen.
5. Navigation einstellen: Weiter-Button (UIA oder kalibrierte Vorlagen), Manuell oder Einmal. Für Weiter einen Buttonbereich mit Klickpunkt darin festlegen.
6. Die frische Auswahlvorschau kontrollieren und Speichern bestätigen. Danach Aufnahme starten und die aktuelle Kontrollansicht nochmals bestätigen.
7. Am Ende die gespeicherten Ansichten kontrollieren, bei Bedarf ausschließen/umordnen. Papierformat, Hoch-/Querformat und eine Seite je Bereich oder nebeneinander wählen. PDF-Vorschau und Export bestätigen.

Ein Papierformatwechsel verändert keine Capture-Auswahl. Bilder werden proportional eingepasst. ESC oder die Maus in der linken oberen Bildschirmecke stoppt. Fenster, Monitor, DPI, Zoom und Layout während eines Laufs beibehalten. Unklare Button-Erkennung oder unsicherer Übergang stoppt; fehlgeschlagene Weiter-Klicks werden nicht automatisch wiederholt.

Profile: data/profiles/<uuid>/; Aufnahmen: data/captures/<profile-uuid>/. Original-PNGs und Capture-Manifest bleiben beim Review erhalten. Neue Exporte enthalten export_plan.json, result.json und document.pdf unter exports/<export-id>/. Config-Backups lassen sich über Config-Backups / Wiederherstellen auswählen. RUNNING nach hartem Abbruch wird nicht automatisch abgeschlossen; Resume ist nicht enthalten.

Der Fensteradapter unterstützt Edge, Chrome, Brave und Firefox. Echt geprüft wurden hier Edge-Aufnahmewege mit UIA und Vorlagen bei 96 DPI/100%. Komplette Live-Prüfungen von Chrome/Brave/Firefox, 125/150% physischer Skalierung und vollständiger interaktiver Kalibrierung sind offen. Details: VERIFICATION-rc.1.txt sowie docs/COMPATIBILITY.md im Paket.

Die Build-/Programmversion im unveränderten Paket lautet 0.2.0; rc.1 bezeichnet diesen veröffentlichten Kandidaten.
MIT-Lizenz. Lokal, ohne Cloud-Übertragung; FireShot ist nicht erforderlich. README.de.md und docs/ im Paket enthalten weitere Anleitungen.
'''
verification='''RectoFlow v0.2.0-rc.1 – verification / Prüfstatus

Distribution status: published prerelease candidate; publication is transport authorized by the owner request. It does not supply independent acceptance, owner acceptance or a main merge.
Builder lifecycle: INDEPENDENT_REVIEW_PENDING.
Independent Fresh Breaker outcome: BREAKER_BLOCKED, solely FBR-02-PROOF-004.

Exact source commit: e7627a6a3fcee822236c82777d451fbed963b9ea
Git tree: d6bd848ecf51a5088f59ac1bcc405e7a106e714d
Runtime Python/JavaScript tree SHA256: 99ccfb5ab1c59c65b51ba7ab8fe70c71c72e7ae188eccfe1a9546f07835558fe
Original independently reviewed Windows ZIP SHA256: febf2e1184ac8cdaeec8e952ef8726f7c78356721abfed3fe074d1f93baaa4f6
Explicit source ZIP SHA256: a92adc75e35f15208d423f50ca797c34d5229a59e5c5840276abb87e3c3dc415
Unmodified Windows/source ZIP bytes are published with rc.1 distribution filenames; the embedded build/runtime version remains 0.2.0. Source, dependencies, executable and configuration were not changed for transport.
Independent exact-subject report SHA256: baf57048a35cff1ce86f53b8c2b295914339e80b895279e2ed71ade4295cd81f
The full private-host fixture archive is retained locally rather than published. This summary discloses observed scope and limits.

Executed evidence:
- 124 source regression tests passed on the exact subject, independently rerun.
- 12 independently written adversarial boundary tests passed.
- Real hidden native Tk selection and review checks passed; they do not prove full interactive owner calibration.
- Owned fresh Edge guest localhost fixtures at observed 96 DPI/100% passed, separately with in-memory PNG-template snapshots and the actual UI Automation provider. Each captured 3 views / 2 regions with exactly 2 Next events and a terminal disabled button. Window selection was injected with the explicitly owned window; no frozen live browser capture or full interactive launcher/calibration run was proven.
- 11 actual downloaded EXE invocations passed, including relocated self-check, schema-3 and legacy exports, imported/reordered plan authority, hash/pixel integrity, conflicting override rejection, RUNNING rejection, extreme-DPI and malformed-template failures.
- All 1,277 package members read/hash-recorded; 15 embedded runtime sources and packaged docs/config match the source and BUILD_METADATA.
- 40 paper/orientation/layout combinations passed renderer checks; 3 representative layouts were visually inspected.
- Exact integrated push Windows CI: https://github.com/severinafrancic/RectoFlow/actions/runs/37382635215 (job 112008153613), SUCCESS.
- Final integration PR Windows CI: https://github.com/severinafrancic/RectoFlow/actions/runs/37383927244 (job 112012435822), SUCCESS. Test-merge 06d4120dbdb5deb21634db3b82c3a5f1a69e63d5 has the identical Git tree. This is not a main merge.

Earlier confirmed malformed-profile/numeric isolation, unusable serialized PDF geometry and malformed PNG-template isolation findings were repaired and independently revalidated on this subject. No new confirmed product defect was found in the executed independent scope. That is not an assertion that every browser/page/provider is defect-free.

Still unproven / offen:
Full real Chrome, Brave and Firefox composition; physical 125/150% scaling; full interactive browser selection/calibration/confirmation. The complete four-browser/DPI compatibility matrix remains required. Shared adapter support, executable names, green CI and Edge fixtures do not replace it. Separate reviewer reasoning/worktree was used on the same host/tool infrastructure; separate human/machine authority is not established.

Native Windows 10/11 x64, primary monitor only; unsigned package; finite memory/screen/storage. Automatic Next depends on actual page/provider accessibility or calibrated template state and stops on unknown/unsafe transitions. No automatic retry of an uncertain Next click, no OCR, multi-monitor or resume.

Final integration PR: https://github.com/severinafrancic/RectoFlow/pull/7
Main stable integration/acceptance remains gated. Complete missing proof, recheck exact PR head/base/CI, obtain owner acceptance, then merge and verify resulting SHA/tree before a stable final 0.2 release. Prerelease transport does not close these gates.
'''
notes='''## RectoFlow 0.2 – Windows-Vorabversion / prerelease candidate

**Windows-Download:** Unter **Assets** `RectoFlow-0.2.0-rc.1-windows-x64.zip` herunterladen, vollständig entpacken und `RectoFlow.exe` starten. Den Ordner `_internal` daneben behalten. Python muss nicht zusätzlich installiert werden. `START.de.txt` erklärt die Einrichtung.

### Neu

- Ein, zwei oder weitere frei markierte Capture-Rechtecke, ohne feste Anzahlgrenze; verschieben, skalieren, umsortieren, duplizieren und ausrichten.
- Explizite Browserfenster-Auswahl statt Fokus-Countdown; gebundene Fenster-/Prozess-/DPI-/Fokusprüfung.
- Profile mit isolierten Configs/Vorlagen, atomare Config-Backups und Restore, native prozessübergreifende Sperren.
- Gespeicherte Ansichten vor Export mit Vorschau prüfen, ausschließen oder umordnen; Ähnlichkeits-/Kontrastwarnungen entfernen nichts automatisch.
- Capture-Geometrie und Papierformat getrennt. A0–A6, Letter, Legal, Original; Hoch-/Querformat; einzelne Bereiche oder nebeneinander.
- Unveränderte Capture-Originale; bytegebundener ExportPlan und verknüpfte Manifest-/Plan-/PDF-Prüfsummen. Unterbrochene RUNNING-Läufe werden nicht als abgeschlossen exportiert.
- Optionaler DOM-Helfer mit einmaliger Ergebnisdatei ohne Clipboard-Transport. Screenshot-Auswahl bleibt Standard. FireShot ist nicht nötig.

### Prüfstatus

Dies ist ein **öffentlich verfügbarer Testkandidat**, keine vollständig abgenommene stabile Ausgabe. Die Veröffentlichung wurde ausdrücklich beauftragt; sie ersetzt keine unabhängige/Owner Acceptance und keinen `main`-Merge.

124 Regressionstests, 12 unabhängige adversariale Prüfungen, native Tk-Prüfungen, beide realen Edge-Aufnahmewege bei 96 DPI und 11 tatsächliche EXE-Aufrufe sind erfolgreich. Windows-CI ist erfolgreich. Drei frühere Produktfehler sind behoben und unabhängig nachgeprüft.

**Noch offen:** vollständige echte Chrome-/Brave-/Firefox-Läufe, physische 125/150-%-Skalierung und vollständige interaktive Kalibrierung. Daher bleibt das unabhängige Ergebnis `BREAKER_BLOCKED` (`FBR-02-PROOF-004`). Details stehen in `VERIFICATION-rc.1.txt` und `docs/COMPATIBILITY.md` im Paket.

Quellstand: `e7627a6a3fcee822236c82777d451fbed963b9ea`. Das unveränderte, unabhängig geprüfte Paket meldet Build-/Programmversion `0.2.0`; `rc.1` ist die Kennzeichnung dieses Release-Kandidaten.

Windows-ZIP SHA-256: `febf2e1184ac8cdaeec8e952ef8726f7c78356721abfed3fe074d1f93baaa4f6`.

MIT-Lizenz; lokal, ohne Cloud-Übertragung. Native Windows 10/11 x64, Hauptmonitor. [Integrations-PR #7](https://github.com/severinafrancic/RectoFlow/pull/7) bleibt separat als Entwurf offen.

**English:** Portable Windows test candidate. Extract the complete ZIP, keep `_internal` beside `RectoFlow.exe`, and read the bundled docs. The exact reviewed source/package is unchanged. Full browser/DPI/interactive-calibration proof and stable-release acceptance remain outstanding; see `VERIFICATION-rc.1.txt` for evidence and limits.
'''
for name,data in [('START.de.txt',start),('VERIFICATION-rc.1.txt',verification),('release-notes.md',notes)]:
 with (stage/name).open('x',encoding='utf-8') as f:f.write(data)
assets=[stage/name for name in [*files,'START.de.txt','VERIFICATION-rc.1.txt']]
with (stage/'SHA256SUMS.txt').open('x',encoding='utf-8') as f:
 for path in assets:f.write(hashlib.sha256(path.read_bytes()).hexdigest()+'  '+path.name+'\n')
assets.append(stage/'SHA256SUMS.txt')
manifest={'tag':'v0.2.0-rc.1','subject':sha,'publication_type':'prerelease transport; not acceptance','assets':{p.name:{'bytes':p.stat().st_size,'sha256':hashlib.sha256(p.read_bytes()).hexdigest()} for p in assets}}
with (stage/'prepared-assets.json').open('x',encoding='utf-8') as f:json.dump(manifest,f,indent=2)
print(json.dumps(manifest,indent=2))
