# Changelog

## Unreleased

## 0.2.0 — Calibration & Workflow UX (prerelease candidate)

- Free capture geometry, explicit browser window picker and strict identity/focus ordering.
- Native cross-process config/profile locks; retained byte-exact backups and restore.
- Experimental single-use DOM bookmarklet/JSON file transport without clipboard writes.
- Indexless UUID profiles, isolated config/template snapshots and manifest provenance.
- Region duplicate/reference alignment/equal-size/direct-right helpers.
- Frozen schema-3 capture manifests; lazy view review, exclusions and reordering.
- Deterministic similarity/contrast warnings; unique ExportPlan views and linked PDF results.
- Unified schema-3 GUI/CLI export; RUNNING runs remain recovery-required.
- Windows console tolerates Unicode browser titles; relocated EXE tests cover legacy/new exports.
- Main PR/Windows ruleset verified by an unmerged documentation smoke PR.

Independent review and owner acceptance remain separate from builder tests/CI.

- Clarify that one, two, three or more rectangles can be selected without a fixed
  rectangle-count limit. Replace mathematical wording in the README; capture
  behavior is unchanged.

The initial prerelease includes the independent-review fix that binds capture
order in the final start confirmation, with regression coverage for reordered
two-region and many-region selections.

## 0.1.0 — initial prerelease

- One, two or many ordered screenshot regions; add/delete/reorder controls.
- Automatic Next, manual navigation and single-view acquisition.
- Window executable support for Brave, Edge, Firefox and Chrome.
- Editable paper-aligned calibration with explicit final/start confirmations.
- Saved-image end export with A0–A6, Letter, Legal, original size and both orientations.
- Separate/spread PDF layout, image hashes, ordered manifests and legacy recovery.
- Portable Windows x64 package, source archive, documentation and MIT license.

Real multi-browser native composition remains explicitly unverified; this is a prerelease.
