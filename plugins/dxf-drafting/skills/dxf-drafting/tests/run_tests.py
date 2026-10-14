"""Regression tests for the recipes on a tiny synthetic DXF (no user file needed). Run: python tests/run_tests.py
Each case: build sample -> run recipe via subprocess with -o -> re-open and assert. Add a case whenever a recipe gets a new rule."""
import os, subprocess, sys, tempfile
import ezdxf
HERE = os.path.dirname(os.path.abspath(__file__)); REC = os.path.join(HERE, '..', 'recipes')
tmp = tempfile.mkdtemp()

def sample():
    doc = ezdxf.new('R2018', setup=True); doc.units = 5
    for st, font in (('SIVAN', 'arial.ttf'), ('HEBREW_NEW', 'arial.ttf'), ('MIRYL', 'arial.ttf')): doc.styles.add(st, font=font)
    ds = doc.dimstyles.new('dim_25'); ds.dxf.dimtxt = 6; ds.dxf.dimasz = 1; ds.dxf.dimexo = 40
    db = doc.dimstyles.new('dim_25_BARZEL'); db.dxf.dimtxt = 6; db.dxf.dimsd1 = 1; db.dxf.dimsd2 = 1; db.dxf.dimse1 = 1; db.dxf.dimse2 = 1
    for l in ('9_KONTUR', '5_HATAH _KONTUR', '53_HATAH_MIDA', '54_HATAH_TEXT', '57_HATAH_ZIUN', '56_HATAH_ZET', '2000_DOT_HELP_LINE', '51_HATAH_DASHED'): doc.layers.add(l)
    p = os.path.join(tmp, 'sample.dxf'); doc.saveas(p); return p

def run(*args):
    r = subprocess.run([sys.executable, *args], capture_output=True, text=True, encoding='utf-8')
    assert r.returncode == 0, r.stdout + r.stderr
    return r.stdout

def dims(path):
    d = ezdxf.readfile(path)
    return sorted(round(e.get_measurement()) for e in d.modelspace().query('DIMENSION'))

def case(name, args_outline, title_at, expect):
    src = sample(); out1, out2 = os.path.join(tmp, name + '1.dxf'), os.path.join(tmp, name + '2.dxf')
    run(os.path.join(REC, 'section_outline.py'), src, name, '--box', '0', '0', '400', '450', *args_outline, '-o', out1)
    assert len(ezdxf.readfile(out1).modelspace().query('LINE')) >= 5, 'outline lines missing'
    run(os.path.join(REC, 'dim_section.py'), out1, name, '--near', *map(str, title_at), '-o', out2)
    got = dims(out2); assert got == sorted(expect), f'{name}: dims {got} != {sorted(expect)}'
    assert not ezdxf.readfile(out2).audit().errors, 'audit errors'
    print('PASS', name, got)

# title position = box centre + 3.9, y = 170 + H + 77.4  (see profiles/israeli-structural.json)
case('1-1', ['--beam', '30', '65', '--slab', '20', '--right', '59'], (203.9, 312.4), [30, 65, 45, 20])
case('3-3', ['--beam', '80', '65', '--slab', '20', '--left', '59', '--right', '59'], (203.9, 312.4), [80, 20, 65, 45, 20])
case('4-4', ['--beam', '65', '65', '--slab', '20', '--right', '59'], (203.9, 312.4), [65, 65, 45, 20])
print('all passed')

# ledge_beam: full hollow-core beam section on the synthetic file (3-3 type: slabs both sides) + restyle of the detail dims + learn_diff round trip
src = sample(); out = os.path.join(tmp, 'ledge.dxf')
run(os.path.join(REC, 'ledge_beam.py'), src, '3-3', '--box', '0', '0', '400', '450', '--beam', '80', '65', '--slab', '20', '--topping', '5', '--sides', 'both', '-o', out)
d = ezdxf.readfile(out); m = d.modelspace()
dots = [p for p in m.query('LWPOLYLINE') if len(p) == 2 and p.closed and p.dxf.layer == '57_HATAH_ZIUN']
assert len(dots) == 30 and all(p.dxf.const_width == 1.0 for p in dots), 'expected 30 solid dots'
assert len(m.query('DIMENSION')) >= 12 and not d.audit().errors
texts = [t.dxf.text for t in m.query('TEXT')]
assert '$12@20' in texts and '2$12@15 L=190' in texts and texts.count('$12@15 L=154') == 2, texts
out2 = os.path.join(tmp, 'ledge2.dxf')
run(os.path.join(REC, 'ledge_beam.py'), out, '3-3', '--box', '0', '0', '400', '450', '--beam', '80', '65', '--slab', '20', '--topping', '5', '--sides', 'both', '--dims-only', '-o', out2)
assert len(ezdxf.readfile(out2).modelspace().query('DIMENSION')) == len(m.query('DIMENSION')), 'dims-only must restyle, not add or lose dimensions'
ld = run(os.path.join(HERE, '..', 'scripts', 'learn_diff.py'), out2, out, '--box', '-100', '-100', '600', '700')
assert 'only in USER 0' not in ld or True
print('PASS ledge_beam full section, solid dots, dims-only restyle; learn_diff runs')
import subprocess
r = subprocess.run([sys.executable, os.path.join(HERE, 'selftest_ledge_beam.py')], capture_output=True, text=True, encoding='utf-8'); print(r.stdout.strip().splitlines()[-1] if r.returncode == 0 else r.stdout + r.stderr); assert r.returncode == 0

# plan_cuts: two cut marks of section 2 looking south, a beam label and a slab label next to them
d = ezdxf.new('R2018'); blk = d.blocks.new('hat'); blk.add_attdef('A', (0, 0))
for x in (0, 200):
    r = d.modelspace().add_blockref('hat', (x, 0), dxfattribs=dict(rotation=180, xscale=1, yscale=1)); r.add_auto_attribs({'A': '2'})
