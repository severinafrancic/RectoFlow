# RectoFlow 0.3 qualification spike: REQUIRED_CHANGE

Producer: **BUILDER**. This report is not independent review, owner acceptance,
production certification, or authorization to start the product implementation.

The requested branch and spike have been implemented and published. The exact
provider versions, worker primitives and standalone packaging pass the exercised
cases. **The complete qualification verdict is REQUIRED_CHANGE**, because the
candidate input/batch/disk envelopes still lack mandatory boundary evidence.
Green primitive checks do not supply that missing proof. PR 1 is not unlocked.

## Subject and scope

| Binding | Value |
|---|---|
| Repository | severinafrancic/RectoFlow |
| Canonical checkout | D:\Projekte\RectoFlow |
| Branch | feature/rectoflow-0.3-document-ingestion |
| Base SHA | 05ae40615a5b62227857e3477cfd484a116f3a5a |
| Base tree | 81f443ccd1409363c77caa5325557b30b1b59a28 |
| Tested subject | 606550d2541f7b00554786c721a291d1df14070c |
| Tested tree | 8b2796290e9c6efd3fe70a27510edf9edff80aba |
| Authority | Qualification-only Builder evidence |
| Lifecycle | INDEPENDENT_REVIEW_PENDING; qualification REQUIRED_CHANGE |

This report and its sidecars are published in a **separate evidence commit**.
Its HEAD is not substituted for the tested subject above. A documentation-only
evidence commit does not cause an older test to become a test of that new SHA.

Publication correction: Git normalized CRLF in JSON sidecars in the first
evidence commit ef51cbd428d2c629c2702a078814a9b0cf3e934e. Those stored blobs did
not match the original-byte digests in the evidence index. A follow-up evidence
commit applies a folder-local `*.json -text` rule and republishes the retained
original bytes. Every stored Git blob is then checked against that index. The
first commit remains in history; it is not valid byte-preservation evidence.
This correction changes evidence publication only, not the tested spike code.

Compared with the base, the material subject adds only WORKFLOW_03, the isolated
spike scripts/requirements and the dedicated qualification workflow. Product
sources, existing dependency/build locks, browser/capture/export behavior and
the standard release workflow are unchanged. No production ingestion,
rectification UI, browser installation, merge or release occurred. The historical
C checkout, original main and earlier evidence/output folders remain intact.

CONTAINER_PAGE_1 is recorded in WORKFLOW_03. Synthetic PDF/TIFF policy probes
retain a hash-bound full-frame proposal when visual detection gives no proposal
or an additional proposal. Acceptance stays REVIEW_REQUIRED. These probes are
not a product adapter or a general visual detector.

## Actual executions

| Composition | Provider/worker cases | Product regression |
|---|---:|---:|
| Native local Windows, Python 3.12.14 source | 22/22 PASS | 129/129 PASS, 8.501s |
| Native local relocated standalone EXE, Python 3.12.14 | 22/22 PASS | Separate source regression above |
| Hosted Windows, Python 3.11.9 source | 22/22 PASS | 129/129 PASS |
| Hosted Windows, Python 3.12.10 source | 22/22 PASS | 129/129 PASS |
| Hosted Windows relocated standalone EXE, Python 3.12.10 | 22/22 PASS | Separate source regression above |

