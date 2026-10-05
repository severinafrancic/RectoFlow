# Third-party notices

RectoFlow project code is MIT licensed. Dependencies and bundled runtimes retain
their own licenses. The portable build ships original discovered license/notice
files under `third_party_licenses` and includes a pinned build dependency inventory.

Runtime components: CPython (PSF and incorporated notices), Tcl/Tk, Pillow and its
image libraries, ReportLab, charset-normalizer, uiautomation, comtypes. Build tools:
PyInstaller and its hooks, setuptools, packaging, pefile, pywin32-ctypes, altgraph.

PyInstaller's distribution exception allows an application bundle to use its own
license, subject to dependency licenses; see its
[official license](https://pyinstaller.org/en/stable/license.html).
No ownership or relicensing of third-party code is claimed. Build/release scripts
collect original dependency notices, including Python and Tcl/Tk runtime files.