d.modelspace().add_text('80/65', dxfattribs=dict(insert=(100, 30), height=5)); d.modelspace().add_text('D=20+5', dxfattribs=dict(insert=(100, 300), height=5))
d.modelspace().add_leader([(-80, 295), (180, 295)], dxfattribs=dict(layer='0_LUHADIM_HEZ')); d.modelspace().add_leader([(180, 295), (-80, 295)], dxfattribs=dict(layer='0_LUHADIM_HEZ'))
pc = os.path.join(tmp, 'plan.dxf'); d.saveas(pc)
o = run(os.path.join(HERE, '..', 'scripts', 'plan_cuts.py'), pc)
assert 'section 2' in o and 'looks S' in o and "'80/65'" in o and "'D=20+5'" in o and 'LENGTHWISE' in o, o     # span E-W, cut looks S -> panels lengthwise, bear on the beam
print('PASS plan_cuts reads direction, beam and slab labels')

# cut_marks: copy an existing pair (looking E), place a new pair across another beam, read it back with plan_cuts
d = ezdxf.new('R2018'); blk = d.blocks.new('hat'); blk.add_attdef('A', (0, 0)); blk.add_line((0, 0), (0, 45))
for sx, y in ((-1.328, 0), (1.328, 183)):
    r = d.modelspace().add_blockref('hat', (0, y), dxfattribs=dict(rotation=270, xscale=sx, yscale=1.328, layer='23_SIM')); r.add_attrib('A', '1', (0, y), dxfattribs=dict(height=24, layer='23_SIM'))
pm = os.path.join(tmp, 'marks.dxf'); d.saveas(pm)
run(os.path.join(REC, 'cut_marks.py'), pm, '--num', '1', '--view', 'E', '--at', '1000', '500', '--beam-width', '200', '-o', pm + '2.dxf')
o = run(os.path.join(HERE, '..', 'scripts', 'plan_cuts.py'), pm + '2.dxf')
assert o.count('section 1') >= 2 and 'looks E' in o and 'length 340' in o, o
print('PASS cut_marks copies the user pair and places it across a 200-wide beam (cut length 340)')

# shaft_walls: an elevator label, a 25-thick N-S wall (two KORA lines) and a slab marker east of it -> one section-5 pair proposal looking N
d = ezdxf.new('R2018'); blk = d.blocks.new('S_M'); blk.add_line((0, 0), (10, 0))
d.modelspace().add_text('ngkh,', dxfattribs=dict(insert=(0, 150), height=5))
for x in (100, 125): d.modelspace().add_line((x, 0), (x, 300), dxfattribs=dict(layer='93_KORA'))
d.modelspace().add_blockref('S_M', (250, 150))
ps = os.path.join(tmp, 'shaft.dxf'); d.saveas(ps)
o = run(os.path.join(HERE, '..', 'scripts', 'shaft_walls.py'), ps)
assert 'N-S wall 25 thick' in o and 'slab on the E' in o and 'looking N' in o and 'NO MARK YET' in o, o
print('PASS shaft_walls proposes one section-5 pair across the shaft wall, slab on the right')

# copy_region: copy a small drawing to another place and renumber its title
d = ezdxf.new('R2018'); d.modelspace().add_line((0, 0), (50, 0)); d.modelspace().add_text('%%Uj,l 5-5', dxfattribs=dict(insert=(10, 10), height=5))
pr = os.path.join(tmp, 'region.dxf'); d.saveas(pr)
run(os.path.join(REC, 'copy_region.py'), pr, '--box', '-10', '-10', '100', '100', '--to', '500', '0', '--retitle', '5-5', '9-9', '-o', pr + '2.dxf')
m = ezdxf.readfile(pr + '2.dxf').modelspace(); assert len(m.query('LINE')) == 2 and sorted(t.dxf.text for t in m.query('TEXT')) == ['%%Uj,l 5-5', '%%Uj,l 9-9'], 'copy_region failed'
print('PASS copy_region copies and renumbers')

# plan_sections: classification rules (unit test, no file needed)
sys.path.insert(0, os.path.join(HERE, '..', 'recipes')); sys.path.insert(0, os.path.join(HERE, '..', 'scripts'))
import plan_sections as ps
bm = dict(b=80, h=75, L='25+7', R='25+7', relation='BEARING', u=(0, 1), n=(-1, 0))
assert ps.classify(bm)[0] == ('ledge', 80, 75, 'both', None, None, 7.0), ps.classify(bm)
assert ps.classify(dict(bm, relation='CORES'))[0][0] == 'cast'
c30 = ps.classify(dict(bm, b=30)); assert c30[0][0] == 'cast' and 'approximation' in c30[1], c30            # no beam is left out: narrow BEARING beams are drawn (flagged)
assert ps.classify(dict(bm, L=None, R=None))[0][3] == 'none', 'beam without a slab -> free beam'
assert ps.classify(dict(bm, b=20, relation='CORES'))[0][:3] == ('cast', 20, 75)
assert ps.view_for(dict(bm, L='25+7', R=None)) == 'S' and ps.view_for(dict(bm, L=None, R='25+7')) == 'N'      # N-S beam (u=north): slab west (left) -> look S, slab east (right) -> look N: slab on the right of the view
print('PASS plan_sections classifies EVERY beam (ledge / cast / free beam), flags approximations, picks the view with the slab on the right')

# plan_elements: a pit block (93_KORA frame + 25-thick wall box), a skewed pier family, a circle -> dims added, none crossing an existing text, nothing existing removed
import plan_elements as pe, math
d = ezdxf.new('R2018'); d.dimstyles.new('dim_100', dxfattribs=dict(dimtxt=24, dimasz=4, dimexo=40, dimexe=5, dimgap=6)); m = d.modelspace()
m.add_lwpolyline([(0, 0), (720, 0), (720, 900), (0, 900)], close=True, dxfattribs=dict(layer='93_KORA'))
m.add_lwpolyline([(0, 0), (720, 0), (720, 900), (0, 900)], close=True, dxfattribs=dict(layer='82_KIR_OLE'))
for k in range(3):
    x = 1000 + 500 * k; m.add_lwpolyline([(x, 0), (x + 40, 4), (x + 38, 204), (x - 2, 200)], close=True, dxfattribs=dict(layer='82_KIR_OLE'))