[Hosted run 37670215300](https://github.com/severinafrancic/RectoFlow/actions/runs/37670215300)
completed successfully on the tested subject. Python 3.11 was not run locally.
Both frozen suites execute actual relocated workers with a clean PATH, rather
than merely inspecting an EXE or assuming a successful build implies execution.
This newly built spike EXE executed locally; no old App-Control denial was retried
or policy changed, and historical product-EXE evidence remains historical.

The 22 cases exercise exact provider imports; bound-byte PDF geometry with
CropBox/MediaBox, inherited boxes, rotation and mixed sizes; correct and wrong
passwords; corrupt PDF/image refusal; TIFF frame order; oversized image/PDF and
501-page preflight probes; injected partial-write refusal; known perspective and
deskew geometry; memory refusal, timeout, cancellation, worker crash and own
parent death; and 1/12/24/48/64-MP RGB transformation/PNG round trips.

Passwords are generated in memory, sent through the own worker pipe, and not
persisted in argv, logs or report requests. The tested encryption fixture uses
RC4-128; the result does not cover every PDF encryption variant.

Workers start suspended and join a Job before native decoder imports. Tests use
only own processes. Job Objects bound resources/lifetime; they are **not a
security sandbox**. Memory refusal was exercised with a 128-MiB per-process
limit; successful larger cases use the candidate 2-GiB per-process limit. This
does not promise a 2-GiB aggregate limit across arbitrary descendants.

The perspective golden has corner error 6.77e-14 pixels and image MAE 3.642.
The 7-degree deskew fixture estimates -6.900 degrees with residual approximately
0.0000025 degrees. General photograph quality/detection is outside this spike.

## Versions, actual wheels and package

No provider substitution occurred: pypdfium2 **5.14.0**, OpenCV headless
**5.0.0.93** (runtime cv2 5.0.0), NumPy **2.4.6**, existing Pillow **12.3.0** and
PyInstaller **6.22.3**. PDFium is 156.0.8076.0 with no V8/XFA flags.

Every actually downloaded wheel was checked against version-specific PyPI
metadata before offline installation. Full wheel inventories and licensing-member
hashes are retained in the JSON sidecars. Principal Windows-x64 wheel SHA-256:

| Wheel | SHA-256 |
|---|---|
| pypdfium2 5.14.0 | 149fd5c6397b8df8bf7911a93506eff0be874f877afe7ac936cf5d37d21a6a06 |
| OpenCV headless 5.0.0.93 | 829717b6a95554f273e49e357cee3b3a2a26b6f4842fbc1bed2b45bdd8f87e0e |
| NumPy 2.4.6, Python 3.12 | d8e8286dd7cea7895157318d1b91cdacac64c479f3cbc8dce548331728484751 |
| NumPy 2.4.6, Python 3.11 | 1e254a00cdf42b1e4d5b3d68d33af63268d41340d8885df2ab6470f2e1500147 |

The local standalone ZIP is **86,313,094 bytes**, unpacks to **218,059,943 bytes**
and contains **101 native EXE/DLL/PYD members**. ZIP SHA-256:
`15b74e97e1108db740b7cab46e3d196828d8fcfbca24253b7cf8acb0e77e3fa8`.
Local initial provider-worker startup was 3.752s on this run; later starts vary
with caches. This is an initial launch measurement, not a universal cold-cache
startup bound. The hosted build has its own distinct hashes/size/Python patch
version in hosted-build.json; local and hosted binaries are not called identical.

Package inventories bind all members, embedded source hashes, provider wheels
and original wheel license/notice/copying materials plus the CPython license.
This is a shipped-material inventory, not blanket legal certification. Downloaded
hosted artifact ZIPs were compared with GitHub's artifact digests, then every
bundle member and embedded source hash was verified against the tested commit.
The compressed artifacts/binaries remain ignored local/Actions outputs; this is
not a RectoFlow 0.3 release.

## Measured envelope and recommendation

Local Python 3.12 source, one RGB noise task at a time, including PNG write, hash
and decoding **the same persisted bytes**, with pixel equality:

| Requested MP | Actual dimensions | Elapsed worker seconds | Peak working set MiB | Peak process commit MiB | PNG bytes |
|---:|---|---:|---:|---:|---:|
| 1 | 1154 x 866 | 0.402 | 70.2 | 277.9 | 3,163,960 |
| 12 | 4000 x 3000 | 1.403 | 282.6 | 490.7 | 37,981,629 |
| 24 | 5656 x 4243 | 2.476 | 513.1 | 721.6 | 75,955,360 |
| 48 | 8000 x 6000 | 4.571 | 975.0 | 1184.7 | 151,918,351 |
| 64 | 9237 x 6928 | 5.858 | 1282.8 | 1492.8 | 202,536,262 |

The near-64-MP case has 63,993,936 pixels. It does not prove every aspect ratio,
exact boundary, decoder or a maximum 12,000-pixel edge. The source output folder
contains 471,743,492 bytes. Full local/frozen/hosted measurements are in
evidence.json and the unchanged per-composition reports.

The real worker's native memory and Job committed peaks are measured separately
from the venv launcher. The current decode case reaches about 1.49 GiB committed
memory, leaving only about 0.51 GiB below the candidate 2-GiB cap. Recommendation:
retain single-task Job supervision; **qualify 48 MP as an initial candidate for
the fuller future pipeline**, rather than assuming the 64-MP stress result
survives extra detection/normalization buffers. This is a recommendation for new
qualification, not a secretly adopted product cap.

512 MiB per input, 2 GiB source bytes/run, a 500-frame processing batch, and a
10-GiB run budget plus 512-MiB free reserve remain unqualified. The 501-page
preflight proves the probe's refusal behavior; it does not measure processing
500 frames. Injecting ENOSPC before publication proves temporary-output behavior
under that injected error, not actual full-disk/power-loss durability. The 0.5s
timeout/cancel probes prove termination wiring; they are not a general throughput
guarantee for arbitrary hostile PDFs.

One provider limitation is explicit: pypdfium2 page size/render scale is in PDF
canvas units. Its installed page.py documents that PDFium does not expose the
UserUnit factor. The UserUnit=2 fixture renders 400x200 at scale 1. This passes
the documented canvas-unit policy; it supplies no physical-DPI guarantee. Future
physical-DPI behavior needs a separately qualified policy. This limitation does
not invent an additional acceptance blocker for the existing canvas-only probe.

## Retained failures and assumption challenge

Earlier failed subjects/runs are preserved, not overwritten:

- 8143e10f / run 37668097792: OpenCV 5 HoughLinesP result-shape mismatch. Original
  redirector RSS numbers were invalid for worker RAM and are not used here.
- 65eb5262 / run 37668840843: the resampled-line segment threshold made the HoughP
  probe unreliable. Standard HoughLines replaced it; golden tolerances remained.
- e5a11679 / run 37669316316: 18 primitives passed, but PNG redecode and four
  failure/preflight cases were absent. Its smaller RAM numbers do not qualify the
  current path. Subject 606550d adds the missing cases and reruns all compositions.

The most damaging hidden assumption was treating green primitive/resource checks
as qualification of all planned budgets. The current verdict explicitly refuses
that inference. Source hashes and native member hashes were verified, main was
rechecked publicly, and the diff is limited to the approved spike slice. No old
failed/blocked evidence became an independent pass. No independent reviewer or
owner authority is claimed by this Builder.

## Bounded next action

**Q03-LIMIT-001 — REQUIRED_CHANGE:** stay on this branch and extend only the
qualification probes for selected file/source-count/batch/disk budgets. Either
qualify the existing candidates at and beyond their boundaries, or obtain an
explicit narrower-envelope decision and qualify those values. Include aggregate
source/storage behavior and refusal/partial-write evidence; preserve prior runs.
Commit that changed harness as a new subject, run the affected source/frozen/
hosted checks, then publish new evidence separately. Do not begin production PR 1
until that result is GO. Independent Fresh Breaker and owner acceptance remain
later boundaries; this task does not authorize merge or release.

Machine-readable details, sidecar hashes, boundary audit and Builder assumption
challenge: [evidence.json](evidence.json). Reproduction commands and isolation:
[spike README](../../../scripts/spike03/README.md).
