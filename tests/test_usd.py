import unittest
from pxr import Gf, Sdf, Usd, UsdGeom, UsdShade

from object_colors.overrides import ColorOverrides
from object_colors.discovery import property_label, scan_stage


def material(stage, path, opacity=1.0):
    mat = UsdShade.Material.Define(stage, path)
    shader = UsdShade.Shader.Define(stage, path + '/Surface')
    shader.CreateIdAttr('UsdPreviewSurface')
    shader.CreateInput('diffuseColor', Sdf.ValueTypeNames.Color3f).Set(Gf.Vec3f(.2, .3, .4))
    shader.CreateInput('opacity', Sdf.ValueTypeNames.Float).Set(opacity)
    mat.CreateSurfaceOutput().ConnectToSource(shader.ConnectableAPI(), 'surface')
    return mat


def fixture():
    stage = Usd.Stage.CreateInMemory()
    UsdGeom.Xform.Define(stage, '/World')
    mat = material(stage, '/World/Looks/Glass', .35)
    stage.CreateClassPrim('/Library')
    mesh = UsdGeom.Cube.Define(stage, '/Library/Shape')
    UsdShade.MaterialBindingAPI.Apply(mesh.GetPrim()).Bind(mat)
    for name in ('A', 'B'):
        root = UsdGeom.Xform.Define(stage, '/World/' + name).GetPrim()
        root.GetReferences().AddInternalReference('/Library')
        root.SetInstanceable(True)
        root.CreateAttribute('bim:Level', Sdf.ValueTypeNames.String, custom=True).Set(name)
    return stage


