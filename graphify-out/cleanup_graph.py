import json
import os
import shutil
import subprocess
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

import networkx as nx
from graphify.analyze import god_nodes, suggest_questions, surprising_connections
from graphify.cluster import cluster, score_all
from graphify.detect import detect
from graphify.export import to_json
from graphify.report import generate

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / 'graphify-out'
os.chdir(ROOT)
original = json.loads((OUT / 'graph.json').read_text(encoding='utf-8'))
graph = nx.node_link_graph(original, edges='links')
before_nodes, before_edges = graph.number_of_nodes(), graph.number_of_edges()
removed = [node for node, data in graph.nodes(data=True)
           if data.get('source_file', '').replace('\\', '/') == 'AGENTS.md']
graph.remove_nodes_from(removed)
added = []


def source_line(file, text):
    lines = (ROOT / file).read_text(encoding='utf-8').splitlines()
    matches = [i for i, line in enumerate(lines, 1) if text in line]
    if not matches:
        raise ValueError(f'Source evidence no longer exists: {file}: {text}')
    return f'L{matches[0]}'


def link(source, target, relation, file, text):
    location = source_line(file, text)
    if source not in graph or target not in graph:
        raise ValueError(f'Missing graph node: {source} / {target}')
    if not graph.has_edge(source, target):
        graph.add_edge(source, target, relation=relation, confidence='EXTRACTED',
                       confidence_score=1.0, weight=1.0, source_file=file,
                       source_location=location, _origin='source_verified_cleanup')
        added.append(dict(source=source, target=target, source_file=file, source_location=location))


link('object_colors_window_objectcolorswindow_build', 'data_search_search_icon',
     'references', 'object_colors/window.py', "data/search.svg")
link('run_verify_kit', 'tests_verify_kit', 'executes', 'run-verify-kit.ps1', 'tests\\verify_kit.py')
for node, data in list(graph.nodes(data=True)):
    file = data.get('source_file', '')
    label = data.get('label', '')
    if file.startswith('tests/') and label.startswith('test_') and label.endswith('.py'):
        link('run_verify', node, 'executes', 'run-verify.ps1', "pattern='test_*.py'")
    if file.startswith('object_colors/') and label.endswith('.py'):
        source_line('run-typecheck.ps1', "'pyproject.toml'")
        link('run_typecheck', node, 'typechecks', 'pyproject.toml', 'files = ["object_colors"]')
link('docs_verification_usd_tests', 'run_verify', 'references', 'docs/verification.md', '`run-verify.ps1` runs')
link('docs_verification_kit_workflow', 'run_verify_kit', 'references', 'docs/verification.md', '`run-verify-kit.ps1` starts')
link('docs_verification_static_typecheck', 'run_typecheck', 'references', 'docs/verification.md', '`run-typecheck.ps1` runs')
link('docs_verification_synthetic_benchmark', 'tests_benchmark', 'references', 'docs/verification.md', '`run-verify.ps1 -Test tests/benchmark.py`')
link('path', 'pathlib', 'imported_from', 'object_colors/presets.py', 'from pathlib import Path')
graph.nodes['path'].update(label='pathlib.Path', norm_label='pathlib.path', external=True, type='external')

for hyperedge in graph.graph.get('hyperedges', []):
    if not set(hyperedge['nodes']).issubset(graph):
        raise ValueError('A hyperedge contains a removed endpoint')

communities = cluster(graph)
labels = {}
anchors = {
    'object_colors_scheme_scheme': 'Schemes and scene persistence',
    'docs_spec_agreed_scope': 'Requirements and verification evidence',
    'object_colors_discovery': 'Stage discovery and USD tests',
    'object_colors_extension': 'Extension startup and commands',
    'object_colors_overrides_coloroverrides': 'Color bindings and regression tests',
    'object_colors_window_objectcolorswindow': 'Property selection and palette',
    'tests_verify_kit': 'Kit rendering verification',
    'object_colors_controller_controller': 'Controller lifecycle and scheduling',
}
for cid, members in communities.items():
    candidates = Counter(graph.nodes[n].get('community_name', '') for n in members)
    labels[cid] = next((name for node, name in anchors.items() if node in members),
                       candidates.most_common(1)[0][0])
