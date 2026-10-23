#!/usr/bin/env python
"""Find (and with --fix delete) DOUBLED entities inside the framed section rows (user 2026-10-22: '2-2 has double reinforcement' - stale dots of two earlier draws of the same cell sat
on the new section, because clear_cell did not remove INSERT 'dot barzel').
    python cell_dupes.py FILE [--fix] [--tol 0.3]
Duplicate = same type + layer + same geometry (INSERT: name + point, rotation; LINE / LWPOLYLINE: vertices; TEXT: text + point; CIRCLE; DIMENSION: defpoints) within TOL, for every entity
whose centre lies in a 72_MISGERET_WIN row polyline. Also reports 'foreign' coincidences: a rebar dot (INSERT 'dot barzel' or 2-vertex 57 polyline <4 wide) lying within 1 of ANOTHER dot of
a different kind (the double reinforcement look). --fix keeps the first (lowest handle) of each group; snapshot first (.bak-dupes-HHMMSS). Importable: dupes(doc) -> list of groups.
Run it after every draw / replace (sections_round does)."""
import argparse, os, shutil, sys, time
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'scripts'))
import ezdxf
from ezdxf import bbox


def frames(doc):
    out = []
    for e in doc.modelspace().query('LWPOLYLINE'):
        if e.dxf.layer == '72_MISGERET_WIN':
            p = [(q[0], q[1]) for q in e.get_points('xy')]
            out.append((min(q[0] for q in p), min(q[1] for q in p), max(q[0] for q in p), max(q[1] for q in p)))
    return out


def key(e, tol):
    r = lambda v: round(v / tol)
    t = e.dxftype(); L = e.dxf.layer
    if t == 'INSERT': return (t, L, e.dxf.name, r(e.dxf.insert.x), r(e.dxf.insert.y), r(e.dxf.rotation))
    if t == 'LINE': a, b = sorted(((r(e.dxf.start.x), r(e.dxf.start.y)), (r(e.dxf.end.x), r(e.dxf.end.y)))); return (t, L, a, b)
    if t == 'LWPOLYLINE': return (t, L, tuple(sorted((r(p[0]), r(p[1])) for p in e.get_points('xy'))))
    if t == 'TEXT': return (t, L, e.dxf.text, r(e.dxf.insert.x), r(e.dxf.insert.y))
    if t == 'CIRCLE': return (t, L, r(e.dxf.center.x), r(e.dxf.center.y), r(e.dxf.radius))
    if t == 'DIMENSION': return (t, L, r(e.dxf.defpoint.x), r(e.dxf.defpoint.y), r(e.dxf.defpoint2.x), r(e.dxf.defpoint2.y), r(e.dxf.defpoint3.x), r(e.dxf.defpoint3.y))
    return None


def dupes(doc, tol=0.3):
    fr = frames(doc); groups = {}
    for e in doc.modelspace():
        if e.dxf.layer in ('72_MISGERET_WIN', 'claude') or e.dxftype() in ('XLINE', 'RAY'): continue
        k = key(e, tol)
        if k is None: continue
        try: b = bbox.extents([e], fast=True)
        except Exception: continue
        if not b.has_data: continue
        c = b.center
        if not any(x0 <= c.x <= x1 and y0 <= c.y <= y1 for x0, y0, x1, y1 in fr): continue
        groups.setdefault(k, []).append(e)
    return [sorted(g, key=lambda e: int(e.dxf.handle, 16)) for g in groups.values() if len(g) > 1]


if __name__ == '__main__':
    ap = argparse.ArgumentParser(); ap.add_argument('file'); ap.add_argument('--fix', action='store_true'); ap.add_argument('--tol', type=float, default=0.3); a = ap.parse_args()
    doc = ezdxf.readfile(a.file); G = dupes(doc, a.tol)
    n = sum(len(g) - 1 for g in G)
    for g in G[:30]: print(g[0].dxftype(), g[0].dxf.layer, [e.dxf.handle for e in g])
    print(n, 'doubled entity(ies) in', len(G), 'group(s)')
    if a.fix and n:
        shutil.copy2(a.file, a.file + time.strftime('.bak-dupes-%H%M%S'))
        for g in G:
            for e in g[1:]: doc.modelspace().delete_entity(e)
        doc.saveas(a.file); print('deleted', n, '(first of each group kept)')
