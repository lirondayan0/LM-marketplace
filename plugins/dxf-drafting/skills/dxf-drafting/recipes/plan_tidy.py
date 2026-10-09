"""Recipe: TIDY a dimension plan = remove redundant dimensions (user's rule: as few as possible, every element still dimensioned). ramla_base.dxf, 2026-10-08.
  python plan_tidy.py USER_FILE --chains CHAINS_FILE -o OUT [--dry] [-v]
Works on the USER's file (their hand edits are the baseline), never regenerates. `--chains` = the file written by plan_chains.py (its handles identify the older, user-approved dims; every other dim is "mine").
Rules (from the user's red clouds on ramla_base-dimplan.dxf, generalised to the whole plan - see conventions/plan-dimensions.md):
 C  every dimension whose TEXT sits inside a red cloud (SHINUIM-TIKUNIM, closed polyline) is deleted - the clouds are the explicit instruction.
 G1 no diameter dimensions on circles (drains / penetrations carry their own labels).
 G2 skewed piers (82_KIR_OLE quadrilaterals, not axis-aligned, 46x123 / 59x203 families): their own size dims (thickness / length, mine or old) go; the spans BETWEEN piers stay.
 G3 shaft/pit blocks: keep only the OVERALL dims (full width / full height); delete every face chain around the block (the continuous pier chains already cross it and give wall thickness + clear spans).
 G4 duplicates: two dims measuring the same two points -> keep one (the older handle).
 G5 one of MY dims measures an interval (same two faces, same direction) that another kept dim within 1500 cm already measures -> delete mine (old user dims are never deleted by G5).
Reports counts per rule, then what each block still carries; writes a NEW file (the user has the file open)."""
import argparse, math, os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'scripts'))
from dxflib import *
import plan_elements as pe

CLOUD_LAYER = 'SHINUIM-TIKUNIM'; NEAR = 45.0; SMALL = 130.0; SHORT = 300.0; TOL = 2.0; NEARV = 1500.0


def clouds(doc):
    out = []
    for e in doc.modelspace().query('LWPOLYLINE'):
        if e.dxf.layer == CLOUD_LAYER and e.closed:
            x0, y0, x1, y1 = pe.bb(pe.pts(e)); out.append((e.dxf.handle, x0, y0, x1, y1))
    return out


def text_pt(d):
    tm = d.dxf.get('text_midpoint')
    return (tm.x, tm.y) if tm is not None else (d.dxf.defpoint.x, d.dxf.defpoint.y)


def dim_line(d):
    p1, p2, dl = d.dxf.defpoint2, d.dxf.defpoint3, d.dxf.defpoint
    ang = math.radians(dim_angle(d)); ux, uy = math.cos(ang), math.sin(ang)
    t1 = (p1.x - dl.x) * ux + (p1.y - dl.y) * uy; t2 = (p2.x - dl.x) * ux + (p2.y - dl.y) * uy
    return (dl.x + ux * t1, dl.y + uy * t1), (dl.x + ux * t2, dl.y + uy * t2)


def axis_of(d):
    a = dim_angle(d) % 180
    return 'h' if abs(a) < 0.5 or abs(a - 180) < 0.5 else 'v' if abs(a - 90) < 0.5 else 'd'


def pair(d):
    p, q = d.dxf.defpoint2, d.dxf.defpoint3
    return (round(p.x), round(p.y)), (round(q.x), round(q.y))


def block_boxes(doc):
    polys, big, circles = pe.inventory(doc); boxes = []
    frames = sorted([q for q in polys if q['layer'] == pe.KORA and q['w'] > 500 and q['hgt'] > 500 and pe.is_rect(q['p'])], key=lambda q: q['w'])
    taken = []
    for f in frames:
        if any(abs(f['box'][0] - t['box'][0]) < 20 and abs(f['box'][1] - t['box'][1]) < 20 for t in taken): continue
        taken.append(f)
    for f in taken:
        x0, y0, x1, y1 = f['box']
        mem = [q for q in polys if q['layer'] == pe.WALL and x0 <= (q['box'][0] + q['box'][2]) / 2 <= x1 and y0 <= (q['box'][1] + q['box'][3]) / 2 <= y1]
        if not mem: continue
        boxes.append((f['h'], min([x0] + [q['box'][0] for q in mem]), min([y0] + [q['box'][1] for q in mem]), max([x1] + [q['box'][2] for q in mem]), max([y1] + [q['box'][3] for q in mem])))
    rot = [q for q in polys if q['layer'] == pe.WALL and len(q['p']) == 4 and not pe.is_rect(q['p']) and (round(q['w'] / 15), round(q['hgt'] / 15)) in ((4, 14), (3, 8), (3, 13), (4, 8))]
    return boxes, rot, circles


