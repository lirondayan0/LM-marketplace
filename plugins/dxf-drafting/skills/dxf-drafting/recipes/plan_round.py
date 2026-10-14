"""ONE ROUND of the user's mark-driven dimensioning (agreed 2026-10-14):  python plan_round.py FILE --scan          what marks are in the file (read-only)
                                                                    python plan_round.py FILE [--write]   run the round; without --write the result is only built + verified in a temp file
Marks the user draws:  layer `claude_DIM` XLINEs (a dimension line goes there) | layer `claude_Kontur` (closed boundary of the work plan) | clouds on layer `claude`: orange 32 = add faces to the nearest chain,
red 256/1 = missing sizes, blue 152 = extend to the boundary, green 116 = align with the Xline (those are handled by plan_xlines.py's outline / aligned logic).
Stages: plan_xlines.py (Xlines -> chains, orange clouds)  ->  plan_clouds.py (red clouds, XLINEs that miss the plan deleted)  ->  plan_repair.py (text collisions)  ->  VERIFY:
  every dim point inside the boundary (kontur or wall outline), 0 text collisions, no dim line that is not on a user mark or an earlier chain (reported), then --write = snapshot + mtime check + in-place save.
NEVER adds a line the user did not mark; gaps are reported. With --write the claude_DIM XLINEs are deleted after the dims are saved (user 2026-10-14)."""
import os, subprocess, sys, tempfile, shutil, collections, math
HERE = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, HERE); sys.path.insert(0, os.path.join(HERE, '..', 'scripts'))
import ezdxf
import plan_xlines_lf as lf
from dxflib import backup
args = sys.argv[1:]; f = args[0]; scan = '--scan' in args; write = '--write' in args

import block_reader as br          # reads any block: element groups are exploded in the working copy only
def explode_blocks(path):
    d = ezdxf.readfile(path); ms = d.modelspace(); k = lf.kontur_outline(ms)
    within = (min(q[0] for q in k), min(q[1] for q in k), max(q[0] for q in k), max(q[1] for q in k)) if k else None
    saved = br.expand_groups(d, ms, within=within)
    if saved: d.saveas(path)
    return saved
def undo_explode(path, saved):
    d = ezdxf.readfile(path); br.restore_groups(d, saved); d.saveas(path)
def py(script, *a):
    r = subprocess.run([sys.executable, '-I', os.path.join(HERE, script), *a], capture_output=True, text=True, encoding='utf-8')
    out = '\n'.join(l for l in (r.stdout + r.stderr).split('\n') if 'BLOCKREPRESENTATION' not in l)
    if r.returncode: sys.exit('FAILED %s\n%s' % (script, out[-1500:]))
    return out
def marks(doc):
    ms = doc.modelspace(); xl = collections.Counter(e.dxf.layer for e in ms.query('XLINE')); cl = collections.Counter()
    for e in ms.query('LWPOLYLINE'):
        if e.dxf.layer == 'claude': cl[(e.dxf.color, e.dxf.get('true_color'))] += 1
    return xl, cl, lf.kontur_outline(ms)
doc = ezdxf.readfile(f); H0 = {d.dxf.handle for d in doc.modelspace().query('DIMENSION')}; xl, cl, kon = marks(doc); mt = os.path.getmtime(f)
print('file', f, 'mtime', mt, '| XLINEs by layer', dict(xl), '| clouds on layer claude (aci, truecolor): count', dict(cl))
_loops = lf.kontur_loops(doc.modelspace())
print('claude_Kontur boundary:', ('closed loop of %d points' % len(kon)) if kon else ('%d closed regions (%s points) - each is processed on its own' % (len(_loops), ', '.join(str(len(l)) for l in _loops))) if len(_loops) > 1 else 'absent or not closed (fallback = biggest closed 82_KIR_OLE polyline)')
_t = lf.dim_template(doc.modelspace()); print('output layer / dim style (red cloud beside the plan):', (_t[0], _t[1]) if _t else 'none marked -> defaults 36_MIDA_CLALI / dim_100')
print('dimensions in file:', len(doc.modelspace().query('DIMENSION')))
if scan: sys.exit(0)

