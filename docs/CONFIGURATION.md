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
| `regions` | Ordered nonempty rectangle list; no fixed two-region limit. |
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

Old configurations without `regions` use `left_rect` and explicit `right_rect`,
or the legacy equal-size adjacent fallback. The calibrator can migrate to a
one-to-many list; unknown configuration fields are preserved. `regions`, when
present, overrides legacy fields. Atomic saves detect prior-byte conflicts;
they do not provide a filesystem CAS guarantee against a noncooperating writer
after the final digest check.

New one-to-many manifests use schema 2 and keep the historical `pairs` array name
for the ordered per-view records. Each record may now contain any positive
number of images. Filenames are `000001_region_001.png`, then region 002, and so
on. Legacy schema-1 records retain `left` / `right` filenames. PDF recovery checks
exact expected names, order, image hashes and dimensions; arbitrary manifest paths
are rejected. Capture coordinates do not change during final PDF export.

`COMPLETE` describes successful acquisition. If final PDF export is cancelled,
`pdf_export_status` is `DEFERRED`; saved PNGs and manifest remain. `STOPPED` keeps
the complete records before failure and may generate a `gesamt_TEILSTAND.pdf`.
Rebuild/export never resumes browser navigation.
