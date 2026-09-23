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

Each object is a final editable Xform: an Xform with no descendant Xforms in the editable stage hierarchy. Native instance roots count once; discovery does not enter their instance proxies. Meshes, subsets, and other child prims do not become separate objects. Standalone meshes and spatial IFC containers are excluded.

Properties come from the Xform and its Xform ancestors, with the nearest value taking precedence. Mesh metadata is ignored. Visible internal reference sources and their enclosing containers are excluded to avoid recoloring other instances indirectly.

Xforms containing lights or cameras are excluded, including native instances of light or camera rigs. This keeps environment and sky materials outside the color overlay. A mixed geometry-and-light Xform is also excluded. Instance prototypes are inspected for this exclusion without counting their children as objects.

The first 100 typed values in deterministic key order appear individually. Additional values form **Unmapped**. Missing values form **Unassigned**, separate from a literal string with that name. The tooltip shows the typed key when labels look alike.

Palette assignments are stored per criterion. They survive refreshes and switches between properties, including assignments for values absent from the current scene. Unassigned defaults to `#969696` unless a saved color or No color choice already exists. Other new assignments use a stable hash and a fixed 40-color palette. The palette is not an exact copy of Forma's swatches.

## Solid coloring and restoration

The extension builds materials and bindings in a dedicated anonymous session sublayer. It does not edit source materials or geometry. Disable mutes that layer. No color omits the relevant override. Shutdown removes the layer and releases the stage subscription.

Each final Xform receives one opaque USD Preview Surface material. Its children inherit that color, including glass, mixed-opacity parts, and material subsets. Source textures, shaders, and opacity do not affect the temporary color. Disable or No color reveals the original materials and transparency.

The extension authors bindings on Xforms, not their child meshes or subsets. Direct Xform bindings support RTX rendering of native instances. Expanding collections handle ancestor binding priorities for the full, preview, and all-purpose material bindings. Material resolution checks run in batches on the Xforms.

Direct edits to instance proxies and separate coloring of point-instancer instances are not supported. Bindings that prevent coloring at the Xform produce a notice. The extension does not de-instance assets.

The extension scans loaded, active, defined prims. Refresh is manual. It does not load payloads or update colors continuously during animation.

## Scene storage

User edits store the active scheme as JSON in the root layer's `customLayerData.objectColorsState`. The normal scene save persists that data. On reopen, the extension rebuilds the temporary rendering layer. It must be enabled to restore the coloring. Merely opening a scene without saved color state does not write default settings into it.

Read-only roots support coloring but cannot retain scene state.

Undo and redo cover mode, property, enabled-state, and palette changes.

## Excluded integrations

Forma palette synchronization, gradients, compound rules, issue thumbnails, clash integration, legend isolation, browser uploads, and account-specific cloud storage are outside this release.
