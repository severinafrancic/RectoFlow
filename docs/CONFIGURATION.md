# Configuration and persistent records

`config.json` sits next to the source launcher or portable executable. Copy it
to `local-config.json` for personal settings and select that file in the launcher.
Every rectangle is `[x, y, width, height]` in primary-monitor physical pixels.

```json
{
  "regions": [[100, 150, 500, 700], [650, 150, 500, 700], [1200, 150, 400, 700]],
  "navigation_mode": "next_button",
  "browser": "auto",
  "button_rect": [1650, 500, 80, 50],
  "next_point": [1690, 525],
  "progress_rect": [1640, 400, 90, 30],
  "paper_format": "A4",
  "paper_orientation": "portrait",
  "pdf_layout": "separate",
  "confirm_pdf_export": true
}
```

This fragment supplements the full example configuration; do not remove required
timing, output, count and recognition fields from that file.

| Setting | Meaning |
| --- | --- |
| `regions` | Ordered rectangle list: one, two, three or more; no fixed limit on rectangle count. At least one is required to capture content. |
| `navigation_mode` | `next_button`, `manual`, or `none` (single view). |
| `browser` | `auto`, `Edge`, `Chrome`, `Brave`, `Firefox`; selected executable must match. |
| `button_rect`, `next_point` | Required in automatic mode; can be null in manual/single mode. |
| `button_mode` | `uia` or `template`. |
| `button_name` | Optional exact accessibility name. |
| `progress_rect` | Optional stable view/page number; absent uses all actual capture regions. |
| `park_point` | Mouse resting point outside regions/button/progress; avoid screen corner. |
| `expected_spreads` | Optional known number of views, not number of rectangles/PDF pages. |
| `max_spreads` | Hard maximum number of captured views. |
| `paper_format` | A0–A6, Letter, Legal or Original. |
| `paper_orientation` | `portrait` or `landscape`. |
| `pdf_layout` | `separate`: each region is a page; `spread`: regions of one view share a page. |
| `confirm_pdf_export` | Show final saved-image format/confirmation dialog. |

The **+ Bereich** control adds further rectangles. `max_spreads` limits the number
of document views captured during navigation, not the number of rectangles in a
view. Rectangle count has no fixed application limit; available screen space,
memory and storage still determine what a particular computer can capture.

Old configurations without `regions` use `left_rect` and explicit `right_rect`,
or the legacy equal-size adjacent fallback. The calibrator can migrate to a
one-to-many list; unknown configuration fields are preserved. `regions`, when
present, overrides legacy fields. Atomic saves detect prior-byte conflicts;
they do not provide a filesystem CAS guarantee against a noncooperating writer
after the final digest check.

New 0.2 manifests use schema 3 and retain the historical `pairs` array name for
ordered views. Schema 1/2 remain legacy-readable. Filenames depend on the original
config representation: ordered `regions` use `000001_region_001.png` onward;
legacy configs retain left/right names. Arbitrary image paths are rejected.

Config saves serialize RectoFlow processes through native locks. All verified
`config.backup.<UTC>.<id>.json` files are retained. Restore creates a backup of the
current config before restoring exact selected bytes. Managed profile locks live
in `data/.locks/`, independent of profile folders. Direct configs use adjacent locks.

Capture ends with `COMPLETE` or `STOPPED` and `finished`, atomically persisted.
Those manifest bytes and original PNGs are frozen before review. No new PDF fields
are appended. `profile` is null for direct configs or contains UUID/config/template
hashes from the actual isolated snapshot.

Every schema-3 export uses `exports/<export-id>/export_plan.json`, `result.json`
and `document.pdf`. Plan schema 1 binds the source-manifest hash, unique selected
view indices and effective paper/orientation/layout/DPI. Persisted plan bytes are
hashed and parsed once. Each image is read once, hashed, decoded from those bytes,
then dimension-checked and rendered. Result schema 1 binds plan/manifest hashes;
COMPLETE includes the finished PDF hash. Export failure never changes capture status.

For schema 3, `--rebuild` without a plan persists an all-views plan before rendering.
With `--export-plan`, that plan is authoritative and format overrides are rejected.
Legacy rebuild may use its historical output names, preserving compatibility.

RUNNING is never exported or silently finalized. The UI distinguishes active writer
from interrupted/recovery-required or unknown activity. Fully recorded views remain
on disk. There is no interrupted-run finalization or navigation resume in 0.2.
