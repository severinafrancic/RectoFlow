# Development and Windows builds

Use native Windows, Python 3.12 x64 and the canonical checkout. Runtime data belongs
in the system temp directory or ignored locations inside the checkout, not sibling
repository copies. Source dependencies are in requirements.txt; the exact initial
build set is in requirements-build.lock.txt. The normal runtime does not need PyInstaller.

```powershell
py -3.12 -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements-build.lock.txt
$env:EDGE_CAPTURE_TEST_TMP = Join-Path (Get-Location) '.build-tests'
.\.venv\Scripts\python.exe -B -m unittest discover -s tests -p 'test_*.py' -v
.\.venv\Scripts\python.exe scripts\build_windows.py
```

The build runs PyInstaller on Windows, collects Tcl/Tk, UIA and ReportLab imports,
keeps configuration beside the executable, includes original third-party notices,
and creates the portable ZIP under ignored artifacts/. It is not a cross-compiler.
See [PyInstaller documentation](https://www.pyinstaller.org/en/stable/).

Source/frozen self-check imports critical components without acquiring the desktop:

```powershell
RectoFlow.exe --self-check
RectoFlow.exe --version
```

## Architecture and verification

`calibration/regions.py` owns the ordered region/browser/navigation contracts.
`geometry.py` keeps physical screen, CSS and scaled canvas spaces separate.
`screenshot_picker.py` edits free geometry with an optional explicit aspect action; `config_io.py` atomically
preserves configuration. `edge_capture.py` binds the selected native window and
owns stable/changed-state capture, manifests and PDF integrity. `pdf_export.py`
uses only saved images for final paper choice. `rectoflow.py` is the launcher/CLI.

`storage.py` provides native process locks; `profiles.py` owns indexless profile
transactions/snapshots; `exports.py` owns schema-3 freeze validation, persisted
plans, same-byte image verification/decoding, analysis and linked export results.
Profile and export state are independent of capture data. See WORKFLOW_02.md.

Native Edge fixture (own localhost page and isolated guest profile; changes focus,
never adopts an owner browser or changes desktop DPI):

```powershell
python tests/edge_fixture_smoke.py
python tests/edge_fixture_smoke.py --uia
```

The three substantive PRs target the integration branch. One full Fresh Breaker
reviews the integrated SHA, then the final PR base/head/CI/conflicts are checked
before owner acceptance. Material changes invalidate affected evidence; main
merge and release hashes need separate post-merge verification.

One capture record becomes visible in the manifest only after all region PNGs are
written. Record ordering and names are deterministic. Failed navigation is never
retried automatically. Legacy two-region configs/manifests remain read-compatible.
Final export changes output dimensions without changing acquisition coordinates.

Tests must challenge wrong identities, deleted/reordered regions, count limits,
unknown buttons, stale confirmed pixels, conflicting config writes, partial failure,
recovery, paper fitting and frozen runtime composition. Browser executable-name
tests are not real browser tests. A new substantive code tree invalidates old evidence.

The initial public release is a prerelease with the Builder lifecycle capped at
INDEPENDENT_REVIEW_PENDING. Independent review can be blocked on unproved native
composition. Do not label a successful package build or green CI production acceptance.