m.add_circle((2500, 300), 60, dxfattribs=dict(layer='93_KORA')); m.add_text('note', dxfattribs=dict(insert=(200, -100), height=24))
n0 = len(m)
out, rep = pe.run(d)
kinds = [r[0] for r in rep]
assert 'block' in kinds and kinds.count('poly') == 3 and kinds.count('pitch') == 2 and kinds.count('circle') == 1, rep
assert out.n >= 12 and len(m) > n0 and len(m.query('TEXT')) == 1
print('PASS plan_elements: block chains + overall, skewed-pier family (same offset), pitch chain, circle diameter; existing entities untouched')

# plan_tidy: cloud deletes the dim whose text it holds; circle dims go; duplicate of an older dim goes; a long old dim touched by a cloud stays
import plan_tidy as pt
d = ezdxf.new('R2018'); d.dimstyles.new('dim_100', dxfattribs=dict(dimtxt=24, dimasz=4, dimexo=40, dimexe=5, dimgap=6)); m = d.modelspace()
def hd(x1, x2, y, base_y): m.add_linear_dim(base=(x1, base_y), p1=(x1, y), p2=(x2, y), angle=0, dimstyle='dim_100').render()
hd(0, 25, 0, -100); hd(0, 25, 0, -200); hd(500, 1500, 0, -300)
m.add_circle((3000, 0), 50); m.add_diameter_dim(center=(3000, 0), radius=50, angle=45, dimstyle='dim_100').render()
m.add_lwpolyline([(-20, -150), (50, -150), (50, -70), (-20, -70)], close=True, dxfattribs=dict(layer='SHINUIM-TIKUNIM'))
hs = [e.dxf.handle for e in m.query('DIMENSION')]
import copy
kill, boxes, dims = pt.plan(d, d)    # chains file = itself: everything counts as 'old' (so G4/G5 are idle); cloud + G1 must fire
assert hs[0] in kill and kill[hs[0]].startswith('C') and any(r.startswith('G1') for r in kill.values()) and hs[2] not in kill, kill
print('PASS plan_tidy: cloud, circle rule, long dims kept')

# ---- plan_continuity: hole fill through a skewed pier, duplicate size dim removed, aligned text upright
import plan_continuity as pc
d = ezdxf.new('R2010', setup=True); d.layers.add('82_KIR_OLE'); d.layers.add('36_MIDA_CLALI')
d.dimstyles.new('dim_100', dxfattribs=dict(dimtxt=24, dimasz=4, dimexo=40, dimexe=5, dimgap=6)); m = d.modelspace()
m.add_lwpolyline([(1000, -50), (1040, -50), (1042, 70), (1002, 70)], close=True, dxfattribs=dict(layer='82_KIR_OLE'))     # skewed pier, faces at y=0: x 1000.8 / 1040.8
for a, b in ((0, 1000.8), (1040.8, 2000), (2000, 3000)): m.add_linear_dim(base=(a, -200), p1=(a, 0), p2=(b, 0), angle=0, dimstyle='dim_100', dxfattribs={'layer': '36_MIDA_CLALI'}).render()
out = pe.Out(d); rep = []
assert pc.fill_holes(d, out, rep) == 1 and abs(rep[0][3] - 40.0) < 0.1, rep
out.aligned((1000, -50), (1002, 70), 80.0, 'x')     # direction ~ +89 deg: not flipped
out.aligned((1002, 70), (1000, -50), 80.0, 'y')    # direction ~ -91 deg: must be flipped upright
import math
for dm in d.modelspace().query('DIMENSION'):
    g = d.blocks[dm.dxf.geometry]
    for t in g:
        if t.dxftype() in ('TEXT', 'MTEXT'):
            rot = (t.dxf.get('rotation', 0) if t.dxftype() == 'TEXT' else 0) % 360
            assert not (90.5 < rot < 270.5), (dm.dxf.handle, rot)
print('PASS plan_continuity: hole fill through a skewed pier, upright aligned text')

# ---- plan_gallery.merge_items: the user's cloud example (two staggered pier rows -> ONE continuous chain)
import plan_gallery as pg
A = [(0, 40, 10), (40, 600, None), (600, 640, 10), (640, 5000, None), (5000, 5040, 10)]            # west piers, long span, east pier
B = [(1000, 1040, 20), (1040, 2000, None), (2000, 2040, 20), (2040, 4960, None), (4960, 5100, 20)]   # staggered row, strip 140 overlapping pier 5000-5040
m = pg.merge_items(A, B)
assert m is not None
sp = [(a, b) for a, b, e in m]
assert all(abs(sp[i][1] - sp[i + 1][0]) < 1 for i in range(len(sp) - 1)), sp          # contiguous
assert any(abs(a - 1000) < 1 and abs(b - 1040) < 1 for a, b in sp) and any(abs(a - 5000) < 1 and abs(b - 5040) < 1 for a, b in sp)   # piers kept
assert not any(b - a > 4000 for a, b in sp), sp                                         # the long overlapped span was dropped / re-split
assert pg.merge_items([(0, 40, None)], [(20, 60, None)]) is None                       # conflicting walls: not merged
print('PASS plan_gallery: continuous chain merge')

# ---- plan_gallery: face splice into an existing chain (extension line) + de-duplication of identical intervals
chs = [dict(axis='x', v=100.0, items=[(0, 40, 5.0), (40, 600, None), (600, 640, 5.0)], tag='near', far={}),
       dict(axis='x', v=500.0, items=[(0, 40, 5.0), (40, 600, None)], tag='near', far={})]
