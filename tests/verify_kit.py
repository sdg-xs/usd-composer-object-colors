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
from PIL import Image, ImageStat
from pxr import Gf, Sdf, Usd, UsdGeom, UsdLux, UsdShade

ROOT = Path(__file__).resolve().parent.parent
sys.path[:0] = [str(ROOT), str(ROOT / 'tests')]
from test_usd import fixture, material
from object_colors.overrides import ColorOverrides
from object_colors.extension import ObjectColorsExtension, get_controller
from object_colors.presets import load_scene, read

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


async def verify_inspection(controller, context):
    stage = context.get_stage()
    assert get_controller() is controller
    source = stage.GetRootLayer().ExportToString()
    scope = controller.begin_inspection(stage)
    assert controller.inspection_active
    assert not controller.overrides.enabled
    try:
        scan = await controller.get_scan(refresh=True)
        assert {o.path for o in scan.objects} == {'/World/A', '/World/B'}
        try:
            controller.begin_inspection(stage)
        except RuntimeError:
            pass
        else:
            raise AssertionError('A second inspection scope was accepted')
        report = await scope.apply({'/World/A': '#4E79A7', '/Missing': '#E15759'})
        assert report.colored_paths == ['/World/A'], report
        assert report.unsupported_paths == ['/Missing'], report
        bound = UsdShade.MaterialBindingAPI(stage.GetPrimAtPath('/World/A/Shape')).ComputeBoundMaterial()[0]
        assert str(bound.GetPath()) == controller.overrides.material_root + '/C4E79A7'
        controller.edit(color=('str:"A"', '#59A14F'))
        assert load_scene(stage).color('str:"A"') == '#59A14F'
        bound = UsdShade.MaterialBindingAPI(stage.GetPrimAtPath('/World/A/Shape')).ComputeBoundMaterial()[0]
        assert str(bound.GetPath()) == controller.overrides.material_root + '/C4E79A7'
        empty = await scope.apply({})
        assert empty.colored == 0
        bound = UsdShade.MaterialBindingAPI(stage.GetPrimAtPath('/World/A/Shape')).ComputeBoundMaterial()[0]
        assert str(bound.GetPath()) == '/World/Looks/Glass'
    finally:
        await scope.close()
    assert not controller.inspection_active
    bound = UsdShade.MaterialBindingAPI(stage.GetPrimAtPath('/World/A/Shape')).ComputeBoundMaterial()[0]
    assert str(bound.GetPath()) == controller.overrides.material_root + '/C59A14F'
    assert stage.GetRootLayer().ExportToString() != source  # Only the deliberate scheme edit persists.
    try:
        await scope.apply({'/World/A': '#E15759'})
    except RuntimeError:
        pass
    else:
        raise AssertionError('A closed inspection scope was accepted')
    controller.edit(color=('str:"A"', '#E15759'))
    await settled(controller)


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
        assert {o.path for o in controller.scan.objects} == {'/World/A', '/World/B'}
        sky = context.get_stage().GetPrimAtPath('/Environment/Sky')
        assert not UsdShade.MaterialBindingAPI(sky).ComputeBoundMaterial()[0]
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
        await verify_inspection(controller, context)
        with Image.open(OUTPUT / 'before.png') as before, Image.open(OUTPUT / 'controller-colored.png') as after:
            background = (0, 0, 32, 32)
            original = ImageStat.Stat(before.convert('RGB').crop(background)).mean
            colored = ImageStat.Stat(after.convert('RGB').crop(background)).mean
            assert min(original) > 20, ('fixture background is already dark', original)
            assert max(abs(a - b) for a, b in zip(original, colored)) < 2, ('sky changed', original, colored)
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
        stale_scope = controller.begin_inspection(context.get_stage())
        await stale_scope.apply({'/World/A': '#E15759'})
        previous_layer_id = controller.overrides.layer.identifier
        await context.close_stage_async()
        await context.open_stage_async(str(sample))
        await settled(controller)
        try:
            await stale_scope.apply({'/World/A': '#E15759'})
        except RuntimeError:
            pass
        else:
            raise AssertionError('A scope from the closed stage was accepted')
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
        other = Usd.Stage.CreateInMemory()
        obj = UsdGeom.Xform.Define(other, '/Another/Part').GetPrim()
        obj.CreateAttribute('bim:Category', Sdf.ValueTypeNames.String, custom=True).Set('Wall')
        UsdGeom.Cube.Define(other, '/Another/Part/Shape')
        other_path = OUTPUT / 'other-project.usda'
        other.GetRootLayer().Export(str(other_path))
        previous_layer_id = controller.overrides.layer.identifier
        await context.close_stage_async()
        await context.open_stage_async(str(other_path))
        await settled(controller)
        assert Sdf.Layer.Find(previous_layer_id) is None
        assert {o.path for o in controller.scan.objects} == {'/Another/Part'}
        assert controller.scheme.property_key == 'bim:Category'
        controller.edit(enabled=True)
        await settled(controller)
        assert not controller.issues, controller.issues
        bound = UsdShade.MaterialBindingAPI(context.get_stage().GetPrimAtPath('/Another/Part/Shape')).ComputeBoundMaterial()[0]
        assert str(bound.GetPath()).startswith(controller.overrides.material_root + '/')
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
        assert Path(sys.modules[ColorOverrides.__module__].__file__).resolve().is_relative_to(ROOT), 'Kit loaded a different Object Colors checkout'
        stage = fixture()
        UsdGeom.XformCommonAPI(stage.GetPrimAtPath('/Library')).SetTranslate(Gf.Vec3d(0, 0, -100))
        UsdGeom.XformCommonAPI(stage.GetPrimAtPath('/World/A')).SetTranslate(Gf.Vec3d(-2, 0, 0))
        UsdGeom.XformCommonAPI(stage.GetPrimAtPath('/World/B')).SetTranslate(Gf.Vec3d(2, 0, 0))
        solid = UsdGeom.Cube.Define(stage, '/Library/Frame')
        solid.CreateSizeAttr(.6)
        UsdGeom.XformCommonAPI(solid).SetTranslate(Gf.Vec3d(1.2, 0, 0))
        UsdShade.MaterialBindingAPI.Apply(solid.GetPrim()).Bind(material(stage, '/World/Looks/Solid'))
        camera = UsdGeom.Camera.Define(stage, '/World/Camera')
        camera.AddTranslateOp().Set(Gf.Vec3d(0, 0, 15))
        UsdGeom.Xform.Define(stage, '/Environment')
        UsdLux.DomeLight.Define(stage, '/Environment/Sky').CreateIntensityAttr(1000)
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
        assert not report.issues, report.issues
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
