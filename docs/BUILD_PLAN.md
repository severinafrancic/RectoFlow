# Implementation and verification plan

Requirement: ordered one-to-many screen regions, automatic Next / manual / single-view navigation, final paper/orientation choice, native Windows support for Edge/Chrome/Brave/Firefox, open-source Git project and Windows prerelease.

Canonical repository: this RectoFlow directory; initial branch main. Prior artifact packages remain historical and are not this repository's verification evidence.

Smallest coherent slice: retain the native screen/window adapter and capture loop, generalize ordered region geometry and manifest records, update every coordinate consumer, add a friendly launcher and saved-image PDF export control, package a portable Windows binary. Legacy two-region configurations and run manifests remain readable.

Affected path: screenshot picker -> atomic configuration -> window/occlusion guards -> stable/progress comparison -> ordered PNG generation -> manifest -> paper PDF/export/rebuild. Browser identity comes from the selected foreground window's actual executable, never a browser restart or profile adoption. UIA is primary and calibrated button templates are the explicit alternative. Manual/single-view navigation never invokes a Next click.

State: schema-2 ordered capture records; schema-1 legacy read adapter; absolute paths stay runtime-local and no captured data goes into Git or releases. Partial PNG writes do not become committed capture records. Export decisions do not mutate capture coordinates or image hashes. Config conflict/failure preserves existing bytes.

Assumption challenge: one-region / many-region / reordered / deleted regions must all reach progress, occlusion, PDF and recovery correctly. Changing paper after capture must not distort or crop original PNGs. UIA capability depends on the target page/provider and cannot be inferred from executable name. Frozen executable paths, DLLs, Tcl/Tk and dynamic imports must be tested separately from source imports.

Failure/recovery: unknown button, stalled transition, focus/window/DPI change, ESC/corner or config conflict stops; no repeated click. Saved images and manifest support export without browser navigation. Cancelled end export retains captured data. Browser runtime tests and independent review must state observed coverage and limits; Builder ceiling is INDEPENDENT_REVIEW_PENDING. Publication is user-authorized, with no false acceptance claim.
