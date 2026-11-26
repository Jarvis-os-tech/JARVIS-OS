"""Geometry-based plate planning. All transforms use millimetres and XYZ Euler angles.

Overhang area is a recommendation, not a bridge/strength simulation. Sliced
toolpaths are authoritative. Bounding-box spacing is deliberately conservative.
"""
import hashlib
import math
import struct
from pathlib import Path

import numpy as np

from .. import cad
from ..projects import store

BED = 260
MARGIN = 20  # preserves the previous 12 mm envelope plus skirt/brim clearance
GAP = 8
ROTATIONS = [('Original', [0, 0, 0]), ('Back face', [180, 0, 0]),
             ('Front face', [90, 0, 0]), ('Rear face', [-90, 0, 0]),
             ('Left face', [0, 90, 0]), ('Right face', [0, -90, 0])]


def read_stl(path):
    data = Path(path).read_bytes()
    if len(data) < 84:
        raise ValueError('The saved part mesh is incomplete.')
    count = struct.unpack_from('<I', data, 80)[0]
    if not 0 < count <= 1000000 or len(data) != 84 + count * 50:
        raise ValueError('Expected a bounded binary CAD STL.')
    dtype = np.dtype([('normal', '<f4', (3,)), ('points', '<f4', (3, 3)), ('attr', '<u2')])
    triangles = np.frombuffer(data, dtype=dtype, offset=84)['points'].astype(float)
    if not np.isfinite(triangles).all():
        raise ValueError('The part has invalid coordinates.')
    return triangles


def write_stl(path, triangles):
    dtype = np.dtype([('normal', '<f4', (3,)), ('points', '<f4', (3, 3)), ('attr', '<u2')])
    records = np.zeros(len(triangles), dtype=dtype)
    records['points'] = triangles
    normals = np.cross(triangles[:, 1] - triangles[:, 0], triangles[:, 2] - triangles[:, 0])
    lengths = np.linalg.norm(normals, axis=1)
    records['normal'] = normals / np.maximum(lengths[:, None], 1e-20)
    Path(path).write_bytes(b'Ada reviewed build plate'.ljust(80, b'\0') + struct.pack('<I', len(records)) + records.tobytes())


def transformed(triangles, rotation, position=(0, 0)):
    x, y, z = np.radians(rotation)
    cx, cy, cz, sx, sy, sz = math.cos(x), math.cos(y), math.cos(z), math.sin(x), math.sin(y), math.sin(z)
    matrix = (np.array([[1, 0, 0], [0, cx, -sx], [0, sx, cx]]) @
              np.array([[cy, 0, sy], [0, 1, 0], [-sy, 0, cy]]) @
              np.array([[cz, -sz, 0], [sz, cz, 0], [0, 0, 1]]))
    points = triangles @ matrix.T
    low, high = points.min(axis=(0, 1)), points.max(axis=(0, 1))
    points -= [(low[0] + high[0]) / 2, (low[1] + high[1]) / 2, low[2]]
    points += [*position, 0]
    return points


def metrics(points, angle=45):
    cross = np.cross(points[:, 1] - points[:, 0], points[:, 2] - points[:, 0])
    twice_area = np.linalg.norm(cross, axis=1)
    nz = cross[:, 2] / np.maximum(twice_area, 1e-20)
    low, high = points.min(axis=(0, 1)), points.max(axis=(0, 1))
    bottom = points[:, :, 2].max(axis=1) <= .06
    overhang = (nz < -math.cos(math.radians(angle))) & (points[:, :, 2].mean(axis=1) > .25)
    contact = float((twice_area[bottom] / 2).sum())
    area = float((twice_area[overhang] / 2).sum())
    return {'size_mm': (high - low).round(3).tolist(), 'bounds': [low.round(3).tolist(), high.round(3).tolist()],
            'contact_mm2': round(contact, 1), 'overhang_mm2': round(area, 1),
            'support_recommended': area > 5, 'brim_recommended': bool(contact < 40 or contact < (high[2] - low[2]) * 2)}


def recommendations(triangles):
    result = []
    for label, rotation in ROTATIONS:
        m = metrics(transformed(triangles, rotation))
        score = m['overhang_mm2'] * 3 + m['size_mm'][2] * 2 - min(m['contact_mm2'], 1000) * .2
        result.append({'label': label, 'rotation': rotation, **m, 'score': score})
    return sorted(result, key=lambda r: r['score'])


def source(project_id, revision_id):
    saved = cad.revision(project_id, revision_id)
    if saved.get('preview') or saved['status'] != 'ready' or not saved['review']['passed']:
        raise ValueError('Finish the CAD checks before preparing a print.')
    return saved


def mesh_path(project_id, saved, part_id):
    part = next((p for p in saved['geometry']['parts'] if p['id'] == part_id and p['printable']), None)
    if not part:
        raise ValueError('Select a printable part from this CAD revision.')
    path = store.path(project_id, saved['path'] + '/' + part['files']['stl'])
    if path.is_symlink() or not path.is_file():
        raise ValueError('The saved part mesh is unavailable.')
    return path