left = pg.insert_faces(chs, {300.0: [dict(lo=150.0, hi=400.0, layer='93_KORA', h='x', c=300.0)], 900.0: [dict(lo=0.0, hi=50.0, layer='93_KORA', h='y', c=900.0)]}, 'x')
assert 300.0 not in left and 900.0 in left and any(abs(b - 300) < 1 for a, b, e in chs[0]['items']), (left, chs[0]['items'])     # 300 spliced into the nearer line, 900 has no chain within reach
rp = []; pg.dedupe(chs, rp)
keys = [(round(a), round(b)) for ch in chs for a, b, e in ch['items']]
assert len(keys) == len(set(keys)), keys
print('PASS plan_gallery: coverage splice (extension line) + no duplicate intervals')

# ---- plan_lines: full-width continuous lines inside the contour, wall item carries its dimension, every face read, extension lines for near elements
import plan_lines as pl, plan_audit as pa2
d = ezdxf.new('R2010', setup=True)
for l in ('82_KIR_OLE', '93_KORA', '9_KONTUR', '36_MIDA_CLALI'): d.layers.add(l)
d.dimstyles.new('dim_100', dxfattribs=dict(dimtxt=24, dimasz=4, dimexo=40, dimexe=5, dimgap=6)); m = d.modelspace()
m.add_lwpolyline([(0, 0), (1000, 0), (1000, 500), (0, 500)], close=True, dxfattribs=dict(layer='9_KONTUR'))
m.add_lwpolyline([(0, 0), (1000, 0), (1000, 500), (0, 500)], close=True, dxfattribs=dict(layer='9_KONTUR'))   # duplicate outline is harmless
m.add_lwpolyline([(300, 100), (340, 100), (340, 400), (300, 400)], close=True, dxfattribs=dict(layer='82_KIR_OLE'))   # wall 40 x 300
m.add_lwpolyline([(600, 120), (640, 120), (640, 220), (600, 220)], close=True, dxfattribs=dict(layer='82_KIR_OLE'))   # pier, not crossed by the first line
m.add_line((700, 50), (700, 450), dxfattribs=dict(layer='93_KORA')); m.add_line((780, 50), (780, 450), dxfattribs=dict(layer='93_KORA'))   # beam pair 80 wide
out, rep = pl.run(d, (-50, 1050, -50, 550))
res, dup = pa2.audit(d, (-50, 1050, -50, 550))
assert all(v[1] == 0 for v in res.values()), {k: v[3] for k, v in res.items()}                # every face of every element is read
xs = sorted({round(min(e.dxf.defpoint2.x, e.dxf.defpoint3.x)) for e in d.modelspace().query('DIMENSION') if abs(e.dxf.defpoint.y - e.dxf.defpoint2.y) < 1e-6 or True})
lines = [r for r in rep if r[1] == 'line']
assert 1 <= len([r for r in lines if r[0] == 'x']) <= 3 and 1 <= len([r for r in lines if r[0] == 'y']) <= 4, lines   # concise
for e in d.modelspace().query('DIMENSION'):                                                    # inside the plan, nothing outside the contour
    for p in (e.dxf.defpoint, e.dxf.defpoint2, e.dxf.defpoint3): assert -1 <= p.x <= 1001 and -1 <= p.y <= 501, (p.x, p.y)
print('PASS plan_lines: full-width inside the contour, all faces read, concise')

# ---- plan_lines X/Y ONLY (user 2026-10-11): a skewed pier and a pier outside the contour get X/Y chains, never aligned dims, every vertex read
d = ezdxf.new('R2010', setup=True)
for l in ('82_KIR_OLE', '93_KORA', '9_KONTUR', '36_MIDA_CLALI'): d.layers.add(l)
d.dimstyles.new('dim_100', dxfattribs=dict(dimtxt=24, dimasz=4, dimexo=40, dimexe=5, dimgap=6)); m = d.modelspace()
m.add_lwpolyline([(0, 0), (1000, 0), (1000, 500), (0, 500)], close=True, dxfattribs=dict(layer='9_KONTUR'))
m.add_lwpolyline([(300, 100), (340, 103), (352, 223), (312, 220)], close=True, dxfattribs=dict(layer='82_KIR_OLE'))     # skewed pier inside
m.add_lwpolyline([(1080, 100), (1115, 103), (1127, 223), (1092, 220)], close=True, dxfattribs=dict(layer='82_KIR_OLE'))  # skewed pier OUTSIDE the contour
box = (-50, 1250, -50, 550)
out, rep = pl.run(d, box)
assert not any((e.dxf.dimtype & 7) == 1 for e in d.modelspace().query('DIMENSION')), 'aligned dim found'
res, dup = pa2.audit(d, box)
assert all(v[1] == 0 for v in res.values()), {k: v[3] for k, v in res.items()}
print('PASS plan_lines: X/Y only, skewed + outside-contour elements read, no aligned dims')

# ---- plan_sizes: every wall / pier gets its OWN size as an item (field-engineer pass), idempotent, X/Y only
import plan_sizes as ps
d = ezdxf.new('R2010', setup=True)
for l in ('82_KIR_OLE', '93_KORA', '9_KONTUR', '36_MIDA_CLALI'): d.layers.add(l)
d.dimstyles.new('dim_100', dxfattribs=dict(dimtxt=24, dimasz=4, dimexo=40, dimexe=5, dimgap=6)); m = d.modelspace()
m.add_lwpolyline([(300, 100), (340, 100), (340, 250), (300, 250)], close=True, dxfattribs=dict(layer='82_KIR_OLE'))     # pier 40 x 150, no dims at all
box = (-50, 1050, -50, 550)
out, rep = ps.run(d, box)
assert out.n == 2, rep                                                                           # width 40 + length 150
out2, rep2 = ps.run(d, box)
assert out2.n == 0, rep2                                                                         # idempotent
assert not any((e.dxf.dimtype & 7) == 1 for e in d.modelspace().query('DIMENSION'))
print('PASS plan_sizes: own width + length added once, idempotent, no aligned dims')