cohesion = score_all(graph, communities)
gods = god_nodes(graph)
surprises = surprising_connections(graph, communities)
questions = suggest_questions(graph, communities, labels)
detection = detect(ROOT)
assert all(Path(file).name != 'AGENTS.md' for files in detection['files'].values() for file in files)
report = generate(graph, communities, cohesion, labels, gods, surprises, detection,
                  {'input': 0, 'output': 0}, str(ROOT), suggested_questions=questions)
report = report.replace('- Token cost: 0 input · 0 output', '- Token cost: no LLM API calls in this cleanup; original Codex extraction usage unavailable.')
report += '\n## Cleanup and coverage\n\nGraphify instructions are excluded by .graphifyignore. Verification launchers and the search icon have source-verified links. pathlib.Path is marked as an external dependency.\n\nThis cleanup started from the exported graph. It does not recover the 13 relationships collapsed during the original extraction. The original diagnostic also counted 53 edges whose endpoints were absent from raw extraction; the exported graph represents their endpoints. See the backup for the original health diagnostic.\n\npyproject.toml produced no nodes in the original AST extraction. Its typecheck configuration was read to verify launcher relationships. The search SVG was inspected as XML rather than rendered.\n'

stamp = datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S%fZ')
backup = OUT / 'backups' / stamp
backup.mkdir(parents=True)
for name in ('graph.json', 'graph.html', 'GRAPH_REPORT.md', '.graphify_labels.json', 'health.json', 'manifest.json'):
    path = OUT / name
    if path.exists():
        shutil.copy2(path, backup / name)

staging = OUT / 'cleanup-staging'
staging.mkdir(exist_ok=True)
assert to_json(graph, communities, str(staging / 'graph.json'), force=True,
               community_labels=labels, built_at_commit=original.get('built_at_commit'))
exported = json.loads((staging / 'graph.json').read_text(encoding='utf-8'))
ids = {node['id'] for node in exported['nodes']}
assert len(ids) == len(exported['nodes'])
assert all(edge['source'] in ids and edge['target'] in ids for edge in exported['links'])
(staging / 'GRAPH_REPORT.md').write_text(report, encoding='utf-8')
(staging / '.graphify_labels.json').write_text(json.dumps(labels, indent=2), encoding='utf-8')
subprocess.run([shutil.which('graphify'), 'export', 'html', '--graph', str(staging / 'graph.json'),
                '--labels', str(staging / '.graphify_labels.json')], check=True,
               env={**os.environ, 'PYTHONHASHSEED': '0'})
assert (staging / 'graph.html').stat().st_size > 1000
for name in ('graph.json', 'graph.html', 'GRAPH_REPORT.md', '.graphify_labels.json'):
    try:
        (staging / name).replace(OUT / name)
    except PermissionError as error:
        if error.winerror != 32:
            raise
        shutil.copyfile(staging / name, OUT / name)
        (staging / name).unlink()
staging.rmdir()
manifest_path = OUT / 'manifest.json'
manifest = json.loads(manifest_path.read_text(encoding='utf-8'))
manifest.pop('AGENTS.md', None)
manifest_path.write_text(json.dumps(manifest, indent=2), encoding='utf-8')
summary = dict(backup=str(backup.relative_to(ROOT)), removed_nodes=removed, added_edges=added,
               before_nodes=before_nodes, after_nodes=graph.number_of_nodes(),
               before_edges=before_edges, after_edges=graph.number_of_edges(),
               isolated_nodes=list(nx.isolates(graph)), communities=labels,
               original_extraction_diagnostic=str((backup / 'health.json').relative_to(ROOT)))
(OUT / 'cleanup.json').write_text(json.dumps(summary, indent=2), encoding='utf-8')
health_path = OUT / 'health.json'
health = json.loads(health_path.read_text(encoding='utf-8'))
health['diagnostic_scope'] = 'Original pre-cleanup extraction; counts above are historical.'
health['current_export'] = dict(nodes=len(graph), edges=graph.number_of_edges(),
                              isolated_nodes=len(list(nx.isolates(graph))), dangling_endpoints=0)
health_path.write_text(json.dumps(health, indent=2), encoding='utf-8')
print(json.dumps(summary, indent=2))
