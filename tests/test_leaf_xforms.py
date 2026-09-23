import unittest

from pxr import Sdf, Usd, UsdGeom, UsdLux, UsdShade

from object_colors.discovery import scan_stage
from object_colors.overrides import ColorOverrides


class LeafXformTests(unittest.TestCase):
    def test_coloring_preserves_sky_and_camera_materials(self):
        stage = Usd.Stage.CreateInMemory()
        UsdGeom.Xform.Define(stage, '/Environment')
        sky = UsdLux.DomeLight.Define(stage, '/Environment/Lights/Sky').GetPrim()
        original = UsdShade.Material.Define(stage, '/Looks/Sky')
        UsdShade.MaterialBindingAPI.Apply(sky).Bind(original)
        UsdGeom.Xform.Define(stage, '/Rig')
        camera = UsdGeom.Camera.Define(stage, '/Rig/Cameras/Main').GetPrim()
        UsdGeom.Xform.Define(stage, '/Model/Part')
        UsdGeom.Cube.Define(stage, '/Model/Part/Shape')
        source = stage.GetRootLayer().ExportToString()
        overrides = ColorOverrides(stage)
        try:
            overrides.apply({o.path: '#E15759' for o in scan_stage(stage).objects})
            self.assertEqual(UsdShade.MaterialBindingAPI(sky).ComputeBoundMaterial()[0].GetPath(), original.GetPath())
            self.assertFalse(UsdShade.MaterialBindingAPI(camera).ComputeBoundMaterial()[0])
            self.assertEqual([o.path for o in scan_stage(stage).objects], ['/Model/Part'])
            self.assertEqual(stage.GetRootLayer().ExportToString(), source)
        finally:
            overrides.close()

    def test_instanced_light_rigs_are_not_color_targets(self):
        stage = Usd.Stage.CreateInMemory()
        stage.CreateClassPrim('/Library')
        UsdLux.DomeLight.Define(stage, '/Library/Sky')
        for name in ('A', 'B'):
            instance = UsdGeom.Xform.Define(stage, f'/World/{name}').GetPrim()
            instance.GetReferences().AddInternalReference('/Library')
            instance.SetInstanceable(True)
        self.assertEqual(scan_stage(stage).objects, [])

    def test_only_deepest_xforms_are_objects_and_mesh_metadata_is_ignored(self):
        stage = Usd.Stage.CreateInMemory()
        root = UsdGeom.Xform.Define(stage, '/World/Assembly').GetPrim()
        root.CreateAttribute('bim:Level', Sdf.ValueTypeNames.String, custom=True).Set('L1')
        for name in ('Door', 'Frame'):
            UsdGeom.Xform.Define(stage, f'/World/Assembly/Parts/{name}')
            mesh = UsdGeom.Cube.Define(stage, f'/World/Assembly/Parts/{name}/Shape').GetPrim()
            mesh.CreateAttribute('mesh:internal', Sdf.ValueTypeNames.String, custom=True).Set('ignore')
        UsdGeom.Cube.Define(stage, '/World/Assembly/LooseMesh')
        scan = scan_stage(stage)
        self.assertEqual({o.path for o in scan.objects},
                         {'/World/Assembly/Parts/Door', '/World/Assembly/Parts/Frame'})
        self.assertEqual(scan.properties, ['bim:Level'])
        self.assertTrue(all(o.properties['bim:Level'] == 'L1' for o in scan.objects))

    def test_leaf_metadata_overrides_parent_metadata(self):
        stage = Usd.Stage.CreateInMemory()
        parent = UsdGeom.Xform.Define(stage, '/World').GetPrim()
        parent.CreateAttribute('bim:Level', Sdf.ValueTypeNames.String, custom=True).Set('parent')
        leaf = UsdGeom.Xform.Define(stage, '/World/Leaf').GetPrim()
        leaf.CreateAttribute('bim:Level', Sdf.ValueTypeNames.String, custom=True).Set('leaf')
        UsdGeom.Cube.Define(stage, '/World/Leaf/Shape')
        self.assertEqual(scan_stage(stage).objects[0].properties['bim:Level'], 'leaf')

    def test_instance_is_one_editable_xform_without_proxy_objects(self):
        stage = Usd.Stage.CreateInMemory()
        stage.CreateClassPrim('/Library')
        UsdGeom.Xform.Define(stage, '/Library/Inner')
        UsdGeom.Cube.Define(stage, '/Library/Inner/Shape')
        instance = UsdGeom.Xform.Define(stage, '/World/Placed').GetPrim()
        instance.GetReferences().AddInternalReference('/Library')
        instance.SetInstanceable(True)
        self.assertEqual([o.path for o in scan_stage(stage).objects], ['/World/Placed'])

    def test_standalone_meshes_and_spatial_containers_are_not_objects(self):
        stage = Usd.Stage.CreateInMemory()
        UsdGeom.Cube.Define(stage, '/LooseMesh')
        floor = UsdGeom.Xform.Define(stage, '/Floor').GetPrim()
        floor.CreateAttribute('omni:hoops:metadata:TYPE', Sdf.ValueTypeNames.String, custom=True).Set('IFCBUILDINGSTOREY')
        UsdGeom.Cube.Define(stage, '/Floor/Shape')
        self.assertEqual(scan_stage(stage).objects, [])

    def test_excluded_instance_source_does_not_make_its_parent_a_color_target(self):
        stage = Usd.Stage.CreateInMemory()
        UsdGeom.Xform.Define(stage, '/World/Prototypes')
        UsdGeom.Xform.Define(stage, '/World/Prototypes/Door')
        UsdGeom.Cube.Define(stage, '/World/Prototypes/Door/Shape')
        instance = UsdGeom.Xform.Define(stage, '/World/Placed').GetPrim()
        instance.GetReferences().AddInternalReference('/World/Prototypes/Door')
        instance.SetInstanceable(True)
        self.assertEqual([o.path for o in scan_stage(stage).objects], ['/World/Placed'])


if __name__ == '__main__':
    unittest.main()
