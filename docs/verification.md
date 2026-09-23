# Verification results

Verified on 2026-09-22 using Kit `110.2.0+feature.342835.698af100.gl`, OpenUSD 25.11, Windows, and an NVIDIA RTX 4070 Laptop GPU.

## Automated checks

`run-verify.ps1` runs 23 focused unittest cases against the installed USD libraries. They cover typed grouping, persistence, final-Xform discovery, inherited properties, ignored mesh metadata, instance source exclusion, sky and camera material preservation, instanced light rig exclusion, solid coloring of mixed-opacity instances and subsets, MDL-only source materials, collection priorities, rejected-binding cleanup, and restoration. Preset serialization tests remain for the underlying storage helpers.

`run-typecheck.ps1` runs mypy with `check_untyped_defs` on the extension. Kit and USD APIs do not ship complete type stubs, so the runtime checks remain necessary.

`run-verify-kit.ps1` starts an isolated Kit app with the actual extension. It renders a generated scene containing native instances with glass and opaque parts and a dome light under an Environment Xform. It changes one instance and measures red pixels before coloring, during coloring, and after Disable. The runner verifies that Kit loaded the checkout being tested. The controller check verifies that the sky receives no material binding and compares background pixels before and during coloring.

The Kit workflow also checks rendered swatch edits and No color, undo, redo, stale palette rejection, File grouping, unavailable Model metadata, incompatible templates, enabled and disabled save/reopen, stage replacement, and shutdown. It checks that the old visualization layer is released and that shutdown leaves no active overrides.

## BS17 coloring regression

The checkout examined on 2026-09-22 had collection-only bindings and source-opacity checks despite the solid-Xform behavior described above. The existing RTX test failed with zero red pixels before and after coloring. Four existing USD tests failed, and a new MDL-only material test reproduced another skipped-object case.

The fix binds one opaque material directly to each target Xform and uses expanding collections for ancestor binding priorities. All 23 USD tests, mypy, and the Kit workflow pass. The workflow now also opens a different project with different prim paths and properties and verifies that its geometry receives the new override.

An isolated check of the user's BS17.usd discovers 1,458 final Xforms and colors 1,391. The remaining 67 are connection-port Xforms without loaded renderable geometry. Loading and scanning took 1.08 seconds; applying the overrides took 0.53 seconds in standalone USD. Sampled geometry returned to its original materials after Disable.

An isolated RTX process rendered BS17 before coloring, with a red override, and after Disable. Red-pixel counts were 0, 285,953, and 0. Both the in-memory root layer after camera setup and the source file's SHA-256 remained unchanged during coloring. The production scene was not saved. Images and results are in `verification/bs17-*.png` and `verification/bs17-render-result.json`. The user's existing Composer process still needs to reload the updated extension.

## Performance

`run-verify.ps1 -Test tests/benchmark.py` generated 3,000 native instances grouped into 20 property values. All 3,000 colored without notices. The measured scan took 0.17 seconds and the complete USD override update took 1.28 seconds. The previous implementation took 8.41 seconds. This is a synthetic standalone USD benchmark, not an RTX frame-rate measurement. The UI path yields between batches.

An independent SOL10 process discovered and colored 18,111 final Xforms with zero notices. Loading and scanning took 16.40 seconds; grouping and applying colors took 11.16 seconds. All 15 renderable parts inspected in a sample door resolved to the solid override. The source root remained unmodified and was not saved. These timings exclude Composer rendering.

After reloading the initial update in the open Composer, the panel reported 18,111 objects and 18,111 Xforms colored in 49.28 seconds, with no notices. That count incorrectly included `/Environment`, which allowed its solid material to inherit onto `/Environment/Sky`. The scene was not saved.

After the environment exclusion fix, a read-only scan of SOL10 finds 18,110 model Xforms. Neither `/Environment/Sky` nor `/Environment/DistantLight` has a targeted ancestor. The fix passes the isolated Kit workflow; restoration of the background in the user's existing Composer session has not been visually verified.

## Limits of this verification

Production T135 metadata and material structure were inspected read-only during initial development. The Xform update was checked against SOL10 in an independent process and rendered on generated fixtures.

Collection-only overrides resolved in USD but did not render on instance descendants in RTX. Direct Xform bindings passed the rendered check. Mixed-opacity native instances now receive the requested solid color; original opacity returns when coloring is disabled.

Streaming infrastructure, concurrent viewers, browser file transfer, and exact Forma visual parity have not been tested. See [the supported data and rendering limits](reference.md).

Generated screenshots, logs, and JSON results are stored in the ignored `verification/` directory.
