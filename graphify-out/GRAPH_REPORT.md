# Graph Report - object.color  (2026-09-23)

## Corpus Check
- 25 files · ~8,255 words
- Verdict: corpus is large enough that graph structure adds value.
- Unclassified: 4 file(s) not represented in the graph (top: (none) 2, .toml 1, .kit 1)

## Summary
- 204 nodes · 481 edges · 9 communities (8 shown, 1 thin omitted)
- Extraction: 96% EXTRACTED · 4% INFERRED · 0% AMBIGUOUS · INFERRED: 19 edges (avg confidence: 0.94)
- Token cost: 0 input · 0 output

## Graph Freshness
- Built from commit: `3e843c4b`
- Run `git rev-parse HEAD` and compare to check if the graph is stale.
- Run `graphify update .` after code changes (no API cost).

## Community Hubs (Navigation)
- Scheme
- Isolated Kit rendering workflow
- discovery.py
- controller.py
- ColorOverrides
- Property selection and palette
- verify_kit.py
- Controller
- InspectionScope

## God Nodes (most connected - your core abstractions)
1. `ColorOverrides` - 27 edges
2. `Controller` - 26 edges
3. `Scheme` - 26 edges
4. `scan_stage()` - 17 edges
5. `ColoringTests` - 15 edges
6. `group_objects()` - 13 edges
7. `ObjectColorsWindow` - 13 edges
8. `fixture()` - 13 edges
9. `InspectionScope` - 12 edges
10. `loads()` - 12 edges

## Surprising Connections (you probably didn't know these)
- `LeafXformTests` --uses--> `ColorOverrides`  [INFERRED]
  tests/test_leaf_xforms.py → object_colors/overrides.py
- `verify_workflow()` --calls--> `ObjectColorsExtension`  [EXTRACTED]
  tests/verify_kit.py → object_colors/extension.py
- `ColoringTests` --uses--> `ColorOverrides`  [INFERRED]
  tests/test_usd.py → object_colors/overrides.py
- `main()` --calls--> `ColorOverrides`  [EXTRACTED]
  tests/verify_kit.py → object_colors/overrides.py
- `verify_workflow()` --calls--> `read()`  [EXTRACTED]
  tests/verify_kit.py → object_colors/presets.py

## Import Cycles
- None detected.

## Hyperedges (group relationships)
- **Reversible scene coloring** — docs_reference_scene_state, docs_reference_session_overlay, docs_reference_solid_xform_bindings, docs_reference_undo_redo [EXTRACTED 1.00]
- **Complementary verification evidence** — docs_verification_usd_tests, docs_verification_kit_workflow, docs_verification_static_typecheck, docs_verification_synthetic_benchmark [EXTRACTED 1.00]

## Communities (9 total, 1 thin omitted)

### Community 0 - "Scheme"
Cohesion: 0.15
Nodes (22): hashlib, json, math, dumps(), export(), load_scene(), loads(), Versioned, portable templates. Loading always produces an independent scheme. (+14 more)

### Community 1 - "Isolated Kit rendering workflow"
Cohesion: 0.09
Nodes (28): Final editable Xforms, Property File and Model grouping, Inherited Xform properties, Light and camera exclusion, Manual loaded-stage refresh, Scene color state persistence, Anonymous session color layer, Solid Xform material bindings (+20 more)

### Community 2 - "discovery.py"
Cohesion: 0.13
Nodes (13): dataclasses, _contains_scene_setup(), _properties(), _provenance(), Discover final editable Xforms and their inherited object properties., Scan, scan_stage(), scan_steps() (+5 more)

### Community 3 - "controller.py"
Cohesion: 0.12
Nodes (13): asyncio, carb, ChangeObjectColors, Kit lifecycle and undo orchestration around the stage-local coloring engine., ObjectColorsExtension, Object Colors for Kit. Core modules also run with standalone OpenUSD., omni_ext, omni_kit_app (+5 more)

### Community 4 - "ColorOverrides"
Cohesion: 0.18
Nodes (6): ApplyReport, ColorOverrides, _linear(), ColoringTests, fixture(), material()

### Community 5 - "Property selection and palette"
Cohesion: 0.16
Nodes (6): Search SVG icon, property_label(), ObjectColorsWindow, Composer-native panel with a searchable property selector and fixed swatches., swatch_color(), omni_ui

### Community 6 - "verify_kit.py"
Cohesion: 0.20
Nodes (16): get_controller(), Return the controller owned by the running Object Colors extension, if any., omni_appwindow, omni_kit_renderer_capture, omni_kit_undo, omni_kit_viewport_utility, pil, sys (+8 more)

### Community 8 - "InspectionScope"
Cohesion: 0.25
Nodes (4): InspectionScope, Release the display and restore the latest desired Object Colors scheme., Exclusive, stage-bound use of the controller's material override layer., Replace the temporary highlight; an empty mapping reveals source materials.

## Knowledge Gaps
- **2 isolated node(s):** `Unverified runtime boundaries`, `Search SVG icon`
  These have ≤1 connection - possible missing edges or undocumented components. (Counts symbols only; 47 node(s) total have ≤1 connection when file, concept and rationale nodes are included.)
- **1 thin communities (<3 nodes) omitted from report** — run `graphify query` to explore isolated nodes.

## Suggested Questions
_Questions this graph is uniquely positioned to answer:_

- **Why does `ColorOverrides` connect `ColorOverrides` to `discovery.py`, `controller.py`, `verify_kit.py`, `Controller`?**
  _High betweenness centrality (0.179) - this node is a cross-community bridge._
- **Why does `Controller` connect `Controller` to `Scheme`, `discovery.py`, `controller.py`, `ColorOverrides`?**
  _High betweenness centrality (0.146) - this node is a cross-community bridge._
- **Are the 3 inferred relationships involving `ColorOverrides` (e.g. with `Controller` and `LeafXformTests`) actually correct?**
  _`ColorOverrides` has 3 INFERRED edges - model-reasoned connections that need verification._
- **Are the 4 inferred relationships involving `Controller` (e.g. with `Scan` and `ColorOverrides`) actually correct?**
  _`Controller` has 4 INFERRED edges - model-reasoned connections that need verification._
- **Are the 7 inferred relationships involving `Scheme` (e.g. with `Controller` and `dumps()`) actually correct?**
  _`Scheme` has 7 INFERRED edges - model-reasoned connections that need verification._
- **What connects `Unverified runtime boundaries`, `Search SVG icon` to the rest of the system?**
  _2 weakly-connected nodes found - possible documentation gaps or missing edges._
- **Should `Scheme` be split into smaller, more focused modules?**
  _Cohesion score 0.14761904761904762 - nodes in this community are weakly interconnected._