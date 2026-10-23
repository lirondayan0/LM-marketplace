"""Recipe: HOLLOW-CORE VOIDS in Revit XREF sections (user 2026-10-23, 3841-CON_test.dxf:
'wherever the section cuts through a hollow-core slab, add the slab's voids to the section').
  python xref_cores.py FILE [--only 1,2,..] [--dry] [--write] [--expect MTIME]
RULE (his convention, conventions/section-drawings.md 'Which drawing for a hollow-core slab' + 'obrounds'): the cut crosses the panels (they run PAST the beam / wall, no bearing) when the slab
meets the stem / wall face WITHOUT a ledge; a slab resting on a ledge is seen lengthwise = no voids. Per side of the XREF section:
  hollow-core = the slab has an A-FLOR-MCUT topping line (T = slab top - topping line); no MCUT = solid slab -> no voids;
  no ledge on that side (no horizontal S-BEAM-1 line at the beam's extreme x between bottom and top) and the slab abuts the face -> voids.
Voids = OBROUNDS (ledge_beam.core_row / obround: 16.8 x 25.2 for a panel p = D - T = 40, scaled by p / 40; layer 10_PLADA_HATAH), centre soffit + p/2 + 0.8, first one >= 8.3 from the face,
pitch >= 20, up to 3 within min(slab length, 58.9). Slab resting ON TOP of a beam / shelf (slab end at the beam's far face, Sec 32) = bearing = no voids. UNVERIFIED against the plan's span arrows."""
import argparse, os, shutil, sys, time
HERE = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, HERE); sys.path.insert(0, os.path.join(HERE, '..', 'scripts'))
import ezdxf
import xref_overlay as XO
import ledge_beam as LB

LAYER = LB.CORE_LAYER
VOID_COLOR = 3         # GREEN (ACI 3) - user 2026-10-23: 'the marking of the voids should be green'; entities are BYLAYER, the layer carries the colour
cover = lambda e: e


def side_slabs(blk):
    """per side of an XREF section block: dict(sd -> slab) with face (x of the slab end nearest the beam / wall), far (x of the other end), top, soffit, T, ledge. Beam from S-BEAM-1, else from A-WALL-1 faces."""
    L = [s for s in blk if s.dxftype() == 'LINE']
    pt = XO.pt; lay = XO.lay
    beam = [(pt(s.dxf.start), pt(s.dxf.end)) for s in L if lay(s) == 'S-BEAM-1']
    wall = [pt(p) for s in L if lay(s) == 'A-WALL-1' for p in (s.dxf.start, s.dxf.end)]
    flr = [(pt(s.dxf.start), pt(s.dxf.end)) for s in L if lay(s) == 'A-FLOR-1' and abs(s.dxf.start.y - s.dxf.end.y) < 0.5]
    cut = [(pt(s.dxf.start)[1], min(s.dxf.start.x, s.dxf.end.x), max(s.dxf.start.x, s.dxf.end.x)) for s in L if lay(s) == 'A-FLOR-MCUT']
    if not flr: return {}
    if beam:
        xs = [p[0] for a, b in beam for p in (a, b)]; ys = [p[1] for a, b in beam for p in (a, b)]; bx0, bx1, yb, yt = min(xs), max(xs), min(ys), max(ys)
    elif wall:
        bx0, bx1, yb, yt = min(p[0] for p in wall), max(p[0] for p in wall), min(p[1] for p in wall), max(p[1] for p in wall)
    else: return {}
    hor = [(a[1], min(a[0], b[0]), max(a[0], b[0])) for a, b in beam if abs(a[1] - b[1]) < 0.5]
    out = {}
    for sd in ('left', 'right'):
        inn = (lambda xa, xb: max(xa, xb) <= bx0 + 0.5) if sd == 'left' else (lambda xa, xb: min(xa, xb) >= bx1 - 0.5)       # the slab line lies wholly beside the beam block
        outl = (lambda xa, xb: min(xa, xb) < bx0 - 0.5) if sd == 'left' else (lambda xa, xb: max(xa, xb) > bx1 + 0.5)
        ln = [(a, b) for a, b in flr if outl(a[0], b[0])]
        if not ln: continue
        ys_ = [a[1] for a, b in ln]
        if max(ys_) - min(ys_) < 1: continue
        top, soffit = max(ys_), min(ys_)
        sl = [(a, b) for a, b in ln if abs(a[1] - soffit) < 0.5][0]
        xa, xb = sorted((sl[0][0], sl[1][0]))
        cy = [y for y, c0, c1 in cut if outl(c0, c1)]
        xe = bx0 if sd == 'left' else bx1
        led = [h for h in hor if yb + 0.5 < h[0] < yt - 0.5 and ((abs(h[1] - xe) < 0.5) if sd == 'left' else (abs(h[2] - xe) < 0.5))]
        out[sd] = dict(face=xb if sd == 'left' else xa, far=xa if sd == 'left' else xb, top=top, soffit=soffit, T=(top - max(cy)) if cy else None, ledge=bool(led), bx=(bx0, bx1))
    return out