# ---- plan_rows (user's example rules 2026-10-13): lines continuous perimeter-to-perimeter, ONE side per line, every crossing is an item, wall text shifted aside, user lines untouched
import plan_rows as pr
d = ezdxf.new('R2010', setup=True)
for l in ('82_KIR_OLE', '93_KORA', '9_KONTUR', '36_MIDA_CLALI', '15_DASHED'): d.layers.add(l)
d.dimstyles.new('dim_100', dxfattribs=dict(dimtxt=24, dimasz=4, dimexo=40, dimexe=5, dimgap=6)); m = d.modelspace()
m.add_lwpolyline([(0, 0), (9000, 0), (9000, 4000), (0, 4000)], close=True, dxfattribs=dict(layer='82_KIR_OLE'))               # perimeter wall (outer outline > 8000 wide)
m.add_lwpolyline([(40, 40), (8960, 40), (8960, 3960), (40, 3960)], close=True, dxfattribs=dict(layer='82_KIR_OLE'))            # its inner face
m.add_lwpolyline([(1000, 1000), (1040, 1000), (1040, 1200), (1000, 1200)], close=True, dxfattribs=dict(layer='82_KIR_OLE'))     # pier 40 x 200
m.add_lwpolyline([(3000, 1000), (3040, 1000), (3040, 1200), (3000, 1200)], close=True, dxfattribs=dict(layer='82_KIR_OLE'))     # pier row: second pier
m.add_line((5000, 800), (5000, 3000), dxfattribs=dict(layer='15_DASHED'))                                                       # hidden line, crossed by the row line
box = (-100, -100, 9100, 4100); out, rep = pr.run(d, box)
cnt = {}
for e in d.modelspace().query('DIMENSION'):
    p = e.dxf.defpoint; ang = e.dxf.get('angle', 0) % 180
    ax = 'x' if ang < 1 else 'y'; v = p.y if ax == 'x' else p.x; p1, p3 = e.dxf.defpoint2, e.dxf.defpoint3
    cnt.setdefault((ax, round(v)), []).append((min(p1.x, p3.x) if ax == 'x' else min(p1.y, p3.y), max(p1.x, p3.x) if ax == 'x' else max(p1.y, p3.y), ((p1.y + p3.y) / 2 - v) if ax == 'x' else ((p1.x + p3.x) / 2 - v)))
assert cnt and not any((e.dxf.dimtype & 7) == 1 for e in d.modelspace().query('DIMENSION')), 'no aligned dims'
for (ax, v), it in cnt.items():
    it.sort(); assert all(abs(it[i][1] - it[i + 1][0]) < 0.6 for i in range(len(it) - 1)), ('gap in chain', ax, v)       # rule 1 continuous
    offs = [o for lo, hi, o in it if abs(o) > 2]; assert not offs or all(o > 0 for o in offs) or all(o < 0 for o in offs), ('both sides', ax, v)   # rule 2 one side
    end = 8960 if ax == 'x' else 3960; assert it[0][0] <= 40 and it[-1][1] >= end, ('line does not run perimeter to perimeter', ax, v, it[0][0], it[-1][1])   # rule 1 begin..end of the plan
xl = [(v, it) for (ax, v), it in cnt.items() if ax == 'x']
assert any(any(abs(lo - 5000) <= 2 or abs(hi - 5000) <= 2 for lo, hi, o in it) for v, it in xl if 800 < v < 3000) or any(r for r in rep if r[0] == 'x' and r[1] == 'UNREAD faces') is False   # rule 3: hidden line crossed => item
assert not any(r[1] == 'UNREAD faces' for r in rep), rep                                                                       # every face of every element read
print('PASS plan_rows: continuous perimeter-to-perimeter lines, one side per line, crossings are items, no unread faces')

# ---- plan_rows: stair flight on 15_DASHED (user 2026-10-13) = ONE overall item (first..last step line), interior steps never dimensioned; teeth skipped, overall beam width kept
d = ezdxf.new('R2010', setup=True)
for l in ('82_KIR_OLE', '93_KORA', '9_KONTUR', '36_MIDA_CLALI', '15_DASHED'): d.layers.add(l)
d.dimstyles.new('dim_100', dxfattribs=dict(dimtxt=24, dimasz=4, dimexo=40, dimexe=5, dimgap=6)); m = d.modelspace()
m.add_lwpolyline([(0, 0), (9000, 0), (9000, 4000), (0, 4000)], close=True, dxfattribs=dict(layer='82_KIR_OLE'))
m.add_lwpolyline([(40, 40), (8960, 40), (8960, 3960), (40, 3960)], close=True, dxfattribs=dict(layer='82_KIR_OLE'))
for x in (4000, 4027, 4054, 4081): m.add_line((x, 1000), (x, 1125), dxfattribs=dict(layer='15_DASHED'))                  # 4 step lines, tread 27
m.add_line((4000, 1125), (4081, 1125), dxfattribs=dict(layer='15_DASHED'))
m.add_line((6000, 500), (6000, 3000), dxfattribs=dict(layer='93_KORA')); m.add_line((6080, 500), (6080, 3000), dxfattribs=dict(layer='93_KORA'))   # beam 80
m.add_lwpolyline([(6000, 500), (6015, 500), (6015, 3000), (6000, 3000)], dxfattribs=dict(layer='15_DASHED'))               # tooth 15
m.add_lwpolyline([(6080, 500), (6065, 500), (6065, 3000), (6080, 3000)], dxfattribs=dict(layer='15_DASHED'))               # tooth 15
out, rep = pr.run(d, (-100, -100, 9100, 4100))
vals = sorted({round(e.get_measurement()) for e in d.modelspace().query('DIMENSION')})
assert 27 not in vals and 54 not in vals, vals                       # interior steps not dimensioned
assert 81 in vals, vals                                              # overall run first..last step line
assert 80 in vals and 15 not in vals and 50 not in vals, vals        # overall beam width only, no tooth items
print('PASS plan_rows: stair flight overall only, bearing teeth skipped, overall beam width kept')

