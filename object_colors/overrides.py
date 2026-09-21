"""Stage-local visualization layer; source geometry and materials are never edited."""

from dataclasses import dataclass, field
import hashlib
import math

from pxr import Gf, Sdf, Usd, UsdGeom, UsdShade


PURPOSES = ('', 'full', 'preview')


@dataclass
class ApplyReport:
    colored: int = 0
    issues: list[str] = field(default_factory=list)


def _renderables(prim):
    return [p for p in Usd.PrimRange(prim, Usd.TraverseInstanceProxies())
            if p.IsA(UsdGeom.Gprim) or p.IsA(UsdGeom.Subset)]


def _opacity(prim, purpose):
    mat, _ = UsdShade.MaterialBindingAPI(prim).ComputeBoundMaterial(purpose)
    if not mat:
        opacity = UsdGeom.PrimvarsAPI(prim).FindPrimvarWithInheritance('displayOpacity')
        if opacity and opacity.GetAttr().GetNumTimeSamples():
            raise ValueError('animated opacity is not supported')
        values = opacity.ComputeFlattened() if opacity else None
        if values and len(set(values)) != 1:
            raise ValueError('varying displayOpacity requires a material adapter')
        return (float(values[0]) if values else 1.0, 0.0)
    shader, _, _ = mat.ComputeSurfaceSource()
    if not shader or shader.GetIdAttr().Get() != 'UsdPreviewSurface':
        raise ValueError('only USD Preview Surface opacity is supported')
    values = []
    for name, default in (('opacity', 1.0), ('opacityThreshold', 0.0)):
        inp = shader.GetInput(name)
        if inp and inp.GetAttr().GetNumTimeSamples():
            raise ValueError('animated opacity is not supported')
        if inp and inp.HasConnectedSource():
            raise ValueError('connected opacity requires a material adapter')
        value = inp.Get() if inp else None
        number = float(default if value is None else value)
        if not math.isfinite(number):
            raise ValueError('non-finite opacity is not supported')
        values.append(number)
    return tuple(values)


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
            batches: dict[tuple, list[str]] = {}
            checks = {}
            for index, (path, color) in enumerate(assignments.items()):
                if index % 64 == 0:
                    yield .6 * index / max(1, len(assignments))
                prim = self.stage.GetPrimAtPath(path)
                if not prim or prim.IsInstanceProxy() or prim.IsA(UsdGeom.PointInstancer):
                    report.issues.append(f'{path}: cannot override this instance boundary')
                    continue
                targets = _renderables(prim)
                if not targets:
                    report.issues.append(f'{path}: no loaded renderable geometry')
                    continue
                profiles = []
                try:
                    if prim.IsInstance():
                        for purpose in PURPOSES:
                            opacities = {_opacity(target, purpose) for target in targets}
                            if len(opacities) != 1:
                                raise ValueError('mixed opacity inside a native instance; use non-instance geometry to color its parts')
                            profiles.append((path, purpose, opacities.pop()))
                    else:
                        for target in targets:
                            for purpose in PURPOSES:
                                profiles.append((str(target.GetPath()), purpose, _opacity(target, purpose)))
                except ValueError as exc:
                    report.issues.append(f'{path}: {exc}')
                    continue
                root = '/' + path.strip('/').split('/')[0]
                checks[path] = [str(p.GetPath()) for p in targets]
                expansion = Usd.Tokens.expandPrims if prim.IsInstance() else Usd.Tokens.explicitOnly
                for target, purpose, opacity in profiles:
                    batches.setdefault((root, purpose, color, opacity, expansion), []).append(target)
            for (root, purpose, color, opacity, expansion), paths in batches.items():
                key = hashlib.sha256(repr((color, opacity)).encode()).hexdigest()[:16]
                mat_path = self.material_root + '/C' + key
                mat = UsdShade.Material.Get(work, mat_path)
                if not mat:
                    mat = UsdShade.Material.Define(work, mat_path)
                    shader = UsdShade.Shader.Define(work, mat_path + '/Surface')
                    shader.CreateIdAttr('UsdPreviewSurface')
                    shader.CreateInput('diffuseColor', Sdf.ValueTypeNames.Color3f).Set(_linear(color))
                    shader.CreateInput('opacity', Sdf.ValueTypeNames.Float).Set(opacity[0])
                    shader.CreateInput('opacityThreshold', Sdf.ValueTypeNames.Float).Set(opacity[1])
                    shader.CreateInput('roughness', Sdf.ValueTypeNames.Float).Set(.65)
                    mat.CreateSurfaceOutput().ConnectToSource(shader.ConnectableAPI(), 'surface')
                root_prim = work.OverridePrim(root)
                for index, path in enumerate(paths):
                    if index % 128 == 0:
                        yield .7
                    target = work.OverridePrim(path)
                    UsdShade.MaterialBindingAPI.Apply(target).Bind(mat, UsdShade.Tokens.strongerThanDescendants, purpose)
                name = 'objectColors_' + key + '_' + (purpose or 'all') + '_' + expansion
                collection = Usd.CollectionAPI.Apply(root_prim, name)
                collection.CreateExpansionRuleAttr().Set(expansion)
                collection.CreateIncludesRel().SetTargets(paths)
                UsdShade.MaterialBindingAPI.Apply(root_prim).Bind(
                    collection, mat, name, UsdShade.Tokens.strongerThanDescendants, purpose)
            # Prepend our collections to source collection ordering at each root.
            for root in {k[0] for k in batches}:
                prim = work.GetPrimAtPath(root)
                ours = sorted(r.GetName() for r in prim.GetRelationships() if r.GetName().startswith('material:binding:'))
                prior = self.stage.GetPrimAtPath(root).GetPropertyOrder()
                prim.SetPropertyOrder(ours + [n for n in prior if n not in ours])
            self._replace(new_layer)
            # Reject rather than silently accept a stronger session opinion or unsupported binding.
            rejected = set()
            for index, (path, targets) in enumerate(checks.items()):
                if index % 64 == 0:
                    yield .8 + .2 * index / max(1, len(checks))
                if all(str(UsdShade.MaterialBindingAPI(self.stage.GetPrimAtPath(p)).ComputeBoundMaterial(purpose)[0].GetPath()).startswith(self.material_root + '/')
                       for p in targets for purpose in PURPOSES):
                    report.colored += 1
                else:
                    report.issues.append(f'{path}: existing binding prevented coloring')
                    rejected.update(targets)
                    rejected.add(path)
            if rejected:
                for prim in work.Traverse():
                    for rel in prim.GetRelationships():
                        if rel.GetName().startswith('collection:') and rel.GetName().endswith(':includes'):
                            rel.SetTargets([p for p in rel.GetTargets() if str(p) not in rejected])
                for path in rejected:
                    prim = work.GetPrimAtPath(path)
                    if prim:
                        for purpose in PURPOSES:
                            name = 'material:binding' + (':' + purpose if purpose else '')
                            prim.RemoveProperty(name)
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
