# Object Colors reference

## Grouping

The scope is always the whole stage. One criterion is active at a time.

| Mode | Data source |
| --- | --- |
| Property | Authored scalar custom attributes, including `omni:hoops:metadata:*` |
| File | The defining USD layer's resolved path |
| Model | The nearest ancestor's `objectColors:model`, asset name, or asset identifier |

Model names are never inferred from prim names. An unavailable mode explains which data is missing. File means the USD source layer, which may differ from an original RVT or IFC filename.

Property keys retain their full namespaces. The panel labels HOOPS properties with `[HOOPS]` and retains their category paths. Values retain their Python scalar type, so the string `"1"` and the integer `1` form different groups.

A logical object owns the geometry below a metadata-bearing prim, ending at the next metadata-bearing object. Untagged geometry becomes its own object when no owner exists. Spatial IFC containers do not become objects. Native instances count once, regardless of their mesh count. Visible internal reference sources are excluded with a notice to avoid recoloring their instances indirectly.

The first 100 typed values in deterministic key order appear individually. Additional values form **Unmapped**. Missing values form **Unassigned**, separate from a literal string with that name. The tooltip shows the typed key when labels look alike.

Palette assignments are stored per criterion. They survive refreshes and switches between properties, including assignments for values absent from the current scene. New assignments use a stable hash and a fixed 40-color palette. The palette is not an exact copy of Forma's swatches.

## Rendering and opacity

The extension builds materials and bindings in a dedicated anonymous session sublayer. It does not edit source materials or geometry. Disable mutes that layer. No color omits the relevant override. Shutdown removes the layer and releases the stage subscription.

Generated materials share a color and opacity profile. Source diffuse textures are replaced. Scalar USD Preview Surface opacity and opacity threshold are retained, as is constant inherited display opacity on geometry without a material.

Ordinary geometry supports face subsets, collection bindings, and the full and preview material purposes. Native instances use a direct root binding because RTX 110.2 did not render collection-only bindings to instance descendants in the verification fixture.

The following cases remain unchanged and produce a notice:

- Native instances whose parts have different opacity profiles.
- Connected or animated opacity, varying display opacity, and unsupported shader types such as MDL-only materials.
- Point instancers and direct edits to instance proxies.
- Bindings that remain stronger than the visualization layer.

To color an unsupported mixed-opacity native instance, supply non-instance geometry with individually bindable parts. The extension does not de-instance assets automatically.

The extension scans loaded, active, defined prims. Refresh is manual. It does not load payloads or update colors continuously during animation.

## Preset storage

Shared templates are version 1 JSON files with `name`, `scope`, `mode`, `property_key`, `enabled`, and `palettes`. `scope` must be `stage`. Imports reject unsupported versions, modes, and colors. The maximum file size is 10 MB.

The bundled templates select IFC element type and Revit instance workset. Extra templates come from `/exts/object.color/templateDirectory`. The list loads when the extension starts. Every load creates a separate scheme object.

User edits store the active scheme as JSON in the root layer's `customLayerData.objectColorsState`. The normal scene save persists that data. On reopen, the extension rebuilds the temporary rendering layer. It must be enabled to restore the coloring. Merely opening a scene without saved color state does not write default settings into it.

Read-only roots support coloring and JSON export, but cannot retain scene state. Reusable templates contain property keys and typed values, not object paths. They therefore apply to other scenes with compatible metadata.

Undo and redo cover mode, property, enabled-state, palette, and template changes. Export writes a new file and is not part of the scene undo stack.

## Excluded integrations

Forma palette synchronization, gradients, compound rules, issue thumbnails, clash integration, legend isolation, browser uploads, and account-specific cloud storage are outside this release.