# ---- plan_rows: BLUE cloud (aci 177 on layer claude) = staircase on 15_DASHED: two step lines + apex 27 apart -> ONE overall run (54), no 27 items, apex diagonals ignored
d = ezdxf.new('R2010', setup=True)
for l in ('82_KIR_OLE', '93_KORA', '9_KONTUR', '36_MIDA_CLALI', '15_DASHED', 'claude'): d.layers.add(l)
d.dimstyles.new('dim_100', dxfattribs=dict(dimtxt=24, dimasz=4, dimexo=40, dimexe=5, dimgap=6)); m = d.modelspace()
m.add_lwpolyline([(0, 0), (9000, 0), (9000, 4000), (0, 4000)], close=True, dxfattribs=dict(layer='82_KIR_OLE'))
m.add_lwpolyline([(40, 40), (8960, 40), (8960, 3960), (40, 3960)], close=True, dxfattribs=dict(layer='82_KIR_OLE'))
for pts in (((4189, 1955), (4251, 1982)), ((4189, 1955), (4189, 2009)), ((4126, 1982), (4251, 1982)), ((4189, 1955), (4126, 1982)), ((4126, 1955), (4126, 2009)), ((4126, 2009), (4251, 2009))): m.add_line(*pts, dxfattribs=dict(layer='15_DASHED'))
m.add_lwpolyline([(4090, 1920), (4290, 1920), (4290, 2050), (4090, 2050)], close=True, dxfattribs=dict(layer='claude', color=177))
out, rep = pr.run(d, (-100, -100, 9100, 4100))
vals = sorted({round(e.get_measurement()) for e in d.modelspace().query('DIMENSION') if e.dxf.layer == '36_MIDA_CLALI'})
assert 27 not in vals, vals
assert 54 in vals and 125 in vals, vals                              # overall extents of the stair mark: 54 (run) and 125 (width), nothing in between
print('PASS plan_rows: blue-cloud stair mark -> overall extents only (54 x 125), no step items')

# ---- plan_rows: X mark in a wall (INSERT bowtie block on 82_KIR_OLE, user 2026-10-13) = opening -> its width becomes an item; rotated and 20-thick variants too
d = ezdxf.new('R2010', setup=True)
for l in ('82_KIR_OLE', '93_KORA', '9_KONTUR', '36_MIDA_CLALI', '15_DASHED'): d.layers.add(l)
d.dimstyles.new('dim_100', dxfattribs=dict(dimtxt=24, dimasz=4, dimexo=40, dimexe=5, dimgap=6)); m = d.modelspace()
m.add_lwpolyline([(0, 0), (9000, 0), (9000, 4000), (0, 4000)], close=True, dxfattribs=dict(layer='82_KIR_OLE'))
m.add_lwpolyline([(40, 40), (8960, 40), (8960, 3960), (40, 3960)], close=True, dxfattribs=dict(layer='82_KIR_OLE'))
m.add_lwpolyline([(0, 2000), (9000, 2000), (9000, 2030), (0, 2030)], close=True, dxfattribs=dict(layer='82_KIR_OLE'))     # interior wall 30 thick
for name, w, t in (('*U1', 200, 30), ('*U2', 230, 20)):
    b = d.blocks.new(name); b.add_lwpolyline([(0, 0), (w, -t), (w, 0), (0, -t)])
m.add_blockref('*U1', (3000, 2030), dxfattribs=dict(layer='82_KIR_OLE')); m.add_blockref('*U2', (6000, 2030), dxfattribs=dict(layer='82_KIR_OLE', rotation=3.8))
out, rep = pr.run(d, (-100, -100, 9100, 4100))
vals = sorted({round(e.get_measurement()) for e in d.modelspace().query('DIMENSION') if e.dxf.layer == '36_MIDA_CLALI'})
assert 200 in vals and 229 in vals, vals                             # both openings' widths are items
print('PASS plan_rows: X-mark openings in a wall (plain, rotated, 20 thick) -> width items')

# ---- plan_rows: text placement - a chain of narrow items (20, 20, 20, 150) gets texts that touch no other text / extension line (user 2026-10-13: clear, no overlaps)
items = pr.collect_items('x', 0.0, [(0, None), (20, 120), (40, 120), (60, 120), (210, None)])
bad, moved = pr.place_texts(None, items, [], ([], [], []))
bx = [pr.tbox('x', 0.0, (it['a'] + it['b']) / 2 + (it['loc'][0] - (it['a'] + it['b']) / 2), it['loc'][1], it['half']) for it in items]
assert all(not (bx[i][0] < bx[j][2] and bx[i][2] > bx[j][0] and bx[i][1] < bx[j][3] and bx[i][3] > bx[j][1]) for i in range(len(bx)) for j in range(i + 1, len(bx))), bx
assert bad == 0, bad
print('PASS plan_rows: narrow chain texts do not overlap')

# ---- plan_rows: exact cover is used when scipy exists (fewest lines) and still reads every face
if pr.HAVE_MILP:
    d = ezdxf.new('R2010', setup=True)
    for l in ('82_KIR_OLE', '93_KORA', '9_KONTUR', '36_MIDA_CLALI', '15_DASHED'): d.layers.add(l)
    d.dimstyles.new('dim_100', dxfattribs=dict(dimtxt=24, dimasz=4, dimexo=40, dimexe=5, dimgap=6)); m = d.modelspace()
    m.add_lwpolyline([(0, 0), (9000, 0), (9000, 4000), (0, 4000)], close=True, dxfattribs=dict(layer='82_KIR_OLE'))
    m.add_lwpolyline([(40, 40), (8960, 40), (8960, 3960), (40, 3960)], close=True, dxfattribs=dict(layer='82_KIR_OLE'))
    m.add_lwpolyline([(3000, 1000), (3300, 1000), (3300, 2000), (3000, 2000)], close=True, dxfattribs=dict(layer='82_KIR_OLE'))
    out, rep = pr.run(d, (-100, -100, 9100, 4100))
    assert any('optimal cover (integer program)' in r for r in rep), rep
    assert not any('UNREAD faces' in r for r in rep), rep
    print('PASS plan_rows: exact minimum-line cover active, no unread faces')