def plan(doc, chains_doc, verbose=False):
    ms = doc.modelspace(); old = {e.dxf.handle for e in chains_doc.modelspace()}
    dims = list(ms.query('DIMENSION')); kill = {}   # handle -> rule
    def mark(d, rule): kill.setdefault(d.dxf.handle, rule)
    cl = clouds(doc)
    for d in dims:                                                           # C
        tx, ty = text_pt(d)
        la, lb = dim_line(d)
        for h, x0, y0, x1, y1 in cl:
            on_line = all(x0 - 5 <= px <= x1 + 5 and y0 - 5 <= py <= y1 + 5 for px, py in (la, lb))   # the whole dim line lies in the cloud (text of narrow dims is staggered outside it)
            if (x0 <= tx <= x1 and y0 <= ty <= y1) or on_line:
                if d.dxf.handle in old and d.get_measurement() > SHORT: continue   # long OLD chain dim whose text only touches the cloud: keep
                mark(d, 'C cloud ' + h)
    for h, x0, y0, x1, y1 in cl:                       # a small cloud hugging an element with no dim text inside: the nearest short dim text (<= NEAR away) is meant
        if max(x1 - x0, y1 - y0) >= SMALL or any(r.endswith(h) for r in kill.values()): continue
        best = None
        for d in dims:
            if d.get_measurement() > SHORT or d.dxf.dimtype & 7 not in (0, 1): continue
            tx, ty = text_pt(d); dd = math.hypot(max(x0 - tx, 0, tx - x1), max(y0 - ty, 0, ty - y1))
            if dd <= NEAR and (best is None or dd < best[0]): best = (dd, d)
        if best: mark(best[1], 'C cloud ' + h + ' (nearest)')
    for d in dims:                                                           # G1
        if d.dxf.dimtype & 7 in (3, 4): mark(d, 'G1 diameter')
    boxes, rot, circles = block_boxes(doc)
    for d in dims:                                                           # G2
        if d.dxf.dimtype & 7 != 0: continue
        (ax, ay), (bx, by) = pair(d)
        for q in rot:
            x0, y0, x1, y1 = q['box']
            if all(x0 - 4 <= px <= x1 + 4 and y0 - 4 <= py <= y1 + 4 for px, py in ((ax, ay), (bx, by))): mark(d, 'G2 skewed pier size ' + q['h'])
    for d in dims:                                                           # G3 (only my dims: handle not in the chains file)
        if d.dxf.handle in old or d.dxf.dimtype & 7 != 0: continue
        ax_ = axis_of(d); (ax, ay), (bx, by) = pair(d)
        for h, x0, y0, x1, y1 in boxes:
            if ax_ == 'h' and abs(ay - by) < TOL and x0 - 150 <= min(ax, bx) and max(ax, bx) <= x1 + 150 and (y0 - 150 <= ay <= y0 + 1 or y1 - 1 <= ay <= y1 + 150):
                full = abs(min(ax, bx) - x0) < TOL and abs(max(ax, bx) - x1) < TOL
                if not full: mark(d, 'G3 face chain (x) ' + h)
            if ax_ == 'v' and abs(ax - bx) < TOL and y0 - 150 <= min(ay, by) and max(ay, by) <= y1 + 150 and (x0 - 150 <= ax <= x0 + 1 or x1 - 1 <= ax <= x1 + 150):
                full = abs(min(ay, by) - y0) < TOL and abs(max(ay, by) - y1) < TOL
                if not full: mark(d, 'G3 face chain (y) ' + h)
    seen = {}                                                                # G4
    for d in sorted(dims, key=lambda d: (d.dxf.handle not in old, int(d.dxf.handle, 16))):
        if d.dxf.handle in kill or d.dxf.dimtype & 7 != 0: continue
        k = (axis_of(d),) + tuple(sorted(pair(d)))
        if k in seen: mark(d, 'G4 duplicate of ' + seen[k])
        else: seen[k] = d.dxf.handle
    keep = [d for d in dims if d.dxf.handle not in kill and d.dxf.dimtype & 7 == 0]            # G5: my dim repeats an interval another kept dim already measures nearby (same faces -> no second dimension)
    def span(d):
        (ax, ay), (bx, by) = pair(d); k = axis_of(d)
        return (k, min(ax, bx), max(ax, bx), ay) if k == 'h' else (k, min(ay, by), max(ay, by), ax) if k == 'v' else None
    for d in sorted(keep, key=lambda d: (d.dxf.handle not in old, int(d.dxf.handle, 16))):
        if d.dxf.handle in old or d.dxf.handle in kill: continue
        sp = span(d)
        if sp is None: continue
        for o in keep:
            if o is d or o.dxf.handle in kill: continue
            so = span(o)
            if so and so[0] == sp[0] and abs(so[1] - sp[1]) <= TOL and abs(so[2] - sp[2]) <= TOL and abs(so[3] - sp[3]) <= NEARV and (o.dxf.handle in old or int(o.dxf.handle, 16) < int(d.dxf.handle, 16)):
                mark(d, 'G5 interval already measured by ' + o.dxf.handle); break
    return kill, boxes, dims


def apply(doc, kill):
    ms = doc.modelspace(); n = 0
    for e in list(ms.query('DIMENSION')):
        if e.dxf.handle in kill:
            name = e.dxf.get('geometry')
            ms.delete_entity(e); n += 1
            if name and name in doc.blocks:
                try: doc.blocks.delete_block(name, safe=False)
                except Exception: pass
    return n


def main():
    ap = argparse.ArgumentParser(); ap.add_argument('file'); ap.add_argument('--chains', required=True); ap.add_argument('-o', required=True)
    ap.add_argument('--dry', action='store_true'); ap.add_argument('-v', action='store_true')
    a = ap.parse_args(); doc = ezdxf.readfile(a.file); cd = ezdxf.readfile(a.chains)
    n0 = len(doc.modelspace().query('DIMENSION'))
    kill, boxes, dims = plan(doc, cd)
    by = collections.Counter(r.split(' ')[0] for r in kill.values())
    print('dimensions', n0, '-> delete', len(kill), dict(by))
    if a.v:
        for h, r in sorted(kill.items(), key=lambda t: t[1]): print(' ', h, r)
    if a.dry: return
    n = apply(doc, kill); print('deleted', n); doc.saveas(a.o); print('saved', a.o)


if __name__ == '__main__': main()