def decide(sd, s, n):
    """(draw?, reason)"""
    if s['T'] is None: return False, 'no topping line = solid slab'
    if s['ledge']: return False, 'on a ledge = panels seen lengthwise (bearing)'
    gap = (s['bx'][0] - s['face']) if sd == 'left' else (s['face'] - s['bx'][1])
    if gap < -1.0: return False, 'slab overlaps the beam / rests on it (bearing)'
    return True, 'abuts the face, no ledge = cut crosses the panels'


def cores_for(sd, s):
    D = s['top'] - s['soffit']; T = s['T']; p = D - T
    if p < 8: return []
    k = p / 40.0; W, Hh = 16.8 * k, 25.2 * k; first = max(8.3, W / 2 + 3.3); pitch = max(20.0, W + 3)
    avail = min(abs(s['far'] - s['face']), LB.CAST_SLAB_END); sg = -1 if sd == 'left' else 1
    n = max(1, min(3, int((avail - 1.5 - W / 2 - first) // pitch) + 1))
    cy = s['soffit'] + p / 2 + 0.8
    return [(s['face'] + sg * (first + pitch * j), cy, W, Hh) for j in range(n)]


def main():
    ap = argparse.ArgumentParser(); ap.add_argument('file'); ap.add_argument('--only'); ap.add_argument('--dry', action='store_true'); ap.add_argument('--write', action='store_true'); ap.add_argument('--expect', type=float)
    a = ap.parse_args()
    if a.expect and abs(os.path.getmtime(a.file) - a.expect) > 1: sys.exit('file changed since it was read (mtime) - re-read first')
    t0 = time.time(); doc = ezdxf.readfile(a.file); print(f'loaded in {time.time() - t0:.0f}s'); msp = doc.modelspace()
    if LAYER not in doc.layers: print('layer', LAYER, 'missing - creating'); doc.layers.add(LAYER, color=VOID_COLOR)
    elif doc.layers.get(LAYER).color != VOID_COLOR: print('layer', LAYER, 'colour', doc.layers.get(LAYER).color, '->', VOID_COLOR); doc.layers.get(LAYER).color = VOID_COLOR
    have = [(e.dxf.layer, e) for e in msp.query('LWPOLYLINE') if e.dxf.layer == LAYER]
    secs = XO.xref_sections(doc); only = {int(x) for x in a.only.split(',')} if a.only else None
    total = 0; report = []
    for n, ins in sorted(secs.items()):
        if only and n not in only: continue
        ix, iy = ins.dxf.insert.x, ins.dxf.insert.y; sl = side_slabs(doc.blocks.get(ins.dxf.name))
        if not sl: report.append(f'Sec {n}: no slab found'); continue
        for sd, s in sl.items():
            ok, why = decide(sd, s, n)
            if not ok: report.append(f'Sec {n} {sd}: none - {why}'); continue
            cs = cores_for(sd, s)
            ctr = [(sum(p[0] for p in e.get_points('xy')) / len(e), sum(p[1] for p in e.get_points('xy')) / len(e)) for _, e in have]      # obround centre = mean of its 4 vertices
            near = [c for c in ctr if any(abs(c[0] - (cx + ix)) < 1 and abs(c[1] - (cy + iy)) < 1 for cx, cy, _, _ in cs)]
            if near: report.append(f'Sec {n} {sd}: already has voids - skipped'); continue
            report.append(f'Sec {n} {sd}: {len(cs)} voids {why}; D={s["top"] - s["soffit"]:g} T={s["T"]:g} obround {cs[0][2]:.1f}x{cs[0][3]:.1f}')
            if not a.dry:
                for cx, cy, w, h in cs: LB.obround(msp, cx + ix, cy + iy, w, h, LAYER)
            total += len(cs)
    print('\n'.join(report)); print('voids', total)
    if a.write and total and not a.dry:
        out = a.file
        if os.path.exists(out + '.dwl') or os.path.exists(out + '.dwl2'): sys.exit('file is open in CAD (.dwl) - save + close it, then re-run')
        bak = f'{out}.bak-cores-{time.strftime("%H%M%S")}'; shutil.copy2(out, bak); print('snapshot', bak); doc.saveas(out); print('saved', out)


if __name__ == '__main__': main()


