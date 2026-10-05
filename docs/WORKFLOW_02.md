# RectoFlow 0.2 workflow contracts

Calibration uses freely sized rectangles. Paper settings never resize the capture
selection automatically. The optional aspect-ratio action affects only the
selected rectangle and requires confirmation.

Choose a browser window explicitly. READY requires supported executable, visible
non-minimized top-level window, usable primary-monitor bounds and known process
identity/DPI. Identity and environment are checked before activation; foreground
is checked after activation and immediately before screenshots/input. HWNDs are
never substituted automatically.

Config writes use exclusive native Windows handles across processes, digest
conflict detection, verified byte-exact backups and atomic replacement. Restore
backs up the current file and restores the selected backup bytes. All backups are
retained; the launcher displays the latest ten. Foreign writers are outside the
cooperative lock protocol.

Screenshot selection is the default. The experimental HTML helper uses a local
bookmarklet and a downloaded JSON result, never the clipboard. Tokens expire
180 seconds after generation and are consumed once after valid import. CSP may
block the helper; use the screenshot picker without changing browser protections.

Builder verification and publication do not constitute independent or owner
acceptance. Main requires PR, current successful Windows CI and resolved review
threads; the smoke PR is closed without merging.

Profiles use `data/profiles/<uuid>/` with metadata/config and independent template
bytes. UUID folders are enumerated without a central index. Incomplete staged
folders are hidden; malformed profiles are reported individually. Stable store,
UUID and canonical-config locks live outside movable profile folders. Capture
snapshots config and templates under these locks, then releases them for the run.
Managed output is `data/captures/<profile-uuid>/<run-id>/`; direct `--config`
retains relative `output_dir`. The manifest records the profile UUID and hashes
of the actual snapshot bytes (`profile: null` for direct configs).

The picker supports duplicate, left/top alignment, equal size and placement
directly to the right of an explicit reference; default gap is zero physical
pixels. Invalid geometry is rejected without changing the current selection.
