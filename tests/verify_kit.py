"""Exercise RTX in an isolated Kit process; never touch an occupied user stage."""
import asyncio
import json
from pathlib import Path
import sys
import traceback

import omni.kit.app
import omni.appwindow
import omni.kit.renderer_capture
import omni.kit.undo
import omni.ui as ui
import omni.kit.viewport.utility as vp_util
import omni.usd
from PIL import Image
from pxr import Gf, Sdf, UsdGeom, UsdLux, UsdShade

ROOT = Path(__file__).resolve().parent.parent
sys.path[:0] = [str(ROOT), str(ROOT / 'tests')]
from test_usd import fixture
from object_colors.overrides import ColorOverrides
from object_colors.extension import ObjectColorsExtension
from object_colors.presets import read

APP = omni.kit.app.get_app()
OUTPUT = ROOT / 'verification'


async def frames(n=10):
    for _ in range(n):
        await APP.next_update_async()


async def capture(viewport, name):
    path = OUTPUT / name
    path.unlink(missing_ok=True)
    await vp_util.capture_viewport_to_file(viewport, str(path)).wait_for_result()
    for _ in range(300):
        try:
            with Image.open(path) as image:
                pixels = image.convert('RGB').tobytes()
            return sum(r > g * 1.5 and r > b * 1.5 and r > 60 for r, g, b in zip(pixels[::3], pixels[1::3], pixels[2::3]))
        except OSError:
            await frames(1)
    raise AssertionError('Capture was not written')


async def settled(controller):
    await frames(2)
    if controller.task:
        await asyncio.wait_for(asyncio.shield(controller.task), 60)
    await frames(3)
    assert not controller.busy
    assert not controller.status.startswith('Could not'), controller.status


async def verify_workflow(context, sample):
    manager = APP.get_extension_manager()
    extension_id = manager.get_enabled_extension_id('object.color')
    manager.set_extension_enabled_immediate(extension_id, False)
    extension = ObjectColorsExtension()
    extension.on_startup('object.color.test')
    try:
        controller = extension.controller
        await settled(controller)
        assert ui.Workspace.get_window('Object Colors').visible
        controller.edit(property_key='bim:Level', enabled=True)
        await settled(controller)
        assert controller.scheme.enabled
        assert len(controller.groups) == 2
        capture_api = omni.kit.renderer_capture.acquire_renderer_capture_interface()
        app_window = omni.appwindow.get_default_app_window()
        capture_api.capture_next_frame_swapchain(str(OUTPUT / 'panel.png'), app_window)
        await frames(3)
        capture_api.wait_async_capture(app_window)
        controller.edit(color=('str:"A"', '#E15759'))
        await settled(controller)
        assert controller.scheme.color('str:"A"') == '#E15759'
        viewport = vp_util.get_active_viewport()
        await frames(30)
        rendered = await capture(viewport, 'controller-colored.png')
        assert rendered > 100, ('controller did not render its selected color', rendered)
        controller.edit(color=('str:"A"', None))
        await settled(controller)
        mesh = context.get_stage().GetPrimAtPath('/World/A/Shape')
        assert str(UsdShade.MaterialBindingAPI(mesh).ComputeBoundMaterial()[0].GetPath()) == '/World/Looks/Glass'
        await frames(30)
        assert await capture(viewport, 'controller-no-color.png') < rendered / 2
        omni.kit.undo.undo()
        await settled(controller)
        assert controller.scheme.color('str:"A"') == '#E15759'
        omni.kit.undo.redo()
        await settled(controller)
        assert controller.scheme.color('str:"A"') is None
        extension.panel._palette(controller.groups[0])
        generation = controller.generation
        criterion = controller.scheme.criterion
        assert ui.Workspace.get_window('Choose color').visible
        await frames(3)
        capture_api.capture_next_frame_swapchain(str(OUTPUT / 'palette.png'), app_window)
        await frames(3)
        capture_api.wait_async_capture(app_window)
        controller.edit(mode='File')
        await settled(controller)
        assert len(controller.groups) == 1
        assert not ui.Workspace.get_window('Choose color').visible
        extension.panel._choose('str:"A"', '#E15759', generation, criterion)
        assert 'str:"A"' not in controller.scheme.palettes.get('File:', {})
        controller.edit(mode='Model')
        await settled(controller)
        assert any('model asset metadata' in issue for issue in controller.issues)
        _, template = read(ROOT / 'data/templates/ifc-type.json')
        controller.change(template)
        await settled(controller)
        assert any('property is absent' in issue for issue in controller.issues)
        controller.edit(property_key='bim:Level', enabled=True)
        await settled(controller)
        context.get_stage().GetRootLayer().Save()
        previous_layer_id = controller.overrides.layer.identifier
        await context.close_stage_async()
        await context.open_stage_async(str(sample))
        await settled(controller)
        assert Sdf.Layer.Find(previous_layer_id) is None
        assert controller.scheme.enabled
        assert controller.scheme.property_key == 'bim:Level'
        assert len(context.get_stage().GetSessionLayer().subLayerPaths) == 1
        controller.edit(enabled=False)
        await settled(controller)
        context.get_stage().GetRootLayer().Save()
        await context.close_stage_async()
        await context.open_stage_async(str(sample))
        await settled(controller)
        assert not controller.scheme.enabled
        controller.edit(enabled=True)
        await settled(controller)
        stage = context.get_stage()
        extension.on_shutdown()
        extension = None
        await frames()
        assert not stage.GetSessionLayer().subLayerPaths
        # Undo entries from a shut-down controller are harmless.
        omni.kit.undo.undo()
        await frames()
        assert not stage.GetSessionLayer().subLayerPaths
        return 'passed'
    finally:
        if extension:
            extension.on_shutdown()


