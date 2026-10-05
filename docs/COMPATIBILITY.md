# Browser compatibility and evidence limits

Target platform: native Windows 10/11 x64, primary monitor. The portable build
contains CPython, Tcl/Tk and dependencies. Other OSes are not supported.

| Browser | Executable accepted | Screen regions / manual / single | Automatic Next |
| --- | --- | --- | --- |
| Microsoft Edge | `msedge.exe` | Implemented | UIA or calibrated templates |
| Google Chrome | `chrome.exe` | Implemented | UIA or calibrated templates |
| Brave | `brave.exe` | Implemented | UIA or calibrated templates |
| Mozilla Firefox | `firefox.exe` | Implemented | UIA when exposed; calibrated templates otherwise |

The native adapter reads only the selected foreground window's process executable
and creation time. It does not enumerate or adopt other browser processes, restart
the browser, change its profile, modify flags, install extensions, or change security
settings. Screen-pixel acquisition and native mouse input are common to all four.

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

Only Edge was available in the build environment. Chrome, Brave and Firefox were
not installed at the checked standard machine/user locations. Complete live
calibration/capture with real 100/125/150% scaling on each browser is still a required
compatibility verification step. The prerelease does not claim production certification.

## DOM and window boundaries

The optional DOM picker is standard local JavaScript and offers coarse proposals
for the first two regions and Next/progress. Remaining or arbitrary regions are
always available in the screenshot picker. Browser consoles may prevent pasting;
use manual selection rather than weakening browser safeguards.

CSS/device/canvas coordinates stay separate; three visible markers measure the
viewport offset and DPI mapping. Missing/inconsistent markers discard proposals.
Iframe interiors and closed Shadow DOM need manual pixel selection. A full-screen
shield handles normal dynamic/moved/open-shadow frame surfaces, but preexisting
global page handlers are not universally isolated. Use the full manual path for
pages with those handlers. F8/Cancel/timeout removes the temporary DOM interface.

Window/monitor/DPI changes stop acquisition. Process creation time does not prove
same-process HWND lifetime, and native bounds alone cannot prove every tab/layout/
zoom change. Current explicit visual confirmation and selected-pixel checks protect
the initial capture; later page semantics still depend on reliable progress/button
signals. UIA calls may block inside a provider. Protected/DRM content may render black.
Many large regions require memory; no finite machine can promise unlimited storage.
