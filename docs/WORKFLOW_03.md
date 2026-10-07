# RectoFlow 0.3: Document Ingestion & Rectification

Status: approved design; qualification spike only. No production ingestion,
rectification UI, OCR, new export, migration, merge or release is implemented here.
The 0.2 browser/capture/profile/schema-3/export contracts remain unchanged.

## Container boundaries

CONTAINER_PAGE_1

For sources with authoritative container page boundaries (PDF pages, TIFF frames),
RectoFlow MUST preserve a full-frame container-derived page proposal.
Visual page detection MAY provide additional crop/split proposals but MUST NOT
silently replace the container page boundary.

PDF/TIFF default: FULL_FRAME / CONTAINER_PAGE, with optional additional visual
crop/split proposals. Photo/arbitrary image default: visual detection; manual
full-frame always possible. Container proposals bind source/frame identity,
verified raster SHA-256, dimensions, and corners in TL/TR/BR/BL order. The PDF
frame includes explicitly recorded effective bounds/rotation. No detection result
may delete that proposal. User exclusion is explicit. Container provenance is
not automatic acceptance or proof that all visible content is a document page.

## Approved future product boundary

Sources stay immutable; source artifact -> source frame -> 0..N proposals ->
accepted normalized pages. Verify stored bytes before decoding those same bytes.
Each transform binds provider/version, algorithm/configuration, input/output
hashes, matrices, dimensions and time. Full-resolution candidate PNGs exist before
acceptance; publication uses exactly their accepted bytes, never an unseen rerender.
Editing invalidates acceptance. Plans bind actual persisted bytes. New schemas
are type-qualified schema 1; capture schemas and ExportPlan v1 do not migrate.

Natural file ordering, manual ordering, EXIF/alpha/ICC handling, local password
transport, bounded workers, immutable final records and fail-closed partial runs
are required in the later source/artifact slice. No RUNNING run becomes COMPLETE
after writer death. No automatic retries, provider changes or inter-run cache.

## Qualification before PR 1

Exact candidates: pypdfium2 5.14.0, opencv-python-headless 5.0.0.93, numpy 2.4.6;
existing Pillow/PyInstaller lock. Source Python3.11 and Windows-build Python3.12.
No substitutions. Downloads are hashed and checked against version-specific PyPI
metadata before offline installation in an ignored, isolated spike environment.

The own worker starts suspended, is assigned to a memory-limited Job Object,
then resumed before native provider imports. Timeout/cancel/parent exit terminate
only own workers. Job Objects are not an exploit/security sandbox. Probe secret
passwords never appear in argv, logs, JSON results or stored plaintext fixtures.

PDF geometry, inherited boxes, UserUnit, mixed sizes, corrupt/encrypted inputs,
TIFF frames, container-policy, perspective/deskew ground truth, worker refusal,
memory limit, timeout/cancel/parent exit and real relocated frozen execution are
mandatory. DLL hashes, complete shipped wheel license materials, cold start,
peak RAM, runtime and disk measurements accompany results.

Limit candidates: 512MiB/file, 2GiB source bytes/run, 500 frames/run, 64MP and
12000px per raster/output, one full-size task, 2GiB worker, 60s task timeout,
10GiB run budget plus512MiB free reserve. These are candidates, not qualified
guarantees. The spike explicitly separates tested envelopes and untested limits.
Raster scale300/72 is not a physical DPI guarantee when UserUnit is unknown.

## Evidence and authority

Commit harness/contract/workflow first; execute on that subject SHA/tree; commit
report separately. Each material harness fix makes a new subject and invalidates
affected earlier evidence. Local/source/hosted/frozen evidence stays separate.
Builder verdict is GO, REQUIRED_CHANGE or NO-GO, never independent acceptance.
Missing mandatory proof cannot be a pass. GO unlocks PR1; it does not authorize
product implementation within this spike, owner acceptance, merge or release.

Keep full logs/artifacts ignored; publish a durable digest-bound summary under
docs/evidence. Synthetic fixtures only. Existing evidence remains immutable.