def catalogue(project_id, revision_id):
    saved = source(project_id, revision_id)
    parts = []
    for part in saved['geometry']['parts']:
        if not part['printable']:
            continue
        design = next(p for p in saved['design']['parts'] if p['id'] == part['id'])
        path = mesh_path(project_id, saved, part['id'])
        parts.append({**part, 'notes': design['print_notes'], 'material': design['material'],
                      'path': saved['path'] + '/' + part['files']['stl'],
                      'sha256': hashlib.sha256(path.read_bytes()).hexdigest(),
                      'orientations': recommendations(read_stl(path))})
    instances = [{'id': f"{p['id']}-{n+1}", 'part_id': p['id'],
                  'rotation': p['orientations'][0]['rotation'], 'position': [130, 130]}
                 for p in parts for n in range(p['quantity'])]
    arranged = arrange(instances, {p['id']: read_stl(mesh_path(project_id, saved, p['id'])) for p in parts})
    return {'project_id': project_id, 'revision_id': saved['id'], 'title': saved['design']['name'],
            'stale': saved['stale'], 'parts': parts, 'instances': arranged['instances'],
            'layout_errors': arranged['errors'], 'bed_mm': [BED, BED, BED], 'margin_mm': MARGIN}


def arrange(instances, meshes, gap=GAP):
    prepared = [(i.copy(), metrics(transformed(meshes[i['part_id']], i['rotation']))) for i in instances]
    prepared.sort(key=lambda p: p[1]['size_mm'][0] * p[1]['size_mm'][1], reverse=True)
    boxes, result, errors = [], [], []
    for item, m in prepared:
        w, h = m['size_mm'][:2]
        candidates = []
        for x in sorted({MARGIN, *(b[2] + gap for b in boxes)}):
            for y in sorted({MARGIN, *(b[3] + gap for b in boxes)}):
                if x + w > BED - MARGIN or y + h > BED - MARGIN:
                    continue
                if any(x < b[2] + gap - .01 and x+w+gap > b[0]+.01 and y < b[3]+gap-.01 and y+h+gap > b[1]+.01 for b in boxes):
                    continue
                candidates.append((y, x))
        if not candidates:
            errors.append(f"{item['id']} does not fit. Remove a part and prepare another plate.")
            item['position'] = [130, 130]
        else:
            y, x = min(candidates)
            boxes.append([x, y, x+w, y+h]); item['position'] = [round(x+w/2, 3), round(y+h/2, 3)]
        result.append(item)
    return {'instances': result, 'errors': errors}


def inspect(request, *, output=None, auto_arrange=False):
    saved = source(request['project_id'], request['revision_id'])
    meshes = {i['part_id']: read_stl(mesh_path(request['project_id'], saved, i['part_id'])) for i in request['instances']}
    if auto_arrange:
        return arrange(request['instances'], meshes, gap=12 if request['brim'] else GAP)
    errors, warnings, reports, transformed_parts, hashes = [], [], [], [], {}
    if len({i['id'] for i in request['instances']}) != len(request['instances']):
        errors.append('Every plate copy needs a unique ID.')
    if saved['stale'] and not request['acknowledge_stale']:
        errors.append('This is an earlier CAD revision. Acknowledge the saved version or regenerate CAD.')
    for item in request['instances']:
        points = transformed(meshes[item['part_id']], item['rotation'], item['position'])
        report = {'id': item['id'], **metrics(points, request['support_angle'])}
        low, high = report['bounds']
        if min(low[:2]) < MARGIN-.01 or max(high[:2]) > BED-MARGIN+.01 or high[2] > BED:
            errors.append(f"{item['id']}: outside the usable plate. Move or rotate this part.")
        if report['support_recommended']:
            warnings.append(f"{item['id']}: {report['overhang_mm2']:g} mm² of downward-facing overhang. Inspect bridges and support access in the sliced preview.")
            if request['supports'] == 'off':
                warnings.append(f"{item['id']}: supports are off despite the overhang recommendation.")
        if report['brim_recommended'] and not request['brim']:
            warnings.append(f"{item['id']}: small bed contact; consider a brim or a wider face down.")
        for previous in reports:
            a, b = previous['bounds']
            spacing = 12 if request['brim'] else GAP
            if all(low[k] < b[k]+spacing-.01 and high[k]+spacing > a[k]+.01 for k in (0, 1)):
                errors.append(f"{item['id']} and {previous['id']}: leave at least {spacing} mm between parts.")
        reports.append(report); transformed_parts.append(points)
        path = mesh_path(request['project_id'], saved, item['part_id'])
        hashes[item['part_id']] = hashlib.sha256(path.read_bytes()).hexdigest()
    if output and not errors:
        write_stl(output, np.concatenate(transformed_parts))
    return {'valid': not errors, 'errors': errors, 'warnings': warnings, 'parts': reports,
            'source_hashes': hashes, 'title': saved['design']['name'], 'stale': saved['stale']}
