"""Map authored scalar properties to logical objects and renderable targets."""

from dataclasses import dataclass, field
import math
from pxr import Usd, UsdGeom

from .scheme import ObjectRecord

HOOPS = 'omni:hoops:metadata:'
SPATIAL_TYPES = {'IFCPROJECT', 'IFCSITE', 'IFCBUILDING', 'IFCBUILDINGSTOREY'}


@dataclass
class Scan:
    objects: list[ObjectRecord] = field(default_factory=list)
    properties: list[str] = field(default_factory=list)
    issues: list[str] = field(default_factory=list)

    def unavailable_reason(self, mode: str) -> str:
        if mode == 'Property':
            return '' if self.properties else 'No authored scalar object properties were found.'
        return '' if any(getattr(o, mode.lower()) for o in self.objects) else (
            'No source layer provenance is available.' if mode == 'File' else
            'No model asset metadata or objectColors:model mapping is available.')


def _properties(prim):
    values = {}
    for attr in prim.GetAuthoredAttributes():
        key = attr.GetName()
        if not (attr.IsCustom() or key.startswith(HOOPS)) or key.startswith('objectColors:'):
            continue
        if attr.GetTypeName().isArray:
            continue
        value = attr.Get()
        if type(value) in (str, bool, int, float) and not (isinstance(value, float) and not math.isfinite(value)):
            values[key] = value
    return values


def _provenance(prim):
    file = ''
    for spec in prim.GetPrimStack():
        if not spec.layer.anonymous and (spec.typeName or spec.referenceList.GetAppliedItems()):
            file = spec.layer.realPath or spec.layer.identifier
            break
    model = ''
    current = prim
    while current and not current.IsPseudoRoot():
        attr = current.GetAttribute('objectColors:model')
        if attr and attr.Get():
            model = str(attr.Get())
            break
        api = Usd.ModelAPI(current)
        if api.GetAssetName():
            model = api.GetAssetName()
            break
        if api.GetAssetIdentifier().path:
            model = api.GetAssetIdentifier().path
            break
        current = current.GetParent()
    return file, model


def scan_stage(stage) -> Scan:
    steps = scan_steps(stage)
    while True:
        try:
            next(steps)
        except StopIteration as done:
            return done.value


def scan_steps(stage):
    result = Scan()
    source_roots = set()
    for prim in stage.Traverse():
        if prim.IsInstance():
            refs = prim.GetMetadata('references')
            for ref in refs.GetAppliedItems() if refs else []:
                if not ref.assetPath and ref.primPath and stage.GetPrimAtPath(ref.primPath):
                    source_roots.add(ref.primPath)
    for path in source_roots:
        result.issues.append(f'{path}: instance source geometry is excluded; color the placed instances instead')
    owners: dict[str, str | None] = {}
    properties = {}
    targets: dict[str, list[str]] = {}
    provenance = {}
    for index, prim in enumerate(stage.Traverse()):
        if index % 128 == 0:
            yield index
        path = str(prim.GetPath())
        if path.startswith('/__ObjectColors') or any(prim.GetPath().HasPrefix(p) for p in source_roots):
            continue
        parent = str(prim.GetParent().GetPath())
        owner = owners.get(parent)
        values = _properties(prim)
        kind = str(values.get(HOOPS + 'TYPE', ''))
        is_object = bool(values) and kind not in SPATIAL_TYPES
        if is_object or (not owner and (prim.IsInstance() or prim.IsA(UsdGeom.Gprim))):
            owner = path
            properties[path] = values
            targets[path] = []
            provenance[path] = _provenance(prim)
        owners[path] = owner
        if prim.IsA(UsdGeom.PointInstancer):
            result.issues.append(f'{path}: point instancers are not supported; expose objects as native instances')
        elif owner and (prim.IsInstance() or prim.IsA(UsdGeom.Gprim)):
            targets[owner].append(path)
    for path, renderables in targets.items():
        if renderables:
            file, model = provenance[path]
            result.objects.append(ObjectRecord(path, properties[path], file, model, tuple(renderables)))
    result.properties = sorted({k for obj in result.objects for k in obj.properties})
    return result


def property_label(key: str) -> str:
    return key.removeprefix(HOOPS).replace(':', ' / ')
