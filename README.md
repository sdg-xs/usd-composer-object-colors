# Object Colors for USD Composer

Color a whole USD stage by an object property, source file, or model. Edit colors in a legend and reuse schemes through shared JSON templates.

This extension targets Kit 110.2 on Windows. See [supported data and limitations](docs/reference.md) and [verification results](docs/verification.md).

## Enable the extension

1. Put the `object.color` folder in an extension search directory.
2. Open **Developer > Extensions** in Composer.
3. Add the parent directory of `object.color` to the extension search paths if needed.
4. Search for **Object Colors** and enable it.

The panel opens automatically. Reopen it through **Window > Object Colors**.

## Color the scene

1. Open a USD scene.
2. Choose **Property**, **File**, or **Model** under **Color by**.
3. For Property mode, filter the property list and select a property.
4. Select **Enable colors**.
5. Click a legend swatch to choose another color.

Choose **No color** in the palette to reveal the underlying material for that group. Clear **Enable colors** to restore the whole scene.

Click **Refresh** after changing the scene or its properties. Existing assignments remain stable. Expand **notices** for objects that cannot be colored.

Use Composer's Undo and Redo commands for scheme and swatch changes. Save the scene to retain its scheme and enabled state.

## Reuse and publish a scheme

1. Select a shared template and click **Load** to create a session copy.
2. Adjust the colors as needed.
3. Enter a preset name and a full path to a new `.json` file.
4. Click **Export new JSON**.

To reuse an exported file, enter its full path and click **Import JSON**. Export refuses to overwrite an existing file.

To publish templates for a streamed deployment, place JSON presets in a server directory. Set `/exts/object.color/templateDirectory` to that directory before enabling the extension. The extension reads templates and never updates them through the panel.

Template edits affect the current Kit session. Clients sharing one Kit process see the same stage and scheme. Independent sessions require separate Kit processes. JSON paths refer to the Composer machine; browser upload and personal cloud libraries are not included.

## Run verification

Run the commands from the extension directory:

```powershell
./run-verify.ps1
./run-verify-kit.ps1
./run-verify.ps1 -Test tests/benchmark.py
```

The scripts use the Kit installation at `C:\kit-app-template\_build\windows-x86_64\release\kit`. Pass `-KitRoot` to select another installation. The Kit check starts a separate process and generates its own scene. Results and screenshots go to `verification/`.

For static typechecking, install `mypy` into `verification/typecheck` using Kit's Python, then run `./run-typecheck.ps1`.
