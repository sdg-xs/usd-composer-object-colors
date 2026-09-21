# Verification results

Verified on 2026-09-21 using Kit `110.2.0+feature.342835.698af100.gl`, OpenUSD 25.11, Windows, and an NVIDIA RTX 4070 Laptop GPU.

## Automated checks

`run-verify.ps1` runs focused unittest cases against the installed USD libraries. The cases cover typed grouping, missing values, overflow, stable assignments, template independence, import validation, scene persistence, logical-object counting, instance bindings, opacity, subsets, collection priorities, and restoration.

`run-typecheck.ps1` runs mypy with `check_untyped_defs` on the extension. Kit and USD APIs do not ship complete type stubs, so the runtime checks remain necessary.

`run-verify-kit.ps1` starts an isolated Kit app with the actual extension. It renders a generated scene, changes one native instance, and measures red pixels before coloring, during coloring, and after Disable. The last completed rendering check measured 0, 194,512, and 0 red pixels respectively.

The Kit workflow also checks swatch edits, No color, undo, redo, File grouping, unavailable Model metadata, incompatible templates, enabled and disabled save/reopen, stage replacement, and shutdown. It checks that the old visualization layer is released and that shutdown leaves no active overrides.

## Performance

`run-verify.ps1 -Test tests/benchmark.py` generated 3,000 native instances grouped into 20 property values. All 3,000 colored without notices. The measured scan took 0.16 seconds and the complete USD override update took 8.41 seconds. This is a synthetic standalone USD benchmark, not an RTX frame-rate measurement. The UI path yields between batches.

## Limits of this verification

Production T135 metadata and material structure were inspected read-only during development. The final implementation has not been visually validated on a production model. Final verification uses generated scenes as requested by the user.

An attempted check in the occupied SOL10 Composer session stopped at an import error before any coloring or stage mutation. No production stage was saved. Computer access was stopped at the user's request.

Collection-only overrides resolved in USD but did not render on instance descendants in RTX. The direct instance-root binding passed the rendered check. Mixed-opacity native instances and unsupported opacity networks are reported and skipped.

Streaming infrastructure, concurrent viewers, browser file transfer, and exact Forma visual parity have not been tested. See [the supported data and rendering limits](reference.md).

Generated screenshots, logs, and JSON results are stored in the ignored `verification/` directory.
