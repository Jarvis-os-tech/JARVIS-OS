"""Runs only inside bubblewrap. Build and inspection are separate processes.

The inspection process never executes model-authored Python. It loads BREP solids
from the build process and independently measures, checks and exports them.
"""
from __future__ import annotations

import ast
from collections import Counter
import json
import math
from pathlib import Path
import resource
import sys


def limits():
    resource.setrlimit(resource.RLIMIT_CPU, (100, 105))
    resource.setrlimit(resource.RLIMIT_AS, (3 * 1024**3, 3 * 1024**3))
    resource.setrlimit(resource.RLIMIT_FSIZE, (24 * 1024**2, 24 * 1024**2))
    resource.setrlimit(resource.RLIMIT_NOFILE, (128, 128))
    resource.setrlimit(resource.RLIMIT_CORE, (0, 0))
    resource.setrlimit(resource.RLIMIT_NPROC, (128, 128))


def validate_source(source):
    tree = ast.parse(source)
    for node in ast.walk(tree):
        if isinstance(node, (ast.Import, ast.ImportFrom)):
            names = [n.name for n in node.names] if isinstance(node, ast.Import) else [node.module]
            if getattr(node, 'level', 0) or any(n not in {'build123d', 'math'} for n in names):
                raise ValueError('Only build123d and math may be imported.')
            if any(n.name.startswith('_') or (n.asname and n.asname.startswith('_')) for n in node.names):
                raise ValueError('Private imports are not supported.')
        if isinstance(node, ast.Attribute) and (node.attr.startswith('_') or isinstance(node.ctx, (ast.Store, ast.Del))):
            raise ValueError('Private access and attribute assignment are not allowed; return shapes in parts.')
        if isinstance(node, ast.Name) and (node.id.startswith('__') or node.id in {
            'open', 'exec', 'eval', 'compile', 'getattr', 'setattr', 'delattr', 'globals', 'locals',
            'vars', 'input', 'breakpoint', 'help', 'exit', 'quit', 'memoryview', 'type'}):
            raise ValueError('Use geometry operations only.')
        if isinstance(node, (ast.ClassDef, ast.AsyncFunctionDef, ast.AsyncFor, ast.AsyncWith, ast.Global, ast.Nonlocal)):
            raise ValueError('Use ordinary functions and geometry operations only.')
        if isinstance(node, ast.FunctionDef) and node.decorator_list:
            raise ValueError('Function decorators are not supported.')
    return tree


def build():
    import build123d as bd
    source = Path('/input/model.py').read_text()
    tree = validate_source(source)
    design = json.loads(Path('/input/design.json').read_text())
    parameters = {p['name']: p['value'] for p in design['parameters']}
    scope = {'parameters': parameters}
    exec(compile(tree, 'model.py', 'exec'), scope)
    shapes = scope.get('parts')
    expected = {p['id'] for p in design['parts']}
    if not isinstance(shapes, dict) or set(shapes) != expected:
        raise ValueError('The parts dictionary must contain exactly the planned part IDs.')
    for key in expected:
        shape = shapes[key]
        if not isinstance(shape, bd.Shape):
            raise ValueError(f'{key} is not a build123d Shape. Use builder.part for a BuildPart.')
        if not bd.export_brep(shape, f'/output/{key}.brep'):
            raise ValueError(f'Could not preserve solid geometry for {key}.')


def mesh_check(shape):
    vertices, triangles = shape.tessellate(0.08, 0.15)
    if not triangles or len(triangles) > 250000:
        raise ValueError('Mesh is empty or exceeds 250,000 triangles per part.')
    # Weld seam vertices before checking manifold edge incidence and orientation.
    positions = [tuple(round(float(c), 6) for c in v) for v in vertices]
    if any(not math.isfinite(c) for v in positions for c in v):
        raise ValueError('Mesh contains non-finite coordinates.')
    edges, directions = Counter(), Counter()
    for tri in triangles:
        pts = [positions[int(i)] for i in tri]
        if len(set(pts)) != 3:
            continue
        for a, b in zip(pts, pts[1:] + pts[:1]):
            edge = tuple(sorted((a, b)))
            edges[edge] += 1
            directions[edge] += 1 if a < b else -1
    return {'triangles': len(triangles), 'closed_mesh': bool(edges) and all(n == 2 for n in edges.values()),
            'consistent_winding': all(n == 0 for n in directions.values())}


