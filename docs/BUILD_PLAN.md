# Implementation and verification plan

## 0.2 Calibration & Workflow UX

Authoritative implementation contracts are in WORKFLOW_02.md and CONFIGURATION.md.
Three substantive PRs target integration/rectoflow-0.2: calibration/persistence,
profiles/snapshot isolation, immutable review/export. Native config locks bind
Windows file identity (including aliases), backups publish atomically, and each
new schema-3 export uses persisted plan bytes and same-byte image decoding.

Global impact: launcher/calibration → config/profile transactions → per-run
config/template bytes → pinned window/native screenshot/input → ordered PNGs →
frozen capture manifest → lazy review → ExportPlan → renderer → export result.
Producer, consumer and validation ownership follow these explicit boundaries.
PNG/manifest failure preserves originals; missing finalization excludes RUNNING.
Profile staging is hidden on partial failure; locks release on process termination.
No retry of uncertain Next; no automatic capture resume or interrupted finalization.

Main protection has an unmerged smoke PR. Fresh Breaker reviews the integrated
SHA after builder tests/build. Then final PR base/head/CI/conflicts are checked
before owner acceptance. Material changes invalidate affected evidence; merge and
release artifacts require new subject/digest binding. Known four-browser/physical
DPI and owner calibration gaps remain explicit. No OCR/multi-monitor/plugin/grid/
compression/resume expansion in 0.2.

## Historical 0.1 implementation

Requirement: ordered one-to-many screen regions, automatic Next / manual / single-view navigation, final paper/orientation choice, native Windows support for Edge/Chrome/Brave/Firefox, open-source Git project and Windows prerelease.

Canonical repository: this RectoFlow directory; initial branch main. Prior artifact packages remain historical and are not this repository's verification evidence.

Smallest coherent slice: retain the native screen/window adapter and capture loop, generalize ordered region geometry and manifest records, update every coordinate consumer, add a friendly launcher and saved-image PDF export control, package a portable Windows binary. Legacy two-region configurations and run manifests remain readable.

Affected path: screenshot picker -> atomic configuration -> window/occlusion guards -> stable/progress comparison -> ordered PNG generation -> manifest -> paper PDF/export/rebuild. Browser identity comes from the selected foreground window's actual executable, never a browser restart or profile adoption. UIA is primary and calibrated button templates are the explicit alternative. Manual/single-view navigation never invokes a Next click.

State: schema-2 ordered capture records; schema-1 legacy read adapter; absolute paths stay runtime-local and no captured data goes into Git or releases. Partial PNG writes do not become committed capture records. Export decisions do not mutate capture coordinates or image hashes. Config conflict/failure preserves existing bytes.

Assumption challenge: one-region / many-region / reordered / deleted regions must all reach progress, occlusion, PDF and recovery correctly. Changing paper after capture must not distort or crop original PNGs. UIA capability depends on the target page/provider and cannot be inferred from executable name. Frozen executable paths, DLLs, Tcl/Tk and dynamic imports must be tested separately from source imports.

Failure/recovery: unknown button, stalled transition, focus/window/DPI change, ESC/corner or config conflict stops; no repeated click. Saved images and manifest support export without browser navigation. Cancelled end export retains captured data. Browser runtime tests and independent review must state observed coverage and limits; Builder ceiling is INDEPENDENT_REVIEW_PENDING. Publication is user-authorized, with no false acceptance claim.
