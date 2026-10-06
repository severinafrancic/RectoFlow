# Reproducible real-UI demo assets

On an unlocked native Windows developer desktop with the pinned dependencies:

```powershell
python scripts/generate_readme_assets.py
python scripts/generate_readme_assets.py --check
```

Outputs are `docs/assets/rectoflow-calibration.png` and
`docs/assets/rectoflow-review.png`. `--check` generates twice in isolated system
temporary directories, requires byte-identical PNGs and checks required real widget
states. The fixed Windows Arial/clam theme and Tk scaling provide same-environment
repeatability. Different Windows/font/Tk versions may render differently; this is
not a cross-host byte-identity promise. CI validates committed PNGs structurally.

The generator instantiates the actual RectanglePicker and export_dialog. It uses
deterministic PIL content labelled SYNTHETIC DEMO, two regions, Next and progress.
Three temporary synthetic views include an identical adjacent pair so the actual
analysis produces a similarity warning. Native widget events select the rows.
Export controls remain visible; the generator never presses confirmation/export.

Windows PrintWindow renders only each explicitly owned Tk client window to its
own memory DC. There is no screen/desktop capture, browser, network, external image,
clipboard operation, user config, profile or real document. Window borders,
taskbar, neighbouring windows and titles are outside the client image. The task
briefly creates its own mapped Tk windows and closes them in finally blocks.

The existing review component requires a saved manifest; its minimal synthetic
schema-3 fixture and images exist only in a system TemporaryDirectory and are
removed on normal completion. No runtime capture or export is started. No manifest,
plan, result, capture folder or user data is written to docs/assets. An interrupted
developer task may leave its ordinary system-temp fixture; it is not capture evidence.
Every asset contains a visible synthetic-demo banner; README captions reinforce
that these are documentation examples, not Edge/browser/DPI runtime verification.