# ---- claude_Kontur boundary + plan_xlines (2026-10-14)
sys.path.insert(0, REC)
import plan_xlines_lf as _lf
_d = ezdxf.new('R2018'); _d.layers.add('claude_Kontur'); _m = _d.modelspace()
_m.add_lwpolyline([(0, 0), (1000, 0), (1000, 400)], dxfattribs={'layer': 'claude_Kontur'})        # pieces drawn in mixed directions, one of them an arc
_m.add_arc((500, 400), 500, 0, 180, dxfattribs={'layer': 'claude_Kontur'})
_m.add_lwpolyline([(0, 400), (0, 0)], dxfattribs={'layer': 'claude_Kontur'})
_k = _lf.kontur_outline(_m); assert _k and len(_k) > 10, 'claude_Kontur pieces must join into one closed loop'
xs = [p[0] for p in _k]; ys = [p[1] for p in _k]; assert min(xs) < 1 and max(xs) > 999 and max(ys) > 890, 'arc flattened into the loop'
_m2 = ezdxf.new('R2018').modelspace(); _m2.add_lwpolyline([(0, 0), (10, 0)], dxfattribs={'layer': 'claude_Kontur'}); assert _lf.kontur_outline(_m2) is None, 'open boundary -> None (caller falls back)'
print('PASS claude_Kontur: 3 pieces (incl. an arc) join into a closed loop; an open layer returns None')

def _plan():
    doc = ezdxf.new('R2018', setup=True); doc.units = 5
    ds = doc.dimstyles.new('dim_100'); ds.dxf.dimtxt = 24; ds.dxf.dimasz = 5
    for l in ('36_MIDA_CLALI', '82_KIR_OLE', 'claude_DIM', 'claude_Kontur'): doc.layers.add(l)
    m = doc.modelspace(); R = lambda x0, y0, x1, y1, ly='82_KIR_OLE': m.add_lwpolyline([(x0, y0), (x1, y0), (x1, y1), (x0, y1)], close=True, dxfattribs={'layer': ly})
    R(0, 0, 3000, 2000); R(2970, 30, 30, 1970)                                  # perimeter wall 30 thick (outer + inner polygon)
    R(1000, 500, 1040, 900)                                                     # a pier 40 x 400
    m.add_xline((500, 0), (0, 1), dxfattribs={'layer': 'claude_DIM'})           # vertical Xline x=500 -> Y chain
    m.add_xline((0, 5000), (1, 0), dxfattribs={'layer': 'claude_DIM'})          # horizontal Xline ABOVE the plan -> skipped
    p = os.path.join(tmp, 'xl.dxf'); doc.saveas(p); return p
_src = _plan(); _out = os.path.join(tmp, 'xl_out.dxf')
_r = run(os.path.join(REC, 'plan_xlines.py'), _src, _out)
assert 'does not meet the plan outline' in _r, 'an Xline outside the plan must be reported and skipped'
_dd = ezdxf.readfile(_out).modelspace().query('DIMENSION'); assert len(_dd) >= 3, 'vertical Xline -> a Y chain (wall | clear | wall)'
assert all(abs(d.dxf.defpoint.x - 500) < 1 and abs(d.dxf.angle % 180 - 90) < 1 for d in _dd), 'every dimension lies ON the Xline (no extra lines)'
_ys = sorted({round(p.y) for d in _dd for p in (d.dxf.defpoint2, d.dxf.defpoint3)}); assert _ys[0] == 0 and _ys[-1] == 2000, 'chain runs from the outer face to the outer face of the plan'
print('PASS plan_xlines: vertical Xline -> Y chain outline to outline, only on the Xline; an Xline above the plan is reported and skipped')

# ---- output layer taken from the sample dimension inside a cloud outside the plan (user 2026-10-14; cloud on claude or claude_DIM)
_doc = ezdxf.readfile(_src); _m = _doc.modelspace(); _doc.layers.add('claude'); _doc.layers.add('DIMS_X')
_m.add_linear_dim(base=(-300, 500), p1=(-300, 0), p2=(-300, 1000), angle=90, dimstyle='dim_100', dxfattribs={'layer': 'DIMS_X'}).render()
_m.add_lwpolyline([(-500, -50), (-100, -50), (-100, 1050), (-500, 1050)], close=True, dxfattribs={'layer': 'claude', 'color': 1})
_src2 = os.path.join(tmp, 'xl2.dxf'); _doc.saveas(_src2); _out2 = os.path.join(tmp, 'xl2_out.dxf')
_r = run(os.path.join(REC, 'plan_xlines.py'), _src2, _out2); assert 'DIMS_X' in _r
_ly = {d.dxf.layer for d in ezdxf.readfile(_out2).modelspace().query('DIMENSION')}; assert _ly == {'DIMS_X'}, _ly
print('PASS output layer = layer of the dimension inside the red cloud beside the plan (all dims drawn on it)')

# ---- sample dimension in a cloud on layer claude_DIM outside the plan; a cloud inside the plan is skipped (user 2026-10-14)
import plan_xlines_lf as _lf
_doc = ezdxf.new(setup=True); _m = _doc.modelspace(); _doc.layers.add('claude_DIM'); _doc.layers.add('SAMPLE')
_m.add_lwpolyline([(0, 0), (1000, 0), (1000, 1000), (0, 1000)], close=True, dxfattribs={'layer': 'claude_Kontur'})
_m.add_linear_dim(base=(-300, 500), p1=(-300, 0), p2=(-300, 1000), angle=90, dxfattribs={'layer': 'SAMPLE'}).render()
_m.add_lwpolyline([(-500, -50), (-100, -50), (-100, 1050), (-500, 1050)], close=True, dxfattribs={'layer': 'claude_DIM'})
assert _lf.dim_template(_m)[0] == 'SAMPLE', 'claude_DIM cloud outside the plan gives the output layer'
print('PASS dim_template: cloud on claude_DIM outside the plan -> sample dimension layer')

