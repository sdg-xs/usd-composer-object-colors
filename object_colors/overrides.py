"""Stage-local visualization layer; source geometry and materials are never edited."""

from dataclasses import dataclass, field

from pxr import Gf, Sdf, Usd, UsdGeom, UsdShade


PURPOSES = ('', 'full', 'preview')


@dataclass
class ApplyReport:
    colored: int = 0
    issues: list[str] = field(default_factory=list)


def _linear(hex_color):
    values = [int(hex_color[i:i + 2], 16) / 255 for i in (1, 3, 5)]
    return Gf.Vec3f(*(v / 12.92 if v <= .04045 else ((v + .055) / 1.055) ** 2.4 for v in values))


class ColorOverrides:
    def __init__(self, stage):
        self.stage = stage
        self.layer = None
        self.enabled = True
        self.material_root = '/__ObjectColors'
        while stage.GetPrimAtPath(self.material_root):
            self.material_root += '_'

    def set_enabled(self, enabled: bool):
        self.enabled = enabled
        if self.layer:
            if enabled:
                self.stage.UnmuteLayer(self.layer.identifier)
            else:
                self.stage.MuteLayer(self.layer.identifier)

    def apply(self, assignments: dict[str, str]) -> ApplyReport:
        steps = self.apply_steps(assignments)
        while True:
            try:
                next(steps)
            except StopIteration as done:
                return done.value

    def apply_steps(self, assignments: dict[str, str]):
        report = ApplyReport()
        if self.layer:
            self.stage.MuteLayer(self.layer.identifier)
        try:
            new_layer = Sdf.Layer.CreateAnonymous('object-colors.usda')
            work = Usd.Stage.Open(new_layer)
            batches: dict[tuple[str, str], list[str]] = {}
            checks = []
            for index, (path, color) in enumerate(assignments.items()):
                if index % 64 == 0:
                    yield .4 * index / len(assignments)
                prim = self.stage.GetPrimAtPath(path)
                if not prim or prim.IsInstanceProxy() or prim.IsA(UsdGeom.PointInstancer):
                    report.issues.append(f'{path}: cannot override this instance boundary')
                    continue
                if not any(p.IsA(UsdGeom.Gprim) for p in Usd.PrimRange(prim, Usd.TraverseInstanceProxies())):
                    report.issues.append(f'{path}: no loaded renderable geometry')
                    continue
                root = '/' + path.strip('/').split('/')[0]
                checks.append(path)
                batches.setdefault((root, color), []).append(path)
            authored = 0
            for (root, color), paths in batches.items():
                key = color.removeprefix('#')
                mat_path = self.material_root + '/C' + key
                mat = UsdShade.Material.Get(work, mat_path)
                if not mat:
                    mat = UsdShade.Material.Define(work, mat_path)
                    shader = UsdShade.Shader.Define(work, mat_path + '/Surface')
                    shader.CreateIdAttr('UsdPreviewSurface')
                    shader.CreateInput('diffuseColor', Sdf.ValueTypeNames.Color3f).Set(_linear(color))
                    shader.CreateInput('opacity', Sdf.ValueTypeNames.Float).Set(1.0)
                    shader.CreateInput('opacityThreshold', Sdf.ValueTypeNames.Float).Set(0.0)
                    shader.CreateInput('roughness', Sdf.ValueTypeNames.Float).Set(.65)
                    mat.CreateSurfaceOutput().ConnectToSource(shader.ConnectableAPI(), 'surface')
                root_prim = work.OverridePrim(root)
                name = 'objectColors_' + key
                collection = Usd.CollectionAPI.Apply(root_prim, name)
                collection.CreateExpansionRuleAttr().Set(Usd.Tokens.expandPrims)
                collection.CreateIncludesRel().SetTargets(paths)
                for purpose in PURPOSES:
                    UsdShade.MaterialBindingAPI.Apply(root_prim).Bind(
                        collection, mat, name, UsdShade.Tokens.strongerThanDescendants, purpose)
                # RTX needs a direct binding on the editable instance root.
                for path in paths:
                    if authored % 128 == 0:
                        yield .4 + .4 * authored / len(checks)
                    api = UsdShade.MaterialBindingAPI.Apply(work.OverridePrim(path))
                    for purpose in PURPOSES:
                        api.Bind(mat, UsdShade.Tokens.strongerThanDescendants, purpose)
                    authored += 1
            # Prepend our collections to source collection ordering at each root.
            for root in {k[0] for k in batches}:
                prim = work.GetPrimAtPath(root)
                ours = sorted(r.GetName() for r in prim.GetRelationships() if r.GetName().startswith('material:binding:'))
                prior = self.stage.GetPrimAtPath(root).GetPropertyOrder()
                prim.SetPropertyOrder(ours + [n for n in prior if n not in ours])
            self._replace(new_layer)
            # Reject rather than silently accept a stronger session opinion or unsupported binding.
            rejected = set()
            for index in range(0, len(checks), 128):
                yield .8 + .2 * index / len(checks)
                paths = checks[index:index + 128]
                prims = [self.stage.GetPrimAtPath(path) for path in paths]
                for purpose in PURPOSES:
                    materials, _ = UsdShade.MaterialBindingAPI.ComputeBoundMaterials(prims, purpose)
                    for path, mat in zip(paths, materials):
                        expected = self.material_root + '/C' + assignments[path].removeprefix('#')
                        if not mat or str(mat.GetPath()) != expected:
                            rejected.add(path)
            for path in checks:
                if path in rejected:
                    report.issues.append(f'{path}: existing binding prevented coloring')
                else:
                    report.colored += 1
            if rejected:
                with Sdf.ChangeBlock():
                    for (root, color), paths in batches.items():
                        collection = Usd.CollectionAPI(work.GetPrimAtPath(root), 'objectColors_' + color.removeprefix('#'))
                        collection.GetIncludesRel().SetTargets([p for p in paths if p not in rejected])
                    for path in rejected:
                        prim = work.GetPrimAtPath(path)
                        for purpose in PURPOSES:
                            prim.RemoveProperty('material:binding' + (':' + purpose if purpose else ''))
            return report
        finally:
            self.set_enabled(self.enabled)

    def _replace(self, layer):
        session = self.stage.GetSessionLayer()
        prior = self.layer
        paths = [p for p in session.subLayerPaths if not prior or p != prior.identifier]
        session.subLayerPaths = [layer.identifier] + paths
        self.layer = layer
        if prior:
            self.stage.UnmuteLayer(prior.identifier)

    def close(self):
        if self.layer:
            session = self.stage.GetSessionLayer()
            session.subLayerPaths = [p for p in session.subLayerPaths if p != self.layer.identifier]
            self.stage.UnmuteLayer(self.layer.identifier)
            self.layer = None
