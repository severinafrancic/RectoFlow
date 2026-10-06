# Browser compatibility and evidence limits

Target platform: native Windows 10/11 x64, primary monitor. The portable build
contains CPython, Tcl/Tk and dependencies. Other OSes are not supported.

## Contract for 0.2

Support and evidence are separate dimensions, not a single promotion ladder:

| Term | Meaning |
| --- | --- |
| IMPLEMENTED | The adapter accepts the target and common product paths exist. Supported does not mean runtime-verified. |
| SYNTHETICALLY_VERIFIED | Named unit/contract/synthetic tests pass for the exact reviewed subject; no real target composition is implied. |
| RUNTIME_VERIFIED | A named actual environment/path has digest-bound execution evidence. It does not extend to untested modes, pages, browsers, DPI or binaries. |
| UNVERIFIED_RUNTIME | Real E2E evidence for this target/path is absent or incomplete; not a claim of incompatibility. |
| UNSUPPORTED | Outside the implemented product contract, including other OSes and multi-monitor capture. |

| Browser | Executable / support | Contract evidence | Runtime evidence |
| --- | --- | --- | --- |
| Edge | `msedge.exe` / IMPLEMENTED | SYNTHETICALLY_VERIFIED: identity and common paths | RUNTIME_VERIFIED for named 96-DPI paths below; other combinations UNVERIFIED_RUNTIME |
| Chrome | `chrome.exe` / IMPLEMENTED | SYNTHETICALLY_VERIFIED: identity and common paths | UNVERIFIED_RUNTIME: real browser E2E not verified |
| Brave | `brave.exe` / IMPLEMENTED | SYNTHETICALLY_VERIFIED: identity and common paths | UNVERIFIED_RUNTIME: real browser E2E not verified |
| Firefox | `firefox.exe` / IMPLEMENTED | SYNTHETICALLY_VERIFIED: identity and common paths | UNVERIFIED_RUNTIME: real browser E2E not verified |

| Windows scale / DPI | Coordinate support | Physical desktop composition |
| --- | --- | --- |
| 100% / 96 DPI | IMPLEMENTED, SYNTHETICALLY_VERIFIED | RUNTIME_VERIFIED only for documented Edge runs |
| 125% / 120 DPI | IMPLEMENTED, SYNTHETICALLY_VERIFIED marker/coordinate mapping | UNVERIFIED_RUNTIME |
| 150% / 144 DPI | IMPLEMENTED, SYNTHETICALLY_VERIFIED marker/coordinate mapping | UNVERIFIED_RUNTIME |

For this early prerelease, missing real Chrome/Brave/Firefox or physical 125%/150%
runs are **non-blocking compatibility evidence**, not merge requirements. No
cross-browser/DPI production certification or universal page-load detection is
claimed. Required correctness/safety, current tests/CI, independent review and
exact PR head/base verification remain gates; see [VERIFICATION.md](VERIFICATION.md).

The picker enumerates top-level browser windows for explicit user selection.
The adapter pins the selected HWND, executable, process creation identity and a
window-lifetime marker; it never substitutes another HWND. Normal capture does not
restart browsers, adopt profiles, install extensions or change security settings.
Screen-pixel acquisition and native mouse input are common to all four.

