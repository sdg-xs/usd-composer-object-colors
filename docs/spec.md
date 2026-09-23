# Agreed implementation scope

Source: `forma-object-colors-codex-handoff.md`, supplied by the user on 2026-09-21, plus the decisions from the design interview.

- Implement a local Python Kit extension in `object.color`, using the installed Composer runtime.
- Color the whole stage with one active criterion: Property, File, or Model when provenance exists.
- Use a native Composer panel, searchable source-qualified properties, value swatches, logical-object counts, and a fixed palette.
- User update on 2026-09-22: use final editable Xforms as objects and ignore mesh-level metadata and opacity. Apply one solid color to each Xform's whole subtree, including glass. Disable restores the original appearance.
- Exclude final Xforms containing lights or cameras, including instanced rigs, to preserve sky and environment materials.
- Keep values typed. Missing values are distinct from the literal string `Unassigned`.
- Display 100 values in deterministic order, with additional values grouped as Unmapped.
- Keep palette assignments stable through refreshes and model content changes.
- No color and Disable must reveal the original appearance, including original textures and bindings.
- User update on 2026-09-22: remove the Shared templates section, including template loading and JSON import and export controls. Retain scene persistence.
- Save and reopen must restore the active scheme and enabled state. Source geometry and materials must remain intact.
- Follow host undo and redo conventions. Stage replacement and shutdown must remove stale overrides and subscriptions.
- Batch long work so Composer can continue processing frames.
- Verify grouping and persistence with focused tests. Verify material and lifecycle behavior in Kit, and report measured performance and limitations.
- Use generated test files and an isolated process for rendering checks. The user requested inspection and updates of the loaded extension in the open Composer on 2026-09-22. Do not save production scenes during verification.

The original handoff also requests installation instructions, preset storage documentation, a tested runtime version, and an honest record of unexecuted checks.