async def main():
    overrides = None
    try:
        stage = fixture()
        UsdGeom.XformCommonAPI(stage.GetPrimAtPath('/Library')).SetTranslate(Gf.Vec3d(0, 0, -100))
        UsdGeom.XformCommonAPI(stage.GetPrimAtPath('/World/A')).SetTranslate(Gf.Vec3d(-2, 0, 0))
        UsdGeom.XformCommonAPI(stage.GetPrimAtPath('/World/B')).SetTranslate(Gf.Vec3d(2, 0, 0))
        stage.GetPrimAtPath('/World/Looks/Glass/Surface').GetAttribute('inputs:opacity').Set(1.0)
        camera = UsdGeom.Camera.Define(stage, '/World/Camera')
        camera.AddTranslateOp().Set(Gf.Vec3d(0, 0, 15))
        UsdLux.DomeLight.Define(stage, '/World/Light').CreateIntensityAttr(1000)
        sample = OUTPUT / 'render-fixture.usda'
        stage.GetRootLayer().Export(str(sample))
        context = omni.usd.get_context()
        await context.open_stage_async(str(sample))
        stage = context.get_stage()
        viewport = vp_util.get_active_viewport()
        viewport.camera_path = '/World/Camera'
        await frames(90)
        before = await capture(viewport, 'before.png')
        overrides = ColorOverrides(stage)
        report = overrides.apply({'/World/A': '#E15759'})
        assert report.colored == 1, report.issues
        colored = 0
        for _ in range(12):
            await frames(30)
            colored = await capture(viewport, 'colored.png')
            if colored > before + 100:
                break
        assert colored > before + 100, (before, colored, 'instance collection did not render red')
        overrides.set_enabled(False)
        await frames(30)
        restored = await capture(viewport, 'restored.png')
        assert restored < colored / 2, (colored, restored)
        overrides.close()
        workflow = await verify_workflow(context, sample)
        (OUTPUT / 'kit-result.json').write_text(json.dumps(dict(before=before, colored=colored, restored=restored, workflow=workflow)), encoding='utf-8')
        print('OBJECT_COLORS_KIT_PASS', before, colored, restored)
        APP.post_quit(0)
    except Exception:
        traceback.print_exc()
        APP.post_quit(1)
    finally:
        if overrides:
            overrides.close()


asyncio.ensure_future(main())