class ColoringTests(unittest.TestCase):
    def test_cancelled_replacement_keeps_the_previous_color_layer(self):
        stage = fixture()
        overrides = ColorOverrides(stage)
        try:
            first = overrides.apply({'/World/A': '#E15759'})
            self.assertEqual(first.colored_paths, ['/World/A'])
            prior = overrides.layer
            steps = overrides.apply_steps({'/World/A': '#4E79A7'})
            while overrides.layer is prior:
                next(steps)
            steps.close()
            self.assertIs(overrides.layer, prior)
            self.assertEqual(list(stage.GetSessionLayer().subLayerPaths), [prior.identifier])
            material = UsdShade.MaterialBindingAPI(stage.GetPrimAtPath('/World/A/Shape')).ComputeBoundMaterial()[0]
            self.assertEqual(str(material.GetPath()), overrides.material_root + '/CE15759')
        finally:
            overrides.close()

    def test_apply_report_names_unsupported_paths(self):
        stage = fixture()
        overrides = ColorOverrides(stage)
        try:
            report = overrides.apply({'/World/A': '#E15759', '/Absent': '#E15759'})
            self.assertEqual(report.colored_paths, ['/World/A'])
            self.assertEqual(report.unsupported_paths, ['/Absent'])
            self.assertEqual(report.unsupported, 1)
        finally:
            overrides.close()

    def test_user_geometry_named_like_the_extension_is_still_discovered(self):
        stage = Usd.Stage.CreateInMemory()
        UsdGeom.Xform.Define(stage, '/__ObjectColorsBuilding')
        UsdGeom.Cube.Define(stage, '/__ObjectColorsBuilding/Shape')
        self.assertEqual([o.path for o in scan_stage(stage).objects], ['/__ObjectColorsBuilding'])

    def test_hoops_property_labels_retain_source_context(self):
        self.assertNotEqual(property_label('TYPE'), property_label('omni:hoops:metadata:TYPE'))

    def test_solid_xform_color_ignores_display_opacity_and_keeps_model_mapping(self):
        stage = Usd.Stage.CreateInMemory()
        root = UsdGeom.Xform.Define(stage, '/World').GetPrim()
        root.CreateAttribute('objectColors:model', Sdf.ValueTypeNames.String, custom=True).Set('Architecture')
        UsdGeom.PrimvarsAPI(root).CreatePrimvar('displayOpacity', Sdf.ValueTypeNames.FloatArray, 'constant').Set([.25])
        UsdGeom.Cube.Define(stage, '/World/Cube')
        self.assertEqual(scan_stage(stage).objects[0].model, 'Architecture')
        overrides = ColorOverrides(stage)
        report = overrides.apply({'/World': '#E15759'})
        self.assertEqual(report.colored, 1, report.issues)
        mat = UsdShade.MaterialBindingAPI(stage.GetPrimAtPath('/World/Cube')).ComputeBoundMaterial()[0]
        self.assertAlmostEqual(mat.ComputeSurfaceSource()[0].GetInput('opacity').Get(), 1.0)
        overrides.close()
        self.assertAlmostEqual(UsdGeom.PrimvarsAPI(root).GetPrimvar('displayOpacity').Get()[0], .25)

    def test_visible_internal_instance_sources_are_excluded_with_a_notice(self):
        stage = fixture()
        stage.GetPrimAtPath('/Library').SetSpecifier(Sdf.SpecifierDef)
        scan = scan_stage(stage)
        self.assertEqual({o.path for o in scan.objects}, {'/World/A', '/World/B'})
        self.assertTrue(any('instance source' in issue for issue in scan.issues))

    def test_collection_purpose_bindings_and_refresh_restore_exact_source(self):
        stage = fixture()
        root = stage.GetPrimAtPath('/World')
        collection = Usd.CollectionAPI.Apply(root, 'original')
        collection.CreateIncludesRel().SetTargets(['/World/A'])
        original = material(stage, '/World/Looks/Original', .6)
        api = UsdShade.MaterialBindingAPI.Apply(root)
        for purpose in ('', 'full', 'preview'):
            api.Bind(collection, original, 'original', UsdShade.Tokens.strongerThanDescendants, purpose)
        source = stage.GetRootLayer().ExportToString()
        overrides = ColorOverrides(stage)
        for color in ('#E15759', '#4E79A7', '#59A14F'):
            report = overrides.apply({'/World/A': color})
            self.assertEqual(report.colored, 1, report.issues)
            self.assertEqual(len(stage.GetSessionLayer().subLayerPaths), 1)
        # No color removes the feature's opinion rather than unbinding the object.
        overrides.apply({})
        for purpose in ('', 'full', 'preview'):
            restored = UsdShade.MaterialBindingAPI(stage.GetPrimAtPath('/World/A/Shape')).ComputeBoundMaterial(purpose)[0]
            self.assertEqual(restored.GetPath(), original.GetPath())
        overrides.close()
        self.assertEqual(stage.GetRootLayer().ExportToString(), source)

    def test_connected_opacity_does_not_block_solid_color_and_restores(self):
        stage = fixture()
        shader = UsdShade.Shader.Get(stage, '/World/Looks/Glass/Surface')
        texture = UsdShade.Shader.Define(stage, '/World/Looks/Glass/Alpha')
        texture.CreateIdAttr('UsdUVTexture')
        shader.GetInput('opacity').ConnectToSource(texture.ConnectableAPI(), 'a')
        overrides = ColorOverrides(stage)
        report = overrides.apply({'/World/A': '#E15759'})
        self.assertEqual(report.colored, 1, report.issues)
        self.assertEqual(report.issues, [])
        mat = UsdShade.MaterialBindingAPI(stage.GetPrimAtPath('/World/A/Shape')).ComputeBoundMaterial()[0]
        self.assertAlmostEqual(mat.ComputeSurfaceSource()[0].GetInput('opacity').Get(), 1.0)
        overrides.close()
        restored = UsdShade.MaterialBindingAPI(stage.GetPrimAtPath('/World/A/Shape')).ComputeBoundMaterial()[0]
        self.assertEqual(str(restored.GetPath()), '/World/Looks/Glass')
        self.assertTrue(shader.GetInput('opacity').HasConnectedSource())

    def test_mdl_only_material_is_colored_and_restored(self):
        stage = fixture()
        mat = UsdShade.Material.Get(stage, '/World/Looks/Glass')
        mat.GetPrim().RemoveProperty('outputs:surface')
        shader = UsdShade.Shader.Define(stage, '/World/Looks/Glass/Mdl')
        shader.SetSourceAsset(Sdf.AssetPath('OmniPBR.mdl'), 'mdl')
        shader.SetSourceAssetSubIdentifier('OmniPBR', 'mdl')
        shader.CreateOutput('out', Sdf.ValueTypeNames.Token)
        mat.CreateSurfaceOutput('mdl').ConnectToSource(shader.ConnectableAPI(), 'out')
        source = stage.GetRootLayer().ExportToString()
        overrides = ColorOverrides(stage)
        try:
            report = overrides.apply({'/World/A': '#E15759'})
            self.assertEqual(report.colored, 1, report.issues)
            for purpose in ('', 'full', 'preview'):
                bound = UsdShade.MaterialBindingAPI(stage.GetPrimAtPath('/World/A/Shape')).ComputeBoundMaterial(purpose)[0]
                self.assertAlmostEqual(bound.ComputeSurfaceSource()[0].GetInput('opacity').Get(), 1.0)
            overrides.apply({})
            restored = UsdShade.MaterialBindingAPI(stage.GetPrimAtPath('/World/A/Shape')).ComputeBoundMaterial()[0]
            self.assertEqual(restored.GetPath(), mat.GetPath())
            self.assertEqual(restored.ComputeSurfaceSource('mdl')[0].GetPath(), shader.GetPath())
            self.assertEqual(stage.GetRootLayer().ExportToString(), source)
        finally:
            overrides.close()

    def test_stronger_session_collection_rejects_only_its_xform(self):
        stage = fixture()
        original = UsdShade.Material.Get(stage, '/World/Looks/Glass')
        with Usd.EditContext(stage, stage.GetSessionLayer()):
            root = stage.GetPrimAtPath('/World')
            collection = Usd.CollectionAPI.Apply(root, 'sessionPriority')
            collection.CreateIncludesRel().SetTargets(['/World/A'])
            api = UsdShade.MaterialBindingAPI.Apply(root)
            for purpose in ('', 'full', 'preview'):
                api.Bind(collection, original, 'sessionPriority', UsdShade.Tokens.strongerThanDescendants, purpose)
            root.SetPropertyOrder([r.GetName() for r in root.GetRelationships()
                                   if r.GetName().startswith('material:binding:')])
        overrides = ColorOverrides(stage)
        report = overrides.apply({'/World/A': '#E15759', '/World/B': '#E15759'})
        self.assertEqual(report.colored, 1, report.issues)
        self.assertEqual(report.issues, ['/World/A: existing binding prevented coloring'])
        included = Usd.CollectionAPI(stage.GetPrimAtPath('/World'), 'objectColors_E15759').GetIncludesRel().GetTargets()
        self.assertEqual(included, [Sdf.Path('/World/B')])
        overrides.close()

    def test_mixed_opacity_instance_and_subsets_use_one_solid_xform_color(self):
        stage = fixture()
        solid = material(stage, '/World/Looks/Solid', 1.0)
        second = UsdGeom.Cube.Define(stage, '/Library/Solid')
        UsdShade.MaterialBindingAPI.Apply(second.GetPrim()).Bind(solid)
        UsdGeom.Xform.Define(stage, '/World/Object')
        mesh = UsdGeom.Mesh.Define(stage, '/World/Object/Mesh')
        subset = UsdGeom.Subset.Define(stage, '/World/Object/Mesh/GlassFaces')
        subset.CreateFamilyNameAttr('materialBind')
        subset.CreateElementTypeAttr('face')
        subset.CreateIndicesAttr([0])
        UsdShade.MaterialBindingAPI.Apply(mesh.GetPrim()).Bind(solid)
        UsdShade.MaterialBindingAPI.Apply(subset.GetPrim()).Bind(UsdShade.Material.Get(stage, '/World/Looks/Glass'))
        overrides = ColorOverrides(stage)
        source = stage.GetRootLayer().ExportToString()
        report = overrides.apply({'/World/A': '#E15759', '/World/Object': '#E15759'})
        self.assertEqual(report.colored, 2, report.issues)
        self.assertEqual(report.issues, [])
        parts = [('/World/A/Shape', .35), ('/World/A/Solid', 1.0),
                 ('/World/Object/Mesh', 1.0), ('/World/Object/Mesh/GlassFaces', .35)]
        for path, _ in parts:
            mat = UsdShade.MaterialBindingAPI(stage.GetPrimAtPath(path)).ComputeBoundMaterial()[0]
            self.assertAlmostEqual(mat.ComputeSurfaceSource()[0].GetInput('opacity').Get(), 1.0)
            self.assertTrue(str(mat.GetPath()).startswith(overrides.material_root + '/'))
            self.assertIsNone(overrides.layer.GetPrimAtPath(path))
        overrides.close()
        for path, expected in parts:
            mat = UsdShade.MaterialBindingAPI(stage.GetPrimAtPath(path)).ComputeBoundMaterial()[0]
            self.assertAlmostEqual(mat.ComputeSurfaceSource()[0].GetInput('opacity').Get(), expected, places=5)
        self.assertEqual(stage.GetRootLayer().ExportToString(), source)

    def test_discovery_counts_a_multimesh_object_once_and_keeps_qualified_keys(self):
        stage = Usd.Stage.CreateInMemory()
        obj = UsdGeom.Xform.Define(stage, '/World/Wall').GetPrim()
        for key, value in [('bim:instance:Workset', 'Level 1'), ('bim:type:Workset', 'Walls')]:
            obj.CreateAttribute(key, Sdf.ValueTypeNames.String, custom=True).Set(value)
        UsdGeom.Cube.Define(stage, '/World/Wall/A')
        UsdGeom.Cube.Define(stage, '/World/Wall/B')
        result = scan_stage(stage)
        self.assertEqual(len(result.objects), 1)
        self.assertEqual(result.objects[0].path, '/World/Wall')
        self.assertEqual(set(result.properties), {'bim:instance:Workset', 'bim:type:Workset'})

    def test_solid_instance_color_leaves_other_instance_unchanged_and_restores(self):
        stage = fixture()
        source = stage.GetRootLayer().ExportToString()
        original = UsdShade.MaterialBindingAPI(stage.GetPrimAtPath('/World/A/Shape')).ComputeBoundMaterial()[0].GetPath()
        overrides = ColorOverrides(stage)
        report = overrides.apply({'/World/A': '#E15759'})
        self.assertEqual(report.colored, 1, report.issues)
        a = UsdShade.MaterialBindingAPI(stage.GetPrimAtPath('/World/A/Shape')).ComputeBoundMaterial()[0]
        b = UsdShade.MaterialBindingAPI(stage.GetPrimAtPath('/World/B/Shape')).ComputeBoundMaterial()[0]
        self.assertNotEqual(a.GetPath(), original)
        self.assertEqual(b.GetPath(), original)
        shader = a.ComputeSurfaceSource()[0]
        self.assertAlmostEqual(shader.GetInput('opacity').Get(), 1.0, places=5)
        self.assertTrue(stage.GetPrimAtPath('/World/A').IsInstance())
        overrides.set_enabled(False)
        self.assertEqual(UsdShade.MaterialBindingAPI(stage.GetPrimAtPath('/World/A/Shape')).ComputeBoundMaterial()[0].GetPath(), original)
        overrides.close()
        self.assertEqual(stage.GetRootLayer().ExportToString(), source)
        self.assertEqual(list(stage.GetSessionLayer().subLayerPaths), [])


if __name__ == '__main__':
    unittest.main()