def inspect(preview=False):
    import build123d as bd
    design = json.loads(Path('/input/design.json').read_text())
    output = Path('/output')
    (output / 'parts').mkdir()
    failures, warnings, reports, solids = [], [], [], {}
    for part in design['parts']:
        key = part['id']
        shape = bd.import_brep(f'/input/raw/{key}.brep')
        box = shape.bounding_box()
        size = [float(c) for c in box.size]
        valid = bool(shape.is_valid)
        count = len(shape.solids())
        volume = float(shape.volume)
        if not valid or not math.isfinite(volume) or volume <= 0 or count != 1:
            raise ValueError(f'{key}: expected one valid, positive-volume solid; received {count}.')
        if any(not math.isfinite(c) or not 0.01 <= c <= 2000 for c in size):
            raise ValueError(f'{key}: geometry exceeds the supported size.')
        mesh = mesh_check(shape)
        if not mesh['closed_mesh'] or not mesh['consistent_winding']:
            raise ValueError(f'{key}: mesh is not closed with consistent face winding.')
        matches = all(abs(a - b) <= part['dimension_tolerance_mm'] for a, b in zip(size, part['dimensions_mm']))
        if not matches:
            failures.append(f'{key}: measured envelope {size} mm differs from planned {part["dimensions_mm"]} mm.')
        bed = design.get('printer_build_volume_mm')
        printer_fit = (all(a <= b for a, b in zip(size, bed)) if bed and part['printable'] else None)
        if printer_fit is False:
            failures.append(f'{key}: this part exceeds the specified printer volume in its saved print orientation.')
        shape.label = key
        solids[key] = shape
        files = {}
        if part['printable'] and not preview:
            # Local coordinates are independent of assembly placement. Centre XY and place Z on the bed.
            centred = shape.moved(bd.Location((-box.center().X, -box.center().Y, -box.min.Z)))
            if not bd.export_stl(centred, str(output / 'parts' / f'{key}.stl'), tolerance=0.08, angular_tolerance=0.15):
                raise ValueError(f'{key}: STL export failed.')
            mesher = bd.Mesher(unit=bd.Unit.MM)
            mesher.add_shape(centred, part_number=key)
            mesher.write(str(output / 'parts' / f'{key}.3mf'))
            if not bd.export_step(shape, str(output / 'parts' / f'{key}.step')):
                raise ValueError(f'{key}: STEP export failed.')
            files = {ext: f'parts/{key}.{ext}' for ext in ('stl', '3mf', 'step')}
        reports.append({'id': key, 'name': part['name'], 'printable': part['printable'],
                        'quantity': sum(i['part_id'] == key for i in design['instances']),
                        'dimensions_mm': size, 'volume_mm3': volume, 'valid_solid': valid,
                        'dimensions_match': matches, 'printer_fit': printer_fit, **mesh, 'files': files})
    placed = {}
    palette = ['#55dfcc', '#b59ae8', '#f0c17d', '#77b9dc', '#a5d799', '#e5a2c1']
    for index, instance in enumerate(design['instances']):
        shape = solids[instance['part_id']].moved(bd.Location(instance['position_mm'], instance['rotation_deg']))
        shape.label = instance['id']
        shape.color = bd.Color(palette[index % len(palette)])
        placed[instance['id']] = shape
    pair_reports = []
    ids = list(placed)
    for index, a in enumerate([] if preview else ids):
        for b in ids[index + 1:]:
            sa, sb = placed[a], placed[b]
            common = sa.intersect(sb)
            overlap = (float(common.volume) if isinstance(common, bd.Shape)
                       else sum(float(piece.volume) for piece in common)) if common is not None else 0.0
            distance = float(sa.distance_to(sb))
            if not math.isfinite(overlap) or not math.isfinite(distance):
                raise ValueError('An assembly intersection could not be measured.')
            collision = overlap > 0.01
            pair_reports.append({'a': a, 'b': b, 'overlap_mm3': overlap, 'gap_mm': distance, 'passed': not collision})
            if collision:
                failures.append(f'{a} intersects {b}: {overlap:.3f} cubic mm of overlapping material.')
    connection_reports = []
    for connection in ([] if preview else design['connections']):
        pair = next(p for p in pair_reports if {p['a'], p['b']} == {connection['a'], connection['b']})
        gap = pair['gap_mm']
        passed = pair['passed'] and connection['min_gap_mm'] - 0.01 <= gap <= connection['max_gap_mm'] + 0.01
        connection_reports.append({**connection, 'measured_gap_mm': gap, 'passed': passed})
        if not passed:
            failures.append(f'{connection["name"]}: measured gap {gap:.3f} mm; expected '
                            f'{connection["min_gap_mm"]}–{connection["max_gap_mm"]} mm without overlap.')
    assembly = bd.Compound(label='assembly', children=list(placed.values()))
    if not preview and not bd.export_step(assembly, str(output / 'assembly.step')):
        raise ValueError('Assembly STEP export failed.')
    if not bd.export_gltf(assembly, str(output / 'assembly.glb'), binary=True, linear_deflection=0.12, angular_deflection=0.2):
        raise ValueError('Assembly preview export failed.')
    warnings.append('Work in progress. Assembly checks and final review are pending.' if preview else
                    'Geometry and clearances were checked at the saved assembly pose. Motion, load strength and real print fit require physical testing.')
    if not design.get('printer_build_volume_mm'):
        warnings.append('Printer build volume is unknown; bed fit has not been checked.')
    result = {'passed': not failures, 'parts': reports, 'pairs': pair_reports, 'connections': connection_reports,
              'failures': failures, 'warnings': warnings, 'units': 'mm',
              'assembly_dimensions_mm': list(assembly.bounding_box().size)}
    (output / 'geometry.json').write_text(json.dumps(result, allow_nan=False, indent=2))


if __name__ == '__main__':
    limits()
    try:
        {'build': build, 'inspect': inspect, 'preview': lambda: inspect(preview=True)}[sys.argv[1]]()
    except Exception as error:
        print(f'{type(error).__name__}: {str(error)[:4000]}', file=sys.stderr)
        sys.exit(1)
