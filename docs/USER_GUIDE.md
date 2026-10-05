# User guide

The launcher and interactive controls are in German. See [README.de.md](../README.de.md)
for the complete normal workflow. All acquisition uses the primary screen.

## Useful commands

```powershell
RectoFlow.exe --calibrate
RectoFlow.exe --preview
RectoFlow.exe --capture
RectoFlow.exe --position
RectoFlow.exe --rebuild "aufnahmen\run_..." --paper A5 --orientation landscape --layout separate
RectoFlow.exe --version
RectoFlow.exe --self-check
```

Use `--config local-config.json` to select a personal configuration. Run `--capture`
explicitly from the CLI; opening the executable without arguments opens the launcher.
The legacy `edge_capture.py` entry point remains available from source.

## UIA or image templates

UIA queries the fresh control at the Next click point. Set `button_name` only when
the exact accessibility name is known and stable. Never treat `unknown` as disabled.

If the provider cannot expose the button, use `button_mode: "template"`, set a tight
button rectangle, and explicitly record both states:

```powershell
RectoFlow.exe --calibrate enabled
RectoFlow.exe --calibrate disabled
```

Show the enabled button for the first command and the real disabled final button for
the second. Both snapshots must match the saved button rectangle. Existing templates
are not overwritten. Hover/tooltips must not cover the button. Similar states fail
closed rather than guessing. If neither recognition method distinguishes the end,
choose manual navigation. A disappearing button is `unknown`, not proved disabled.

## End export and recovery

After successful calibrated acquisition, the final dialog uses saved PNGs. Select
paper and orientation, inspect the representative first-page preview, then confirm
PDF creation. Separate layout exports every region as a page; spread puts each view's
regions side by side. Original dimensions use `pdf_dpi` for PDF points. All other
formats use true paper millimetres with proportional fit and optional white margins.

Cancel keeps PNGs and `manifest.json`. The launcher can reopen any run manifest for
another confirmed export. CLI rebuild with format options produces a new uniquely
named PDF and leaves the recorded capture configuration/PNGs unchanged. Legacy
rebuild without options preserves its existing no-overwrite filename behavior.

## Failure codes and troubleshooting

Calibration messages include CALIBRATION_CANCELLED, TARGET_WINDOW_LOST,
DOM_PICKER_FAILED, COORDINATE_TRANSFORM_FAILED, SCREENSHOT_FAILED,
INVALID_RECTANGLE and CONFIG_WRITE_FAILED. RECALIBRATION_REQUIRED identifies
stale window/monitor/DPI state. No failed transition triggers another Next click.

A changed selected image after confirmation prevents the initial capture. Avoid
animations, blinking carets, hover and overlays in selected regions. Calibrate again
when changing zoom/layout. Progress should be a page/view number that updates only
when the new view is ready; a clock/spinner is unsuitable. A temporarily disabled
Next button can resemble the end, so known view counts are useful.

Captured PNGs/metadata stay in the configured output directory. Partial writes are
not added as complete records. There is no automatic restart or resume of navigation.
Use rebuild for saved records and choose the correct start view for a new acquisition.
