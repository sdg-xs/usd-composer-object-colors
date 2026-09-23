"""Benchmark a generated 3,000-object fixture without opening user scenes."""
import json
from pathlib import Path
from time import perf_counter
from pxr import Sdf, Usd, UsdGeom, UsdShade

from object_colors.discovery import scan_stage
from object_colors.overrides import ColorOverrides
from object_colors.scheme import Scheme, group_objects

stage = Usd.Stage.CreateInMemory()
stage.CreateClassPrim('/Template')
UsdGeom.Cube.Define(stage, '/Template/Shape')
for index in range(3000):
    prim = UsdGeom.Xform.Define(stage, f'/World/Object{index:04}').GetPrim()
    prim.GetReferences().AddInternalReference('/Template')
    prim.SetInstanceable(True)
    prim.CreateAttribute('bim:Level', Sdf.ValueTypeNames.String, custom=True).Set(f'Level {index % 20:02}')
source = stage.GetRootLayer().ExportToString()
start = perf_counter()
scan = scan_stage(stage)
scan_seconds = perf_counter() - start
scheme = Scheme(property_key='bim:Level', enabled=True)
groups = group_objects(scan.objects, scheme)
colors = {p: g.color for g in groups for p in g.objects}
assignments = {path: color for path, color in colors.items() if color is not None}
overrides = ColorOverrides(stage)
start = perf_counter()
report = overrides.apply(assignments)
apply_seconds = perf_counter() - start
assert report.colored == 3000, report.issues[:5]
overrides.close()
assert stage.GetRootLayer().ExportToString() == source
result = dict(objects=len(scan.objects), properties=len(scan.properties), groups=len(groups),
              colored=report.colored, issues=report.issues,
              scan_seconds=scan_seconds, apply_seconds=apply_seconds)
output = Path(__file__).resolve().parent.parent / 'verification'
output.mkdir(exist_ok=True)
(output / 'benchmark.json').write_text(json.dumps(result, indent=2), encoding='utf-8')
print(json.dumps(result, indent=2))