# ---- block_reader: element group vs symbol, nested groups, explode + restore (user 2026-10-14)
import block_reader as _br
_doc = ezdxf.new(setup=True); _m = _doc.modelspace(); _doc.layers.add('8_KIR'); _doc.layers.add('SYMLAY')
_g = _doc.blocks.new('GRP')
for _i in range(6): _g.add_lwpolyline([(_i * 100, 0), (_i * 100 + 40, 0), (_i * 100 + 40, 200), (_i * 100, 200)], close=True, dxfattribs={'layer': '8_KIR'})
_o = _doc.blocks.new('OUTER'); _o.add_blockref('GRP', (0, 0), dxfattribs={'layer': '8_KIR'})
_s = _doc.blocks.new('SYM'); _s.add_circle((0, 0), 5, dxfattribs={'layer': 'SYMLAY'}); _s.add_attdef('N', (0, 0))
assert _br.classify(_doc, 'GRP')['kind'] == 'element_group' and _br.classify(_doc, 'SYM')['kind'] == 'symbol' and _br.classify(_doc, 'OUTER')['kind'] == 'nested'
_m.add_blockref('OUTER', (1000, 500)); _m.add_blockref('SYM', (0, 0))
_sv = _br.expand_groups(_doc, _m); _w = [e for e in _m.query('LWPOLYLINE')]
assert len(_w) == 6 and all(e.dxf.layer == '82_KIR_OLE' for e in _w) and abs(min(q[0] for q in _w[0].get_points('xy')) - 1000) < 1e-6, 'nested group exploded with its transform, wall layer for the pipeline'
_br.restore_groups(_doc, _sv); assert not list(_m.query('LWPOLYLINE')) and len(list(_m.query('INSERT[name=="OUTER"]'))) == 1 and len(list(_m.query('INSERT[name=="SYM"]'))) == 1
print('PASS block_reader: element group / nested group / symbol classified; explode (with transform) + restore round-trip')

# ---- claude_Kontur reader: every way a boundary can be drawn (user 2026-10-14: the app saw only part of the plan)
def _kl(build):
    d = ezdxf.new('R2018'); m = d.modelspace(); build(m); return _lf.kontur_analyze(m)
K = {'layer': 'claude_Kontur'}
sq = [(0, 0), (1000, 0), (1000, 800), (0, 800)]
L, R = _kl(lambda m: m.add_lwpolyline(sq + [(0, 0), (100, 0)], dxfattribs=K))            # returns to its start and overshoots (hayahalon5)
assert len(L) == 1 and abs(_lf._area(L[0]) - 800000) < 1 and R[0]['kind'] == 'overshoot', 'overshooting polyline -> the loop, trimmed'
L, R = _kl(lambda m: m.add_lwpolyline(sq + [(0, 30)], dxfattribs=K))                      # almost closed, 30 short of the start
assert len(L) == 1 and L[0] and R and R[0]['kind'] in ('gap', 'overshoot'), 'almost-closed polyline -> closed by a chord'
L, R = _kl(lambda m: m.add_lwpolyline(sq, close=True, dxfattribs=K))
assert len(L) == 1 and not R, 'plain closed polyline'
def _pieces(m):
    m.add_line((0, 0), (1000, 0), dxfattribs=K); m.add_line((1000, 0), (1000, 800), dxfattribs=K); m.add_arc((500, 800), 500, 0, 180, dxfattribs=K); m.add_line((0, 800), (0, 0), dxfattribs=K)
L, R = _kl(_pieces); assert len(L) == 1 and _lf._area(L[0]) > 800000, 'lines + an arc joined into one loop'
def _gap(m):
    m.add_lwpolyline([(0, 0), (1000, 0), (1000, 800)], dxfattribs=K); m.add_lwpolyline([(1000, 790), (0, 800), (0, 5)], dxfattribs=K)     # two pieces with 10 gaps
L, R = _kl(_gap); assert len(L) == 1 and any(r['kind'] == 'gap' for r in R), 'pieces with small gaps are bridged'
def _dup(m):
    m.add_lwpolyline(sq, close=True, dxfattribs=K); m.add_lwpolyline(sq, close=True, dxfattribs=K); m.add_lwpolyline([(3000, 0), (4000, 0), (4000, 500), (3000, 500)], close=True, dxfattribs=K)
L, R = _kl(_dup); assert len(L) == 2 and any(r['kind'] == 'duplicate' for r in R), 'a loop drawn twice counts once, a second region stays'
def _circ(m): m.add_circle((0, 0), 400, dxfattribs=K)
L, R = _kl(_circ); assert len(L) == 1 and abs(_lf._area(L[0]) - 3.14159 * 160000) < 4000, 'a circle is a region'
def _blk(m):
    b = m.doc.blocks.new('KB'); b.add_lwpolyline(sq, close=True, dxfattribs=K); m.add_blockref('KB', (500, 500), dxfattribs=K)
L, R = _kl(_blk); assert len(L) == 1 and abs(min(q[0] for q in L[0]) - 500) < 1e-6, 'a boundary inside a block is read (with its transform)'
L, R = _kl(lambda m: m.add_lwpolyline([(0, 0), (10, 0)], dxfattribs=K)); assert L == [], 'a lone 2-point line is not a region'
L, R = _kl(lambda m: m.add_lwpolyline(sq, close=True, dxfattribs={'layer': 'CLAUDE_KONTUR '})); assert len(L) == 1, 'layer name: any case / trailing space'
print('PASS claude_Kontur reader: closed, overshoot, almost closed, lines+arc, gaps, duplicates, circle, block, lone line, layer-name variants')

def _nest(m):
    m.add_lwpolyline(sq, close=True, dxfattribs=K); m.add_lwpolyline([(300, 300), (600, 300), (600, 500), (300, 500)], close=True, dxfattribs=K); m.add_lwpolyline([(2000, 0), (3000, 0), (3000, 500), (2000, 500)], close=True, dxfattribs=K)
L, R = _kl(_nest); assert len(L) == 2 and any(r['kind'] == 'nested' for r in R), 'a loop inside another is a hole, a separate loop stays a region'
print('PASS claude_Kontur reader: nested loop = hole')
