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

LOCK_IDENTITY_1: existing configs bind a native volume/file ID obtained from an
opened handle; absent configs bind the final handle-resolved parent and normalized
filename. Stable final-path locks survive atomic replacement; a file-ID mutex also
serializes hard-link aliases. Case/dot/path aliases resolve to the same identity.
Backups are written/flushed/verified under a .json.tmp name and atomically published
as .json before config replacement. Restore enumeration ignores unfinished files.

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

Button-template recording also uses store/UUID/config locks, rejects a stale
config digest, validates the encoded PNG and publishes it atomically. Calibration
may load config without templates to create missing templates; capture always
requires the complete verified snapshot. CLI failures return exit code 2 without
opening a modal dialog, including frozen executables and interrupted-run exports.

The picker supports duplicate, left/top alignment, equal size and placement
directly to the right of an explicit reference; default gap is zero physical
pixels. Invalid geometry is rejected without changing the current selection.

New capture records use schema 3. Only COMPLETE/STOPPED plus finished may enter
review/export. A writer holds its run lock until final manifest persistence. Hard
interruption leaves RUNNING intact and excluded from normal export; no auto-finalize
or resume. Legacy unknown-writer activity remains explicitly unknown.

Each new export persists a unique ExportPlan before rendering. The actual stored
bytes define its SHA-256 and parsed settings. GUI and schema-3 --rebuild share this
renderer; absent --export-plan means a new all-views plan with effective defaults
and optional CLI paper overrides. Existing plans reject conflicting overrides.

PNG path read → SHA-256 check → BytesIO decode/load → dimension check → render
that decoded object. Result schema 1 links plan/manifest/PDF hashes. Plan/manifest
changes during rendering prevent COMPLETE. Export errors/cancellation never modify
the capture manifest. COMPLETE PDFs remain proportional and browser-neutral.
Computed page dimensions must stay finite and positive after the exact ReportLab
number serialization; zero/infinite MediaBoxes cannot produce COMPLETE results.
JSON numeric validation rejects values outside finite runtime representation
without escaping per-profile isolation. Metadata and config roots must be objects;
one malformed profile cannot prevent discovery of valid siblings.
Template decoding is shared by profile validation, recording and runtime. It
rejects unexpected dimensions before loading pixels, preserves Pillow image-bomb
limits and turns malformed image data into per-profile validation errors.

Analysis v1: corresponding regions, RGB 64×64 LANCZOS, mean absolute channel
difference; similarity = 1 − difference/255, view mean across every region,
warning at ≥0.995. Missing regions are not evaluable. Luminance population stddev
at ≤2.0 warns on low contrast. Neither warning removes views automatically.