Chromium enabled native Windows UIA by default from Chrome 138 according to the
[Chromium team](https://developer.chrome.com/blog/windows-uia-support-update).
Firefox's IsEnabled implementation is recorded in
[Mozilla's issue tracker](https://bugzilla.mozilla.org/show_bug.cgi?id=1889290).
These upstream facts do not prove that every page/button/provider is accessible.
An unavailable, offscreen, ambiguous or unreachable control yields `unknown` and
stops. It never becomes a false normal end. No automatic fallback guesses a button.

## Executed coverage versus support

Contract tests exercise all four executable identities, wrong-browser rejection,
one/two/many region producer/consumer paths, UIA/template branches, manual/single
navigation and paper export. Source and frozen-executable tests are recorded under
verification/release evidence. These are not four real browser end-to-end tests.

Contract coverage includes four executable identities/mismatches
(`tests/test_regions.py`), readiness/native guards, unknown UIA/template states,
snapshot bytes, region ordering and export. Synthetic marker mapping at
1/1.25/1.5 is in `tests/test_calibration.py`; it is not a physical DPI run.
The shared screenshot/input/template/capture/export architecture has no separate
browser capture backend. UIA remains conditional on each page/provider; Firefox
and Chromium can expose different controls. Identity tests cannot prove reliability.

## Bound Edge evidence and remaining uncertainty

Historical real evidence is bound to source
`e7627a6a3fcee822236c82777d451fbed963b9ea`, tree
`d6bd848ecf51a5088f59ac1bcc405e7a106e714d`, RC ZIP SHA-256
`febf2e1184ac8cdaeec8e952ef8726f7c78356721abfed3fe074d1f93baaa4f6`,
EXE SHA-256 `65cf61ca51330254003f7fd99e406a2769714090b1b52fe139aca29544113ffd`.
Independent Edge report SHA-256:
`5267f556c33f8771fa052b2a867381e8145fd11b083ee8f04fac5236e5c2d324`.

The published EXE ran with an owned synthetic Edge guest page at observed
96 DPI/100%. Genuine window selection, screenshot calibration, Next/progress/click
point, final preview/save/start confirmation, three views/two regions, exactly two
Next clicks, UIA and real enabled/disabled template baselines were exercised.
Actual review reordered/excluded views and exported A5 landscape; immutable
originals, PDF pixels/order/geometry and digest provenance were verified. Nochange,
4200-ms temporary-disabled **template**, unknown-template and interrupted-RUNNING
rebuild refusal cases were exercised. Earlier source Edge fixtures inject owned
window selection and are not interactive calibration evidence.

A later UIA attempt returned another top-level HWND of the same owned Edge PID.
RectoFlow safely stopped with zero captures/clicks. Cause remains unresolved;
this is neither proven platform failure nor a confirmed product defect. Reliable
handling of that provider state is UNVERIFIED_RUNTIME. Do not claim the UIA
temporary-disabled case passed because the template case passed.

Profile-management GUI lifecycle, optional DOM one-use/replay GUI composition and
live focus/move/resize/target-close adversarial cases remain unverified. Their
correctness contracts remain required and test-covered; full live matrix
certification is not a 0.2 gate. Historical reports retain their original BLOCKED
verdicts. A new reviewer must explicitly reevaluate FBR-02-PROOF-004 under this
owner-authorized contract; the Builder cannot close it by editing this document.

New source/package evidence must name its own SHA/digest. Unchanged runtime member
bytes may explain continuity with historical Edge evidence, but do not turn an old
EXE run into execution of a new package. README demo screenshots are synthetic UI
documentation, never runtime verification evidence.

## DOM and window boundaries

The optional DOM picker is standard local JavaScript and offers coarse proposals
for the first two regions and Next/progress. Remaining or arbitrary regions are
always available in the screenshot picker. The helper uses a temporary local
bookmarklet and downloaded JSON file, not the clipboard. CSP/browser policies may
block execution; use manual selection without weakening browser safeguards.

CSS/device/canvas coordinates stay separate; three visible markers measure the
viewport offset and DPI mapping. Missing/inconsistent markers discard proposals.
Iframe interiors and closed Shadow DOM need manual pixel selection. A full-screen
shield handles normal dynamic/moved/open-shadow frame surfaces, but preexisting
global page handlers are not universally isolated. Use the full manual path for
pages with those handlers. F8/Cancel/timeout removes the temporary DOM interface.

Window/monitor/DPI changes stop acquisition. The HWND marker detects its destroyed
and recreated lifetime; native bounds alone cannot prove every tab/layout/
zoom change. Current explicit visual confirmation and selected-pixel checks protect
the initial capture; later page semantics still depend on reliable progress/button
signals. UIA calls may block inside a provider. Protected/DRM content may render black.
Many large regions require memory; no finite machine can promise unlimited storage.