# ---- SEVERAL boundary regions (DIM-app test 2026-10-14: tall region + small region, 26 Xlines across both): one single-region round per region on a working copy, results accumulate, the original claude_Kontur entities are restored at the end
if len(_loops) > 1:
    tmp = tempfile.mkdtemp(); base = os.path.join(tmp, 'base.dxf'); shutil.copyfile(f, base); orig = ezdxf.readfile(f); om = orig.modelspace()
    xls = [(e.dxf.start, e.dxf.unit_vector, e.dxf.layer) for e in om.query('XLINE') if e.dxf.layer in ('claude_DIM', 'claude')]
    def crosses(loop, st, u):
        sg = [(q[0] - st.x) * (-u.y) + (q[1] - st.y) * u.x for q in loop]; return min(sg) <= 1e-6 and max(sg) >= -1e-6
    for k, loop in enumerate(_loops):
        mine = [x for x in xls if crosses(loop, x[0], x[1])]; wk = os.path.join(tmp, 'region%d.dxf' % k); shutil.copyfile(base, wk); dk = ezdxf.readfile(wk); mk = dk.modelspace()
        for e in list(mk):
            if e.dxf.layer.lower() == 'claude_kontur' or (e.dxftype() == 'XLINE' and e.dxf.layer in ('claude_DIM', 'claude')): mk.delete_entity(e)
        mk.add_lwpolyline([(q[0], q[1]) for q in loop], close=True, dxfattribs={'layer': 'claude_Kontur'})
        for st, u, ly in mine: mk.add_xline((st.x, st.y, 0), (u.x, u.y, 0), dxfattribs={'layer': ly})
        dk.saveas(wk); print('--- region %d/%d: %d points, %d Xlines cross it' % (k + 1, len(_loops), len(loop), len(mine)))
        if not mine: print('    no Xline crosses this region: skipped'); continue
        r = subprocess.run([sys.executable, '-I', os.path.abspath(__file__), wk, '--write'], capture_output=True, text=True, encoding='utf-8')
        out = [l for l in (r.stdout + r.stderr).splitlines() if l.strip() and 'BLOCKREPRESENTATION' not in l and not l.startswith(('saved ', 'copy process'))]
        print(chr(10).join('    ' + l[:260] for l in out[-8:]))
        if r.returncode: sys.exit('region %d failed' % (k + 1))
        base = wk
    dfin = ezdxf.readfile(base); mf = dfin.modelspace()
    for e in list(mf):
        if e.dxf.layer.lower() == 'claude_kontur': mf.delete_entity(e)
    for e in om:
        if e.dxf.layer.lower() == 'claude_kontur': mf.add_entity(e.copy())
    for e in list(mf.query('XLINE')):
        if e.dxf.layer == 'claude_DIM': mf.delete_entity(e)
    final = os.path.join(tmp, 'final.dxf'); dfin.saveas(final)
    if not write: print('dry: built in', final); sys.exit(0)
    if abs(os.path.getmtime(f) - mt) > 1: sys.exit('the file was saved meanwhile (user): re-run, building on their save')
    open(f, 'ab').close(); backup(f, 'round'); shutil.copyfile(final, f); print('written', f, '(snapshot taken); claude_DIM XLINEs deleted'); sys.exit(0)
if not (xl.get('claude_DIM') or xl.get('claude') or cl): sys.exit('no marks (no XLINE on claude_DIM / claude, no clouds on layer claude): nothing to do')
tmp = tempfile.mkdtemp(); a, b, c = (os.path.join(tmp, n) for n in ('1.dxf', '2.dxf', '3.dxf'))
f0 = os.path.join(tmp, '0.dxf'); shutil.copyfile(f, f0); saved_blocks = explode_blocks(f0)
print(py('plan_xlines.py', f0, a).strip().split('\n')[-1]); print(py('plan_clouds.py', a, b).strip().split('\n')[-1]); r = py('plan_repair.py', b, c); print(r.strip().split('\n')[-1])
if saved_blocks: undo_explode(c, saved_blocks); print('block INSERTs restored in the result')
# ---- verify
d2 = ezdxf.readfile(c); m2 = d2.modelspace(); bound, src_ = lf.plan_outline(m2); print('boundary used:', src_)
def inside(x, y, tol=4.0):
    c = False
    for i in range(len(bound)):
        (x1, y1), (x2, y2) = bound[i], bound[(i + 1) % len(bound)]
        if (y1 > y) != (y2 > y) and x < x1 + (y - y1) * (x2 - x1) / (y2 - y1): c = not c
        dx, dy = x2 - x1, y2 - y1; t = max(0, min(1, ((x - x1) * dx + (y - y1) * dy) / (dx * dx + dy * dy or 1)))
        if math.hypot(x1 + t * dx - x, y1 + t * dy - y) <= tol: return True
    return c
tag = lambda d: d.has_xdata('CLAUDE_ROWS')
_bx=(min(q[0] for q in bound)-3000,min(q[1] for q in bound)-3000,max(q[0] for q in bound)+3000,max(q[1] for q in bound)+3000)   # other plan copies in the file keep their own dims
near_ = lambda d: _bx[0]<=d.dxf.defpoint2.x<=_bx[2] and _bx[1]<=d.dxf.defpoint2.y<=_bx[3]
new = [d for d in m2.query('DIMENSION') if d.dxf.handle not in H0 and near_(d) and tag(d) and any(t.value in ('xline_dims',) for t in d.get_xdata('CLAUDE_ROWS'))]
out_ = [d for d in new if not all(inside(p.x, p.y) for p in (d.dxf.defpoint2, d.dxf.defpoint3))]
lines = collections.Counter()
for d in m2.query('DIMENSION'):
    ang = d.dxf.get('angle', 0) % 180; p = d.dxf.defpoint
    lines[('X', round(p.y)) if ang < 1 else (('Y', round(p.x)) if abs(ang - 90) < 1 else ('aligned %.1f' % ang, 0))] += 1
print('VERIFY: generated dims', len(new), '| with a measured point outside the boundary:', len(out_), '| dimension lines in file:', len(lines), '| text collisions:', r.strip().split('\n')[-1])
def crossing(axis, v):
    r = []
    for i in range(len(bound)):
        (x1, y1), (x2, y2) = bound[i], bound[(i + 1) % len(bound)]
        if axis == 'X' and (y1 - v) * (y2 - v) < 0: r.append(x1 + (v - y1) * (x2 - x1) / (y2 - y1))
        if axis == 'Y' and (x1 - v) * (x2 - v) < 0: r.append(y1 + (v - x1) * (y2 - y1) / (x2 - x1))
    return sorted(r)
ext = collections.defaultdict(list)
for d in filter(lambda q: near_(q) and q.dxf.handle not in H0, m2.query('DIMENSION')):
    ang = d.dxf.get('angle', 0) % 180; p = d.dxf.defpoint
    if ang < 1: ext[('X', round(p.y, 1))] += [d.dxf.defpoint2.x, d.dxf.defpoint3.x]
    elif abs(ang - 90) < 1: ext[('Y', round(p.x, 1))] += [d.dxf.defpoint2.y, d.dxf.defpoint3.y]
gaps = []
for (ax, v), cc in sorted(ext.items()):
    z = crossing(ax, v)
    if len(cc) < 8 or not z: continue                                  # short / user-drawn lines are not full-width chains
    g0, g1 = min(cc) - z[0], z[-1] - max(cc)
    if g0 > 3 or g1 > 3: gaps.append((ax, v, round(g0), round(g1)))
print('CHAIN ENDS vs boundary: chains short of it by > 3 (axis, line, gap at start, gap at end):', gaps if gaps else 'none')
if out_: print('  OUTSIDE:', [(round(d.dxf.defpoint2.x), round(d.dxf.defpoint2.y)) for d in out_][:8])
if not write: print('dry: built in', c, '(use --write to save over', f, ')'); sys.exit(0)
if abs(os.path.getmtime(f) - mt) > 1: sys.exit('the file was saved meanwhile (user): re-run, building on their save')
open(f, 'ab').close(); backup(f, 'round'); shutil.copyfile(c, f); print('written', f, '(snapshot taken)')
dw = ezdxf.readfile(f); mw = dw.modelspace(); xs = [e for e in mw.query('XLINE') if e.dxf.layer == 'claude_DIM']       # user 2026-10-14: once the dimensions exist, delete the XLINEs
for e in xs: mw.delete_entity(e)
dw.saveas(f); print('deleted', len(xs), 'XLINEs on claude_DIM')
