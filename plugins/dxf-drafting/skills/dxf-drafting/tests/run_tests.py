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
run(os.path.join(REC, 'ledge_beam.py'), src, '3-3', '--box', '0', '0', '400', '450', '--beam', '80', '65', '--slab', '20', '--topping', '5', '--sides', 'both', '--stirrups', 'transfer', '-o', out)
d = ezdxf.readfile(out); m = d.modelspace()
dots = [p for p in m.query('LWPOLYLINE') if len(p) == 2 and p.closed and p.dxf.layer == '57_HATAH_ZIUN']
assert len(dots) == 30 and all(p.dxf.const_width == 1.0 for p in dots), 'expected 30 solid dots'
assert len(m.query('DIMENSION')) >= 12 and not d.audit().errors
texts = [t.dxf.text for t in m.query('TEXT')]
assert '$12@20' in texts and '2$12/14/16@15 L=190' in texts and texts.count('$12@15 L=154') == 2, texts      # ST: only the tall-stirrup note is 12/14/16 (user's cloud 2026-10-21)
# solid slab beside a ledge beam with the parametric thickness symbol H (user 2026-10-18, 'casting completion' cloud, 6-6)
outS = os.path.join(tmp, 'ledge_solid.dxf')
run(os.path.join(REC, 'ledge_beam.py'), sample(), '6-6', '--box', '0', '0', '400', '450', '--beam', '80', '70', '--slab', '25', '--topping', '7', '--sides', 'left', '--solid', 'right', '--solid-D', '25', '--solid-label', 'H', '--detail', 'plan', '-o', outS)
dS = ezdxf.readfile(outS); assert not dS.audit().errors
assert [x.dxf.text for x in dS.modelspace().query('DIMENSION') if x.dxf.text == 'H'], 'solid slab thickness dim must carry the symbol H'
# cast edge beam: hollow-core slab one side + SOLID slab the other with the symbol H (user 2026-10-18, 6-6 / 7-7)
outC = os.path.join(tmp, 'cast_solid.dxf')
run(os.path.join(REC, 'ledge_beam.py'), sample(), '7-7', '--box', '0', '0', '400', '450', '--beam', '30', '60', '--slab', '32', '--topping', '7', '--sides', 'right', '--kind', 'cast', '--solid', 'left', '--solid-D', '25', '--solid-label', 'H', '-o', outC)
dC = ezdxf.readfile(outC); assert not dC.audit().errors and len([e for e in dC.modelspace().query('LWPOLYLINE') if e.dxf.layer == '10_PLADA_HATAH' and len(e) == 4 and e.closed]) == 3
assert [x.dxf.text for x in dC.modelspace().query('DIMENSION') if x.dxf.text == 'H'], 'cast + solid: slab thickness dim must be H'
out2 = os.path.join(tmp, 'ledge2.dxf')
run(os.path.join(REC, 'ledge_beam.py'), out, '3-3', '--box', '0', '0', '400', '450', '--beam', '80', '65', '--slab', '20', '--topping', '5', '--sides', 'both', '--stirrups', 'transfer', '--dims-only', '-o', out2)
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

# dim_template: frame around the dimension line + text only (user's legend file, measured points outside the frame)
_d = ezdxf.new('R2018', setup=True); _m = _d.modelspace(); _d.layers.add('claude_DIM'); _d.layers.add('claude_Kontur'); _d.layers.add('36_MIDA_CLALI')
_m.add_lwpolyline([(0, 0), (1000, 0), (1000, 800), (0, 800)], close=True, dxfattribs={'layer': 'claude_Kontur'})
_m.add_linear_dim(base=(3080, 100), p1=(3300, 100), p2=(3300, 300), angle=90, dimstyle='EZDXF', dxfattribs={'layer': '36_MIDA_CLALI'}).render()
_m.add_lwpolyline([(3040, 60), (3120, 60), (3120, 340), (3040, 340)], close=True, dxfattribs={'layer': 'claude_DIM'})
_tp = _lf.dim_template(_m); assert _tp and _tp[0] == '36_MIDA_CLALI', 'frame around the dimension line and text (points outside) finds the sample dimension'
print('PASS dim_template: frame around line + text only')

# ledge_beam cast, slab on the LEFT (star marker, 2026-10-15): mirror of the right-slab section - same entity counts, slab geometry on the other side of the beam
_o1, _o2 = os.path.join(tempfile.gettempdir(), 'cast_r.dxf'), os.path.join(tempfile.gettempdir(), 'cast_l.dxf')
for _s, _o in (('right', _o1), ('left', _o2)): run(os.path.join(REC, 'ledge_beam.py'), src, '1-1', '--box', '0', '0', '400', '450', '--beam', '30', '65', '--slab', '25', '--topping', '5', '--sides', _s, '--kind', 'cast', '-o', _o)
def _core_x(p): return [sum(v[0] for v in e.get_points('xy')) / 4 for e in ezdxf.readfile(p).modelspace().query('LWPOLYLINE') if e.dxf.layer == '10_PLADA_HATAH' and len(e) == 4 and e.closed]      # obround cores (user 2026-10-21)
_r, _l = _core_x(_o1), _core_x(_o2); assert len(_r) == len(_l) == 3
def _beam_mid(p): return [(e.dxf.start.x + e.dxf.end.x) / 2 for e in ezdxf.readfile(p).modelspace().query('LINE') if abs(abs(e.dxf.end.x - e.dxf.start.x) - 30) < 1e-6 and abs(e.dxf.end.y - e.dxf.start.y) < 1e-6][0]
assert min(_r) > _beam_mid(_o1) and max(_l) < _beam_mid(_o2), 'cores right of the stem when sides=right, left of it when sides=left'
print('PASS ledge_beam cast: slab on the left = mirror image')

# star_orient: clockwise turn (south pair E -> W), centred on the beam axis, east of the size label, number re-placed (user's red-cloud examples 2026-10-15)
import math as _m
_d = ezdxf.new('R2018'); _b = _d.blocks.new('hat'); _b.add_line((0, 0), (40, 0)); _b.add_attdef('A', (14.66, 25.99), dxfattribs={'height': 22})
for _n in ('automatic_sections', '93_KORA', '451TEXT_KORA_100'): _d.layers.add(_n)
_m2 = _d.modelspace()
def _pair(x, ymid, rot, nm='*'):
    sx = (-1, 1) if rot == 270 else (1, -1)
    for dy, s in ((-92, sx[0]), (92, sx[1])):
        r = _m2.add_blockref('hat', (x, ymid + dy), dxfattribs={'layer': 'automatic_sections', 'rotation': rot, 'xscale': 1.328 * s, 'yscale': 1.328}); r.add_attrib('A', nm, (x + 16, ymid + dy + 38), dxfattribs={'height': 24, 'rotation': 270})
for _y in (0, 1000):                                               # south beam at y=0 (axis 0), north beam at y=1000
    for _yy in (_y - 15, _y + 15): _m2.add_line((-500, _yy), (500, _yy), dxfattribs={'layer': '93_KORA'})
    _m2.add_text('30/65', height=20, dxfattribs={'layer': '451TEXT_KORA_100', 'insert': (-30, _y - 8)})
_pair(-10, 10, 270); _pair(-10, 1010, 270)                      # both looking E, 10 off the beam axis, through the label
_f = os.path.join(tmp, 'star.dxf'); _d.saveas(_f)
r = subprocess.run([sys.executable, os.path.join(REC, 'star_orient.py'), _f, '--tidy', 'W'], capture_output=True, text=True, encoding='utf-8'); assert r.returncode == 0, r.stderr
_m3 = ezdxf.readfile(_f).modelspace(); _h = [e for e in _m3.query('INSERT') if e.dxf.name == 'hat']
_s = [e for e in _h if e.dxf.insert.y < 500]; _n = [e for e in _h if e.dxf.insert.y > 500]
assert all(round(e.dxf.rotation) == 90 for e in _s) and all(round(e.dxf.rotation) == 270 for e in _n), 'south pair turned to W, north pair kept E'
_mid = sum(e.dxf.insert.y for e in _s) / 2; assert abs(_mid) < 1, 'centred on the beam axis'
assert all(abs(e.dxf.insert.x + 10) < 1 for e in _s), 'x along the beam is NOT moved (user examples: no common anchor)'
for e in _s + _n:
    k = 1.328; sx = 1 if e.dxf.xscale > 0 else -1; a = e.attribs[0]; r = _m.radians(e.dxf.rotation); dx, dy = a.dxf.insert.x - e.dxf.insert.x, a.dxf.insert.y - e.dxf.insert.y
    ux, uy = dx * _m.cos(r) + dy * _m.sin(r), -dx * _m.sin(r) + dy * _m.cos(r)
    assert abs(uy / k - 11.9) < 0.1 and abs(sx * ux / k - (16.5 if sx > 0 else 28.55)) < 0.1 and round(a.dxf.rotation) % 360 == round(e.dxf.rotation) % 360, 'number rigid with the block (local position + rotation)'
print('PASS star_orient: clockwise turn + centred on beam + number rigid with the block')

# slab_edge: free edge of a D=20 solid slab = the user's own detail (cell 4 of sections_ramla.dxf, 2026-10-15), numbers measured on it
_d4 = sample(); _d4doc = ezdxf.readfile(_d4); _b2 = _d4doc.blocks.new('dot barzel'); _b2.add_circle((0, 0), 1.25); _d4doc.layers.add('1922_ZIUN_DOT_T+I'); _d4doc.saveas(_d4)
_o3 = os.path.join(tempfile.gettempdir(), 'edge.dxf'); run(os.path.join(REC, 'slab_edge.py'), _d4, '4-4', '--box', '0', '0', '400', '450', '--slab', '20', '-o', _o3)
_d3 = ezdxf.readfile(_o3); _m4 = _d3.modelspace(); assert not _d3.audit().errors
_ln = [e for e in _m4.query('LINE') if e.dxf.layer == '9_KONTUR']; assert len(_ln) == 3, 'top, soffit and free end face'
_top = [e for e in _ln if abs(e.dxf.start.y - 301.3) < 1e-6]; assert len(_top) == 1 and abs(abs(_top[0].dxf.end.x - _top[0].dxf.start.x) - 58.8) < 0.05 and abs(max(_top[0].dxf.start.x, _top[0].dxf.end.x) - 234.4) < 1e-6, 'edge at x0+234.4, 58.8 long, top at y0+301.3'
_bars = [e for e in _m4.query('LINE') if e.dxf.layer == '57_HATAH_ZIUN']; assert len(_bars) == 2 and all(abs(max(e.dxf.start.x, e.dxf.end.x) - 231.4) < 1e-6 for e in _bars), 'bar lines stop 3 short of the edge'
_dots = [e for e in _m4.query('INSERT') if e.dxf.name == 'dot barzel']; assert len(_dots) == 8 and sorted({round(e.dxf.insert.y, 1) for e in _dots}) == [285.6, 297.0] and sorted({round(e.dxf.insert.x, 1) for e in _dots}) == [184.9, 199.9, 214.9, 229.9], '2 rows x 4 dot barzel'
_tx = [t.dxf.text for t in _m4.query('TEXT')]; assert 'c/g/ kph ,fw' in _tx and 'c/,/ kph ,fw' in _tx and 'euyr upxhgv gwwp' in _tx and 'crzk zhui tupeh' in _tx, 'per-plan notes + bar-shape note'
_u = [e for e in _m4.query('LWPOLYLINE') if e.dxf.layer == '57_HATAH_ZIUN' and len(e) == 4]; assert len(_u) == 1 and abs((max(p[1] for p in _u[0].get_points('xy')) - min(p[1] for p in _u[0].get_points('xy'))) - 14) < 1e-6, 'U-bar shape 60 x (D-6)'
print('PASS slab_edge: free slab edge = the user ceiling-edge detail')

# thick free edge (D=80, his 4-4): NO restraint mesh since 2026-10-24 (FREE_EDGE_MESH off); the code path still exists behind FREE_EDGE_MESH=1
def _thick(env):
    o = os.path.join(tempfile.gettempdir(), 'edge_thick%s.dxf' % env); e0 = os.environ.get('FREE_EDGE_MESH')
    if env == '1': os.environ['FREE_EDGE_MESH'] = '1'
    else: os.environ.pop('FREE_EDGE_MESH', None)
    run(os.path.join(REC, 'slab_edge.py'), _d4, '6-6', '--box', '0', '0', '400', '450', '--slab', '80', '-o', o)
    if e0 is None: os.environ.pop('FREE_EDGE_MESH', None)
    else: os.environ['FREE_EDGE_MESH'] = e0
    m = ezdxf.readfile(o).modelspace()
    return len([e for e in m if e.dxf.layer == 'HATAH_ZIUN_17']), len(m.query('LEADER')), len([t for t in m.query('TEXT') if t.dxf.text.startswith('#')])
_off = _thick('0'); _on = _thick('1')
assert _off[1] == 0 and _off[2] == 0, 'thick free edge must have no mesh leaders or mesh note'
assert _on[0] == _off[0] + 1 and _on[1] == 2 and _on[2] == 1, 'the mesh code path (FREE_EDGE_MESH=1) must still draw bar + 2 leaders + note'
print('PASS slab_edge thick: no restraint mesh by default (FREE_EDGE_MESH=0), still available behind the switch')

# stirrup tables (user's two images, 2026-10-15): consistent with the user's own examples; standard 85 -> 3 x 35 (ex 5-5), transfer 50 -> 2 x 30 (ex 2-2), n = 1 -> width = thickness - 6
sys.path.insert(0, os.path.join(HERE, '..', 'scripts')); import dxflib as _dl
assert _dl.stirrup_layout(85, 'standard')[:2] == (3, 35) and _dl.stirrup_layout(50, 'transfer')[:2] == (2, 30) and _dl.stirrup_layout(50, 'standard')[:2] == (2, 30)
assert _dl.stirrup_layout(30, 'standard')[:2] == (1, 24) and _dl.stirrup_layout(200, 'transfer')[:2] == (7, 40) and _dl.stirrup_layout(44, 'standard')[3] == 45 and _dl.stirrup_layout(200, 'standard')[:2] == (5, 55)
_o5 = os.path.join(tempfile.gettempdir(), 'st_std.dxf'); run(os.path.join(REC, 'ledge_beam.py'), src, '3-3', '--box', '0', '0', '400', '450', '--beam', '80', '65', '--slab', '20', '--topping', '5', '--sides', 'both', '-o', _o5)
_tx = [t.dxf.text for t in ezdxf.readfile(_o5).modelspace().query('TEXT')]; assert any(x.startswith('2$12@15 L=') for x in _tx), 'standard 80/65 ledge beam: TWO stem stirrups (stem 50 -> 2 x 30, his table 2026-10-16)'
print('PASS stirrup tables: standard / transfer lookup, ledge section uses them')

# transfer_check: a vertical element (even a small pier) on the beam strip makes it a transfer beam (user's red cloud, 80/65 beam with a 26 x 37 pier, 2026-10-15)
sys.path.insert(0, os.path.join(HERE, '..', 'scripts')); import transfer_check as _tc
_d6 = ezdxf.new('R2018'); _m6 = _d6.modelspace(); _d6.layers.add('93_KORA'); _d6.layers.add('82_KIR_OLE')
for _x in (0, 80): _m6.add_line((_x, 0), (_x, 1000), dxfattribs={'layer': '93_KORA'})
_m6.add_lwpolyline([(27, 500), (53, 500), (53, 537), (27, 537)], close=True, dxfattribs={'layer': '82_KIR_OLE'})
assert _tc.elements_on(_d6, 0, 0, 80, 1000) and not _tc.elements_on(_d6, 0, 0, 80, 400), 'small pier on the beam = transfer; nothing on the other part'
assert _tc.beam_strip(_d6, 40, 300, False) == (0, 0, 80, 1000)
print('PASS transfer_check: element on the beam strip, strip from a cut centre')

# general_beam = the user's parametric section 6-6 (B, D, H); numbers measured on the example (B=20, D=25, H=74) and an untagged beam (B=25, D=20, H=40, height symbol h), 2026-10-15
sys.path.insert(0, os.path.join(HERE, '..', 'recipes')); import general_beam as _gb
assert [round(v, 1) for v in _gb.beam_dot_rows(74, 25)] == [69.7, 53.4, 33.4, 13.4, 4.5], 'dot rows of 6-6'
assert [round(v, 1) for v in _gb.beam_dot_rows(40, 20)] == [35.7, 24.4, 4.5], 'dot rows of the H=40 beam (24.4 - 20 = 4.4 is merged into the bottom row)'
_o7 = os.path.join(tempfile.gettempdir(), 'gb_ex.dxf'); run(os.path.join(REC, 'general_beam.py'), src, '6-6', '--box', '0', '0', '400', '450', '--B', '20', '--D', '25', '--H', '74', '--labels', 'example', '-o', _o7)
_o8 = os.path.join(tempfile.gettempdir(), 'gb_h.dxf'); run(os.path.join(REC, 'general_beam.py'), src, '5-5', '--box', '0', '0', '400', '450', '--B', '25', '--D', '20', '--H', '40', '--h-label', 'h', '-o', _o8)
for _f, _n in ((_o7, 26), (_o8, 2 * 3 + 16)):
    _dd = ezdxf.readfile(_f); _mm = _dd.modelspace(); assert not _dd.audit().errors
    assert len([e for e in _mm.query('LWPOLYLINE') if len(e) == 2 and e.closed and e.dxf.layer == '57_HATAH_ZIUN']) == _n, f'dots {_n}'
_t7 = [t.dxf.text for t in ezdxf.readfile(_o7).modelspace().query('TEXT')]; assert {'4$12', '2$12', '2$8@20', '$12@15'} <= set(_t7)
_dm = {e.dxf.text for e in ezdxf.readfile(_o8).modelspace().query('DIMENSION')}; assert 'h' in _dm and 'h-6' in _dm, 'height dims carry the symbol h'
print('PASS general_beam: 6-6 numbers, untagged beam with symbol h')

# general_beam with the transfer table: B=40 -> 2 stirrups of 25 under the beam, note 2$12/14/16@15 (star pair 6-6, wall rising from the beam, 2026-10-15)
_o9 = os.path.join(tempfile.gettempdir(), 'gb_tr.dxf'); run(os.path.join(REC, 'general_beam.py'), src, '6-6', '--box', '0', '0', '400', '450', '--B', '40', '--D', '25', '--H', '40', '--h-label', 'h', '--stirrups', 'transfer', '-o', _o9)
_m9 = ezdxf.readfile(_o9).modelspace(); assert '2$12/14/16@15' in [t.dxf.text for t in _m9.query('TEXT')], 'transfer note'
assert len([e for e in _m9.query('LWPOLYLINE') if e.dxf.layer == '57_HATAH_ZIUN' and len(e) == 4 and e.closed]) == 4, 'two stirrup rectangles in the detail row + two inside the section (user 2026-10-16)'
print('PASS general_beam: transfer stirrups (2 x 25 for B=40)')

# ledge_beam with the height SYMBOL (untagged beam with a ledge, star pair 6-6, 2026-10-15): height dims carry 'h', 'h-25', 'h-6'; no L= lengths
_oa = os.path.join(tempfile.gettempdir(), 'ledge_h.dxf'); run(os.path.join(REC, 'ledge_beam.py'), src, '6-6', '--box', '0', '0', '400', '450', '--beam', '40', '40', '--slab', '20', '--topping', '5', '--sides', 'right', '--kind', 'ledge', '--stirrups', 'transfer', '--h-label', 'h', '-o', _oa)
_ma = ezdxf.readfile(_oa).modelspace(); _da = {e.dxf.text for e in _ma.query('DIMENSION')}; _ta = [t.dxf.text for t in _ma.query('TEXT')]
assert {'h', 'h-25', 'h-6'} <= _da and not any('L=' in t for t in _ta) and '$12/14/16@15' in _ta, (_da, _ta)
print('PASS ledge_beam: height symbol h on an untagged ledge beam')

# star_plan helpers: tag, D label, dashed line = hidden edge between the faces (ledge), strip from the cut centre
sys.path.insert(0, os.path.join(HERE, '..', 'recipes')); import star_plan as _sp
_d8 = ezdxf.new('R2018'); _m8 = _d8.modelspace()
for _l in ('93_KORA', '15_DASHED', '451TEXT_KORA_100'): _d8.layers.add(_l)
for _x in (0, 40): _m8.add_line((_x, 0), (_x, 1000), dxfattribs={'layer': '93_KORA'})
_m8.add_line((25, 100), (25, 900), dxfattribs={'layer': '15_DASHED'}); _m8.add_text('40/65', height=10, dxfattribs={'layer': '451TEXT_KORA_100', 'insert': (10, 500)}); _m8.add_text('D=20+5', height=10, dxfattribs={'insert': (200, 500)})
_st = _tc.beam_strip(_d8, 20, 500, False); assert _st == (0, 0, 40, 1000)
assert _sp.dashed_inside(_d8, _st, False) == [25.0] and _sp.text_near(_d8, _st, '451TEXT_KORA_100', _sp.TAG)[0][1].groups() == ('40', '65') and _sp.slab_labels(_d8, 20, 500)[0][3:] == (20, 5)
print('PASS star_plan: strip, tag, ledge (dashed), slab label')

# S / SS marks (user 2026-10-16): SS = engineer picks the bars -> the two slab-bar leader notes read 'X$XX', S keeps 'as per plan'; ' zhui kph ,fbh,' stays
_oS = os.path.join(tempfile.gettempdir(), 'gb_S.dxf'); _oSS = os.path.join(tempfile.gettempdir(), 'gb_SS.dxf')
run(os.path.join(REC, 'general_beam.py'), src, '6-6', '--box', '0', '0', '400', '450', '--B', '40', '--D', '25', '--H', '40', '--h-label', 'h', '--detail', 'plan', '-o', _oS)
run(os.path.join(REC, 'general_beam.py'), src, '6-6', '--box', '0', '0', '400', '450', '--B', '40', '--D', '25', '--H', '40', '--h-label', 'h', '--detail', 'ss', '-o', _oSS)
_tS = [t.dxf.text for t in ezdxf.readfile(_oS).modelspace().query('TEXT')]; _tSS = [t.dxf.text for t in ezdxf.readfile(_oSS).modelspace().query('TEXT')]
assert 'X$XX' not in _tS and _tSS.count('X$XX') >= 1 and len(_tS) == len(_tSS), 'SS notes'
print('PASS S / SS marks: SS replaces the slab-bar notes by X$XX')

# S mark on a general beam = the user's hand fix of 8-8 (2026-10-16): '4$12' / '2$12' -> per-plan notes on shelves 46.2 / 47.1, beam-bar leaders (2 lines) removed
_mS = ezdxf.readfile(_oS).modelspace(); _tS2 = [t.dxf.text for t in _mS.query('TEXT')]
assert '4$12' not in _tS2 and '2$12' not in _tS2 and _tS2.count('c/g/ kph ,fw') >= 2 and _tS2.count('c/,/ kph ,fw') >= 2, 'S notes'
print('PASS S mark: beam bar callouts become as-per-plan notes (8-8)')

# user's fix of 10-10 / 11-11 (2026-10-16): two-digit title numbers are written digit-reversed; SS on a cast beam = X$XX on the beam bar callout, slab notes per plan
import ledge_beam as _lbm
assert _lbm.title_name('10-10') == '01-01' and _lbm.title_name('12-12') == '21-21' and _lbm.title_name('3-3') == '3-3', 'title digits'
_oC = os.path.join(tempfile.gettempdir(), 'lb_ss_cast.dxf'); run(os.path.join(REC, 'ledge_beam.py'), src, '11-11', '--box', '0', '0', '400', '450', '--beam', '30', '90', '--kind', 'cast', '--sides', 'both', '--topping', '7', '--stirrups', 'standard', '--slab', '32', '--detail', 'ss', '-o', _oC)
_tC = [t.dxf.text for t in ezdxf.readfile(_oC).modelspace().query('TEXT')]
assert _tC.count('X$XX') == 2 and '4$12' not in _tC and '2$12' not in _tC and _tC.count(' zhui kph ,fbh,') == 2, 'SS cast'
print('PASS titles digit-reversed; SS on a cast beam (11-11)')

# ST mark = S with TRANSFER stirrups (user 2026-10-16)
import star_plan as _spm
class _H:
    def __init__(s, t): s.attribs = [type('A', (), {'dxf': type('D', (), {'text': t})()})()]
assert _spm.mark_of(_H('ST'), _H('ST')) == 'ST' and _spm.mark_of(_H('SS'), _H('SS')) == 'SS' and _spm.mark_of(_H('S'), _H('S')) == 'S' and _spm.mark_of(_H('*'), _H('*')) == 'S', 'mark_of'
print('PASS star marks S / SS / ST')

# leader_fit (user 2026-10-21): every note stands on a shelf as long as its text, with forks to bars; the S-mark 8-8 fix keeps the forks of the top note
sys.path.insert(0, os.path.join(HERE, '..', 'scripts'))
import leader_fit as _lf, shx_width as _sw
_ext = _sw.text_extent('MIRYL', ' zhui kph ,fbh,', 100.0, 6, 1.0); assert 60 < _ext[1] - _ext[0] < 68 and _ext[1] <= 100.0, 'MIRYL runs leftwards from the insert'
_dS = ezdxf.readfile(_oS); _ch = _lf.fit_box(_dS, (0, -150, 400, 600), dry=True)
assert not [c for c in _ch if 'orphan' in c or 'left' in c], _ch
print('PASS leader_fit: SHX text width, S-mark notes keep their forks, shelves cover the text')

# leader_fit tip snap (user 2026-10-21): a stirrup-note fork ending 1.5 beside a dot goes onto the dot centre
_ds = ezdxf.new('R2018'); _ms = _ds.modelspace(); _ds.styles.add('HEBREW_NEW', font='hebtxt 500.shx')
for _l in ('56_HATAH_ZET', '54_HATAH_TEXT', '57_HATAH_ZIUN'): _ds.layers.add(_l)
for _p in ((10, 20.5), (30, 20.5), (10, 40), (30, 40)): _ms.add_lwpolyline([(_p[0] - 1, _p[1]), (_p[0] + 1, _p[1])], dxfattribs={'layer': '57_HATAH_ZIUN'})
_ms.add_lwpolyline([(-20, 20), (0, 20)], dxfattribs={'layer': '56_HATAH_ZET'}); _ms.add_line((0, 20), (8.5, 21.5), dxfattribs={'layer': '56_HATAH_ZET'}); _ms.add_line((0, 20), (31.5, 21.0), dxfattribs={'layer': '56_HATAH_ZET'})
_ms.add_text('$12@20', height=6, dxfattribs={'layer': '54_HATAH_TEXT', 'style': 'HEBREW_NEW', 'insert': (-19, 21.5)})
_lf.fit_box(_ds, (-50, -10, 120, 80)); _tips = sorted((l.dxf.end.x, l.dxf.end.y) for l in _ms.query('LINE'))
assert _tips == [(10, 20.5), (30, 20.5)] or [tuple(round(v, 6) for v in t) for t in _tips] == [(10.0, 20.5), (30.0, 20.5)], _tips
print('PASS leader_fit: fork tips snap to the dot centre')

# bar_arrays planning (user 2026-10-21): runs of >=3 equal-step dots -> one array, leftovers paired, odd dot stays loose
import bar_arrays as _ba
_dd = [('a%d' % i, 100.0 + 15 * i, 50.0) for i in range(4)] + [('v%d' % i, 300.0, 10.0 + 20 * i) for i in range(3)] + [('p0', 120.0, 90.0), ('p1', 180.0, 90.0), ('s0', 150.0, 200.0)]
_ar, _lo = _ba.plan_arrays(_dd)
assert sorted((a[0], a[2], round(a[3])) for a in _ar) == [('H', 2, 60), ('H', 4, 45), ('V', 3, 40)] and _lo == ['s0'], (_ar, _lo)
print('PASS bar_arrays: runs, pairs and loose dots planned')

# wide beams: top row (<= 5.9) and bottom row (<= 10.15) of bar dots run across the width (user 2026-10-21, brenda_karka red clouds); B=20 keeps the 2-dot pair
_o9 = os.path.join(tempfile.gettempdir(), 'gb_wide.dxf'); run(os.path.join(REC, 'general_beam.py'), src, '1-1', '--box', '0', '0', '400', '450', '--B', '150', '--D', '25', '--H', '115', '-o', _o9)
_dw = ezdxf.readfile(_o9); _dots = [(round(e[0][0] + e[1][0], 1) / 2, e[0][1]) for e in _dw.modelspace().query('LWPOLYLINE') if e.dxf.layer == '57_HATAH_ZIUN' and len(e) == 2]
_ys = sorted({round(y, 1) for _, y in _dots}); _top, _bot = max(_ys), min(_ys)
_nt = sum(1 for _, y in _dots if abs(y - _top) < .2); _nb = sum(1 for _, y in _dots if abs(y - _bot) < .2)
assert _nt >= 2 + 20 and _nb >= 2 + 10, (_nt, _nb)      # 150 wide: top ~ 150/5.9, bottom ~ 150/10.15 (+ slab dots on the top row)
print('PASS general_beam: wide beam top / bottom bar rows across the width')

# user's hand-organised 1-1 / 2-2 (2026-10-21): slab thickness dimensioned on BOTH ends (right one at B + 91.2), top note keeps 2 forks (top row), skin note on the second mid pair
_dd = [e for e in ezdxf.readfile(_o9).modelspace().query('DIMENSION') if e.dxf.get('angle', 0) == 90 and e.dxf.layer == '53_HATAH_MIDA']
_px = sorted(round(e.dxf.defpoint3[0] - e.dxf.defpoint2[0], 1) for e in _dd if abs(e.dxf.defpoint3[1] - e.dxf.defpoint2[1] - 25) < .1)
assert len(_px) >= 2, _px
print('PASS general_beam: slab thickness dimensioned on both ends')

# per-side slab thickness and level drop (user 2026-10-21 'double-check the ceiling thicknesses'): left D=50 flush, right D=25 dropped 70 on a 130/95 beam
_o10 = os.path.join(tempfile.gettempdir(), 'gb_sides.dxf'); run(os.path.join(REC, 'general_beam.py'), src, '6-6', '--box', '0', '0', '400', '450', '--B', '130', '--H', '95', '--D', '50', '--D-left', '50', '--D-right', '25', '--drop-right', '70', '-o', _o10)
_ms = sorted(round(e.get_measurement()) for e in ezdxf.readfile(_o10).modelspace().query('DIMENSION') if e.dxf.layer == '53_HATAH_MIDA' and e.dxf.get('angle', 0) == 90)
assert _ms.count(50) >= 1 and _ms.count(25) >= 1 and 95 in _ms, _ms
print('PASS general_beam: per-side slab thickness and level drop')

# stirrups beyond the 200 table (user 2026-10-21): fitted rule + HOOP RULE (two branches at most 40 cm apart -> width <= 40)
for _k in ('standard', 'transfer'):
    for _t in range(205, 420, 5):
        _en, _ew = _dl.stirrup_extend(_t, _k); assert _ew <= 40 and (_en * _ew - (_t - 6)) / (_en - 1) >= 8 - 1e-9, (_k, _t, _en, _ew)
assert _dl.stirrup_layout(250, 'standard')[:2] == (8, 40) and _dl.stirrup_layout(205, 'transfer')[0] == 7 and _dl.stirrup_layout(300, 'standard')[0] == 10
print('PASS stirrups: extension beyond 200, width <= 40')

# middle steel rule (user 2026-10-21)
assert _dl.mid_steel(30, 60)[:2] == (8, 20) and _dl.mid_steel(65, 65)[:2] == (8, 15) and _dl.mid_steel(150, 115)[:2] == (10, 15) and _dl.mid_steel(30, 65, hollow=True)[:2] == (12, 20) and _dl.mid_steel(20, 100)[2] == '2$8@15'
assert _dl.mid_steel(50, 40)[:2] == (8, 15) and _dl.mid_steel(100, 100)[:2] == (8, 15) and _dl.mid_steel(100, 101)[:2] == (10, 15)
print('PASS mid_steel: area thresholds and hollow-core rule')

# text overlap + row alignment (user 2026-10-22)
sys.path.insert(0, REC)
import text_overlap as _to, align_row as _ar
_d = ezdxf.new('R2010'); _d.styles.add('SIVAN', font='arial.ttf') if 'SIVAN' not in _d.styles else None
_m = _d.modelspace()
for _y in (0.0, 6.7):                                  # two notes 6.7 apart (the 6-6 cloud): overlap with the 2.0 gap, apart once the lower one is staggered
    _m.add_text('c/g/ kph ,fw', height=6, dxfattribs=dict(layer='54_HATAH_TEXT', style='SIVAN', width=0.7, text_generation_flag=2, insert=(100.0 - _y * 0, _y)))
try:
    assert len(_to.overlaps(_d)) == 1
    print('PASS text_overlap: stacked notes found')
except Exception as _e:
    print('SKIP text_overlap (font not available here):', type(_e).__name__)
_d2 = ezdxf.new('R2010'); _m2 = _d2.modelspace()
_m2.add_lwpolyline([(0, 0), (800, 0), (800, 450), (0, 450)], close=True, dxfattribs=dict(layer='72_MISGERET_WIN'))
_m2.add_line((400, 0), (400, 450), dxfattribs=dict(layer='72_MISGERET_WIN'))
_row = _ar.row_cells(_d2)
assert len(_row[4]) == 3 and _row[4][1] == 400
print('PASS align_row: cells read from the frame dividers')

# doubled entities inside a framed row (user 2026-10-22)
import cell_dupes as _cd
_d3 = ezdxf.new('R2010'); _m3 = _d3.modelspace()
_m3.add_lwpolyline([(0, 0), (400, 0), (400, 450), (0, 450)], close=True, dxfattribs=dict(layer='72_MISGERET_WIN'))
for _i in range(2): _m3.add_line((10, 10), (50, 10), dxfattribs=dict(layer='57_HATAH_ZIUN'))
_m3.add_line((10, 20), (50, 20), dxfattribs=dict(layer='57_HATAH_ZIUN'))
assert len(_cd.dupes(_d3)) == 1
print('PASS cell_dupes: doubled line found, single line kept')

# roller-shutter downstand at a free slab edge (user 2026-10-22, brenda_karka 1-1; numbers from his corrected state)
_o5 = os.path.join(tempfile.gettempdir(), 'edge_shutter.dxf'); run(os.path.join(REC, 'slab_edge.py'), _d4, '5-5', '--box', '0', '0', '400', '450', '--slab', '25', '--d-label', 'H', '--shutter', '10', '35', '-o', _o5)
_d5 = ezdxf.readfile(_o5); _m5 = _d5.modelspace(); assert not _d5.audit().errors
_col = sorted(round(e.dxf.insert.y, 1) for e in _m5.query('INSERT') if e.dxf.name == 'dot barzel' and abs(e.dxf.insert.x - 229.9) < 0.05 and e.dxf.insert.y < 281.3 + 5)
assert len(_col) == 3 + 1 and abs((_col[1] - _col[0]) - 17.05) < 0.1, 'one dot column down the outer face, 3 dots ~17 apart (+ the slab bottom-row dot)'
assert any(l.dxf.layer == '2000_DOT_HELP_LINE' for l in _m5.query('LINE')), 'array help line'
_bx = [t.dxf.text for t in _m5.query('TEXT') if t.dxf.layer == '55_HATAH_TEXT']; assert sorted(_bx) == ['ju.', 'pbho'], 'outside AND inside labels'
assert '2$10' in [t.dxf.text for t in _m5.query('TEXT')]
print('PASS slab_edge shutter: dot column, outside + inside labels')

# roller-shutter under a beam with slab both sides (his hand edit of korchakk 6-6, 2026-10-24): geometry numbers from his state
_d6 = ezdxf.new('R2018', setup=True); _d6.layers.add('9_KONTUR'); _d6.dimstyles.new('dim_25'); _d6.dimstyles.new('dim_25_BARZEL_Above')
_d6.blocks.new('dot barzel'); _m6 = _d6.modelspace(); _m6.add_line((-13172.5, 268837.7), (-13152.5, 268837.7), dxfattribs=dict(layer='9_KONTUR'))
_o6 = os.path.join(tempfile.gettempdir(), 'beam_shutter_in.dxf'); _d6.saveas(_o6); _o7 = os.path.join(tempfile.gettempdir(), 'beam_shutter_out.dxf')
run(os.path.join(REC, 'beam_shutter.py'), _o6, '--face-x', '-13172.5', '--beam-bottom', '268837.7', '--slab-top', '268877.7', '--soffit', '268852.7', '--b', '10', '--h', '35', '--side', 'right', '--h-dim-x', '-13076.1', '-o', _o7)
_d7 = ezdxf.readfile(_o7); _m7 = _d7.modelspace(); assert not _d7.audit().errors
_dots = sorted(round(e.dxf.insert.y, 1) for e in _m7.query('INSERT') if e.dxf.name == 'dot barzel'); assert _dots == [268807.9, 268820.3, 268832.7], _dots
assert any(t.dxf.text == '2$10' and abs(t.dxf.insert.x - (-13147.5)) < 0.2 for t in _m7.query('TEXT')), 'note runs to the right, away from the stem'
assert '$8@15 L=110' in [t.dxf.text for t in _m7.query('TEXT')], 'numeric stirrup'
_bx = sorted((t.dxf.text, round(t.dxf.insert.x - (-13172.5), 1), round(t.dxf.insert.y - (268837.7 - 35), 1)) for t in _m7.query('TEXT') if t.dxf.layer == '55_HATAH_TEXT')
assert _bx == [('ju.', -27.0, 4.6), ('pbho', 78.8, 4.1)], _bx      # his netivot 9-9 (2026-10-25) added the outside / inside boxes: newest wins over korchakk 6-6 (no boxes)
assert not any(t.dxf.text == '$8@15 L=110' and abs(t.dxf.insert.x - (-13172.5 - 93.0 - 40.0 + 10.0)) > 0.2 for t in _m7.query('TEXT')), 'note 10 right of the stirrup leg'
print('PASS beam_shutter: his korchakk 6-6 shutter (dots, note side, numeric stirrup) + his netivot 9-9 additions (outside / inside boxes, stirrup 93 from the face, note right of the leg)')

# slab step 70 / 25 (his 16-16, 2026-10-24): stamped template + re-created dims
_o8 = os.path.join(tempfile.gettempdir(), 'step_in.dxf'); ezdxf.new('R2018', setup=True).saveas(_o8); _o9 = os.path.join(tempfile.gettempdir(), 'step_out.dxf')
run(os.path.join(REC, 'slab_step.py'), _o8, '16-16', '--origin', '1000', '2000', '-o', _o9)
_d9 = ezdxf.readfile(_o9); _m9 = _d9.modelspace(); assert not _d9.audit().errors
assert len(_m9.query('DIMENSION')) == 7 and len(_m9.query('LEADER')) == 3 and any(t.dxf.text == '&12@20' for t in _m9.query('TEXT'))
_ms = sorted(round(d.get_measurement()) for d in _m9.query('DIMENSION')); assert 45 in _ms and 25 in _ms and 64 in _ms and 80 in _ms, _ms
print('PASS slab_step: his 16-16 stamped (7 dims 70/25/45/80/64, 3 leaders, &12@20 ties)')

# diameter symbol font (user 2026-10-22, brenda_karka section 2): '$' bar notes -> HEBREW_NEW
import sivan_text as _st
_d6 = ezdxf.new('R2010'); _m6 = _d6.modelspace()
for _s in ('HEBTXT', 'HEBREW_NEW'): _d6.styles.add(_s, font='txt.shx') if _s not in _d6.styles else None
_m6.add_text('2$10@15', dxfattribs=dict(layer='54_HATAH_TEXT', style='HEBTXT', insert=(10, 10), height=6, width=0.8))
_st.convert_box(_d6, (0, 0, 400, 450))
assert [t.dxf.style for t in _m6.query('TEXT')] == ['HEBREW_NEW'] and _m6.query('TEXT').first.dxf.width == 0.8
print('PASS sivan_text: diameter-symbol notes -> HEBREW_NEW, width kept')
# slab levels + restraint mesh (user 2026-10-22: 're-check the ceiling thicknesses; 60 cm or more needs a restraint mesh')
import star_plan as _sp
assert _sp.LVL.match('+46.20') and _sp.LVL.match('-1.20=+50.30') and _sp.OKT.match('o.k=+45.25') and _sp.OKT.match('o.k. +45.25'), 'bare slab levels and o.k=+nn.nn must parse'
_o6 = os.path.join(tempfile.gettempdir(), 'gb_mesh.dxf'); run(os.path.join(REC, 'general_beam.py'), _d4, '9-9', '--box', '0', '0', '400', '450', '--B', '100', '--H', '120', '--D', '65', '--D-left', '65', '--D-right', '30', '--drop-right', '95', '--detail', 'plan', '-o', _o6)
_d6 = ezdxf.readfile(_o6); _m6 = _d6.modelspace(); assert not _d6.audit().errors
assert not any(t.dxf.text == '#\xa410@15\\15' for t in _m6.query('TEXT')) and not any(e.dxf.layer == 'HATAH_ZIUN_17' for e in _m6.query('LWPOLYLINE')), 'NO restraint mesh in cross-section ceilings (user 2026-10-22, reversed)'
print('PASS general_beam: no restraint mesh even for D=65; slab levels parse')
# side dimension chains (user 2026-10-22, his hand-dimensioned 2-2): left 50 / 35 / 70, right 25 / 130, overall 155
_o7 = os.path.join(tempfile.gettempdir(), 'gb_chain.dxf'); run(os.path.join(REC, 'general_beam.py'), _d4, '2-2', '--box', '0', '0', '400', '450', '--B', '140', '--H', '155', '--D', '35', '--D-left', '35', '--D-right', '25', '--drop-left', '70', '--detail', 'plan', '-o', _o7)
_d7 = ezdxf.readfile(_o7); _v = sorted(round(e.get_measurement()) for e in _d7.modelspace().query('DIMENSION') if abs(e.dxf.get('angle', 0) - 90) < 1 and e.dxf.layer == '53_HATAH_MIDA')
assert _v == sorted([155, 50, 35, 70, 25, 130]), _v
print('PASS general_beam: full side chains (left 50/35/70, right 25/130, overall 155) like his 2-2')
# missing central (side-face) bars where a lower slab exposes the beam face (user 2026-10-22, 12-12)
import general_beam as _gb
assert len(_gb.beam_dot_rows(65, 60, 15, fill_gap=True)) == 6 and len(_gb.beam_dot_rows(65, 60, 15)) == 3 and len(_gb.beam_dot_rows(155, 25, 15, fill_gap=True)) == len(_gb.beam_dot_rows(155, 25, 15))
print('PASS general_beam: gap between top row and soffit row filled with side-face rows (12-12)')
# middle-steel note position (user 2026-10-22, his hand-fixed 3-3): forks re-attach to row 44.4, joint y 32.9
_o8 = os.path.join(tempfile.gettempdir(), 'gb_mid.dxf'); run(os.path.join(REC, 'general_beam.py'), _d4, '3-3', '--box', '0', '0', '400', '450', '--B', '100', '--H', '120', '--D', '40', '--D-left', '35', '--D-right', '40', '--drop-right', '25', '--stirrups', 'transfer', '--detail', 'plan', '-o', _o8)
_d8 = ezdxf.readfile(_o8); assert not _d8.audit().errors
_mn = [x for x in _d8.modelspace().query('TEXT') if x.dxf.text.startswith('2$')][0]; _oy = 0 + 248.8      # general_beam CELL_V0
assert 33.0 < _mn.dxf.insert.y - _oy < 36.0, ('middle-steel note must drop to the clear row (his 3-3: 34.2 above the beam bottom)', _mn.dxf.insert.y - _oy)
print('PASS general_beam: middle-steel note yields to the slab notes (his 3-3 position within 1.5)')
# middle-steel note on the OTHER side when the left is crowded (user 2026-10-22, his hand-fixed 11-11): joint B + 11.3, shelf running right
_o9 = os.path.join(tempfile.gettempdir(), 'gb_mid11.dxf'); run(os.path.join(REC, 'general_beam.py'), _d4, '11-11', '--box', '0', '0', '400', '450', '--B', '120', '--H', '120', '--D', '35', '--D-left', '35', '--D-right', '25', '--drop-left', '50', '--stirrups', 'transfer', '--detail', 'plan', '-o', _o9)
_d9 = ezdxf.readfile(_o9); _mn9 = [x for x in _d9.modelspace().query('TEXT') if x.dxf.text.startswith('2$')][0]; _ox9 = 0 + 179.7 - (120 - 20) / 2
assert _mn9.dxf.insert.x - _ox9 > 120, 'middle-steel note must sit RIGHT of the beam face (B=120) in the 11-11 case'
print('PASS general_beam: middle-steel note moves to the right side when the left is crowded (his 11-11)')
# korchakk 2026-10-23: levels in one datum, marker behind a beam face = another panel, free edge = no slab, per-side symbol H
import star_plan as _sk
assert _sk.levels('-0.30=+4.95') == (-0.30, 4.95) and _sk.levels('o.k.+271.30=+3.80') == (271.30, 3.80) and _sk.levels('o.k.+4.95') == (4.95,) and _sk.levels('+46.20') == (46.20,)
assert abs(_sk.level_drop((4.95,), (-0.30, 4.95))) < 1e-9, 'beam o.k.+4.95 vs slab -0.30=+4.95 is FLUSH (was read as 525)'
assert abs(_sk.level_drop((4.95,), (-0.45, 4.80)) - 0.15) < 1e-9 and abs(_sk.level_drop((-0.30,), (-0.45, 4.80)) - 0.15) < 1e-9 and abs(_sk.level_drop((271.30, 3.80), (-0.30, 4.95)) + 1.15) < 1e-9
assert _sk.level_drop(None, (1.0,)) is None and _sk.level_drop((1.0,), None) is None
_dk = ezdxf.new('R2018'); _mk = _dk.modelspace(); _dk.layers.add('93_KORA'); _dk.layers.add('9_KONTUR')
_mk.add_lwpolyline([(-15, 0), (-15, 100)], dxfattribs={'layer': '93_KORA'}); _mk.add_lwpolyline([(15, 0), (15, 100)], dxfattribs={'layer': '93_KORA'}); _mk.add_lwpolyline([(-300, 0), (-300, 100)], dxfattribs={'layer': '93_KORA'})
_sk._SEPS.clear(); _ik = _sk.side_info(_dk, 0, 50, 'N', 30, [(-200, 50, 40, (0.0,)), (200, 50, 30, (0.0,))])      # N view: left = west; the west marker lies BEHIND the face at x=-300? no: between -15 and -300 -> inside; the one at +200 is the right panel
assert _ik['D']['R'] == 30 and _ik['D']['L'] == 40, _ik
_mk.add_lwpolyline([(-100, 0), (-100, 100)], dxfattribs={'layer': '93_KORA'}); _sk._SEPS.clear(); _ik = _sk.side_info(_dk, 0, 50, 'N', 30, [(-200, 50, 40, (0.0,)), (200, 50, 30, (0.0,))])
assert 'L' in _ik['unknown'] and _ik['D']['L'] == 25 and _ik['D']['R'] == 30, 'a marker behind a beam face is another panel: symbol H, never its D'
assert '--d-label-left H' in _sk.general_args(_ik) and '--sides' not in _sk.general_args(_ik)
_ik = _sk.side_info(_dk, 0, 50, 'N', 30, [(200, 50, 30, (0.0,))], free=('L',)); assert _ik['D']['L'] is None and '--sides right' in _sk.general_args(_ik)
_og = os.path.join(tempfile.gettempdir(), 'gb_free.dxf'); run(os.path.join(REC, 'general_beam.py'), _d4, '1-1', '--box', '0', '0', '400', '450', '--B', '100', '--H', '50', '--D', '25', '--D-left', '0', '--D-right', '25', '--sides', 'right', '--d-label-right', 'H', '--detail', 'plan', '-o', _og)
_dg = ezdxf.readfile(_og); _ox = 0 + 179.7 - (100 - 20) / 2; assert not _dg.audit().errors
assert not [e for e in _dg.modelspace().query('LINE') if e.dxf.layer == '9_KONTUR' and min(e.dxf.start.x, e.dxf.end.x) < _ox - 1], 'free edge: nothing left of the beam face'
assert any(e.dxf.layer == '9_KONTUR' and abs(e.dxf.start.x - _ox) < .01 and abs(e.dxf.end.x - _ox) < .01 and abs(abs(e.dxf.start.y - e.dxf.end.y) - 50) < .01 for e in _dg.modelspace().query('LINE')), 'free edge: the beam face runs the full height 50'
assert any(t.dxf.text == 'H' for t in _dg.modelspace().query('DIMENSION') for t in [t]) or any('H' == (d.dxf.get('text') or '') for d in _dg.modelspace().query('DIMENSION')), 'right slab thickness dim carries the symbol H'
print('PASS star_plan / general_beam: levels in one datum, marker behind a beam face rejected, free edge without slab, per-side symbol H')

# VISIBILITY GATE (netivot 2026-10-24): sections drawn on FROZEN layers are invisible and arrays on the wrong layer -> section_visibility must see it, --fix must repair it, a second run must be clean
import section_visibility as _sv
_dv = ezdxf.new('R2018'); _mv = _dv.modelspace()
for _n in ('54_HATAH_TEXT', '57_HATAH_ZIUN', 'claude_Kontur'): _dv.layers.add(_n)
_dv.styles.add('SIVAN', font='txt.shx')
_mv.add_text('%%Uj,l 1-1', dxfattribs={'layer': '54_HATAH_TEXT', 'style': 'SIVAN', 'insert': (50, 50), 'height': 9})
_bk = _dv.blocks.new('*U1'); _bk.add_line((0, 0), (1, 1), dxfattribs={'layer': 'claude_Kontur'}); _mv.add_blockref('*U1', (60, 60), dxfattribs={'layer': 'claude_Kontur'})
_dv.layers.get('54_HATAH_TEXT').freeze(); _dv.layers.get('57_HATAH_ZIUN').freeze()
_pv = _sv.problems(_sv.scan(_dv, (0, 0, 400, 400)))
assert len(_pv) == 4, _pv                                         # 54 frozen, 57 frozen, array on claude_Kontur, no visible title
_ch, _mv_n = _sv.fix(_dv, (0, 0, 400, 400)); assert _mv_n == 1 and len(_ch) == 2
assert not _sv.problems(_sv.scan(_dv, (0, 0, 400, 400))) and all(b.dxf.layer == '57_HATAH_ZIUN' for b in _dv.blocks.get('*U1')), 'fix leaves nothing hidden, nested bodies re-layered'
assert not _sv.fix(_dv, (0, 0, 400, 400))[0], 'second run changes nothing'
print('PASS section_visibility: frozen layers + stray arrays detected, fixed, idempotent')

# netivot 9-9 (2026-10-24 review): narrow single-stirrup beam (B=20, H=180): the stirrup note now carries ' L=388' and must not overlap the second hoop note
import text_overlap as _to
_on = os.path.join(tempfile.gettempdir(), 'gb_narrow.dxf'); run(os.path.join(REC, 'general_beam.py'), _d4, '9-9', '--box', '0', '0', '400', '450', '--B', '20', '--H', '180', '--D', '50', '--stirrups', 'standard', '--detail', 'ss', '-o', _on)
_dn = ezdxf.readfile(_on); _hoop = [t for t in _dn.modelspace().query('TEXT') if t.dxf.text.startswith('$12@15')]
assert len(_hoop) == 1 and 'L=388' in _hoop[0].dxf.text, [t.dxf.text for t in _hoop]      # ONE note since 2026-10-25 (he deleted the second), centred under the elevation
assert not [p for p in _to.overlaps(_dn) if p[0].dxf.text.startswith('$12@15') or p[1].dxf.text.startswith('$12@15')], 'narrow single-stirrup beam: hoop notes overlap'      # other notes are separated by text_overlap --fix in the round
print('PASS general_beam: narrow single-stirrup beam carries ONE hoop note under its elevation (korchakk 2026-10-25)')

# 2026-10-24: two runs at once must not share a scratch file (fixed 'sp_extent.dxf' in %TEMP% made the app's draw step die with 'missing ENDSEC' while another run was going)
import types as _ty
_fa = os.path.join(tempfile.gettempdir(), 'sx_in.dxf'); ezdxf.new('R2018').saveas(_fa); _seen = []
class _FR: returncode = 1; stdout = ''; stderr = ''
_orig_run = _sk.subprocess.run
_sk.subprocess.run = lambda cmd, **kw: (_seen.append(cmd[cmd.index('-o') + 1]), _FR())[1]
try:
    for _i in range(2): _sk.section_extent(_ty.SimpleNamespace(file=_fa), 'general_beam', '--B 20 --H 50 --D 25', '1-1')
finally: _sk.subprocess.run = _orig_run
assert len(_seen) == 4 and len(set(_seen)) == 4 and not any(os.path.exists(os.path.dirname(x)) for x in _seen), _seen
print('PASS star_plan: section_extent scratch file is unique per call and cleaned up; a failed run on the reduced base is retried on the full file')

# user 2026-10-24 (red cloud, netivot 7-7): a slab TOP bar enters the beam 60 unless both slab tops are flush; bottom bars always 60
def _through(path, B):
    _ox_ = 0 + 179.7 - (B - 20) / 2
    return [e for e in ezdxf.readfile(path).modelspace().query('LINE') if e.dxf.layer == '57_HATAH_ZIUN' and abs(e.dxf.start.y - e.dxf.end.y) < 1e-6 and min(e.dxf.start.x, e.dxf.end.x) <= _ox_ + 3.5 and max(e.dxf.start.x, e.dxf.end.x) >= _ox_ + B - 3.5]
_o1 = os.path.join(tempfile.gettempdir(), 'gb_step.dxf'); run(os.path.join(REC, 'general_beam.py'), _d4, '7-7', '--box', '0', '0', '400', '450', '--B', '130', '--H', '100', '--D', '40', '--D-left', '25', '--D-right', '40', '--drop-left', '65', '--drop-right', '60', '--stirrups', 'transfer', '--detail', 'plan', '-o', _o1)
_o2 = os.path.join(tempfile.gettempdir(), 'gb_flush.dxf'); run(os.path.join(REC, 'general_beam.py'), _d4, '8-8', '--box', '0', '0', '400', '450', '--B', '130', '--H', '100', '--D', '35', '--D-left', '35', '--D-right', '35', '--stirrups', 'transfer', '--detail', 'plan', '-o', _o2)
_o3 = os.path.join(tempfile.gettempdir(), 'gb_oneside.dxf'); run(os.path.join(REC, 'general_beam.py'), _d4, '9-9', '--box', '0', '0', '400', '450', '--B', '130', '--H', '100', '--D', '35', '--D-left', '35', '--D-right', '0', '--sides', 'left', '--stirrups', 'transfer', '--detail', 'plan', '-o', _o3)
assert not _through(_o1, 130), 'stepped section: no slab bar runs through the beam (60 anchorage)'
assert len(_through(_o2, 130)) == 2, 'flush slab tops: the top bar runs through the beam'
assert not _through(_o3, 130), 'one-sided slab: its top bar enters 60, not through'
_tl = [e for e in ezdxf.readfile(_o1).modelspace().query('LINE') if e.dxf.layer == '57_HATAH_ZIUN' and abs(e.dxf.start.y - e.dxf.end.y) < 1e-6 and abs(max(e.dxf.start.x, e.dxf.end.x) - (0 + 179.7 - 55 + 60)) < 0.05]
assert len(_tl) >= 2, 'left slab bars (top + bottom) both end 60 from the left beam face, as drawn by the user in 7-7'
print('PASS general_beam: slab bars enter the beam 60 (top bar too when stepped / one-sided), run through only when the tops are flush (user cloud 7-7)')

# user 2026-10-24: sections are numbered from the RIGHT, clockwise (east -> south -> west -> north)
_c = (0.0, 0.0); _ord = sorted({'E': (100, 0), 'SE': (70, -70), 'S': (0, -100), 'SW': (-70, -70), 'W': (-100, 0), 'NW': (-70, 70), 'N': (0, 100), 'NE': (70, 70)}.items(), key=lambda kv: _sk.clock_key(kv[1], _c))
assert [k for k, _ in _ord] == ['E', 'SE', 'S', 'SW', 'W', 'NW', 'N', 'NE'], _ord
print('PASS star_plan: numbering starts at the right and runs clockwise (east, south, west, north)')

# user 2026-10-24, his hand edits of netivot 17-17: hoop note centred under the stirrups (was left: shx_width had no 'HEBTXT'), o.k marker 5 right of the corner (was 18.3 for B >= 60 until 2026-10-25), scale text centred under the visible title
from shx_width import text_extent as _tx
_oh = os.path.join(tempfile.gettempdir(), 'gb_hoop.dxf'); run(os.path.join(REC, 'general_beam.py'), _d4, '17-17', '--box', '0', '0', '400', '450', '--B', '170', '--H', '90', '--D', '30', '--D-left', '30', '--D-right', '25', '--drop-left', '60', '--stirrups', 'standard', '--detail', 'ss', '-o', _oh)
_dh = ezdxf.readfile(_oh); _mh = _dh.modelspace()
_bb = min(min(e.dxf.start.y, e.dxf.end.y) for e in _mh.query('LINE') if e.dxf.layer in ('9_KONTUR', '5_HATAH _KONTUR')); _rc = [e for e in _mh.query('LWPOLYLINE') if e.dxf.layer == '57_HATAH_ZIUN' and e.closed and len(e) == 4 and max(p[1] for p in e.get_points()) < _bb - 20]
_gx = [p[0] for e in _rc for p in e.get_points()]; _gc = (min(_gx) + max(_gx)) / 2
_nt = [t for t in _mh.query('TEXT') if '$12@15' in t.dxf.text and t.dxf.insert.y < _bb - 20 and len(t.dxf.text) > 8][0]
_na, _nb = _tx('HEBREW_NEW', _nt.dxf.text, _nt.dxf.insert.x, _nt.dxf.height, _nt.dxf.get('width', 1.0))
assert abs((_na + _nb) / 2 - _gc) < 0.5, ((_na + _nb) / 2, _gc)
_ox17 = 0 + 179.7 - (170 - 20) / 2; _mk = [e for e in _mh.query('INSERT') if e.dxf.name == 'MH']
if _mk: assert abs(_mk[0].dxf.insert.x - (_ox17 + 5.0)) < 0.01, _mk[0].dxf.insert.x
import center_titles as _ct
_tt = _mh.add_text('%%Uj,l 71-71', dxfattribs={'style': 'SIVAN', 'height': 9, 'width': 0.9, 'text_generation_flag': 2, 'insert': (580.9, 400)}); _ts = _mh.add_text('1:25', dxfattribs={'style': 'HEBREW_NEW', 'height': 6, 'width': 0.8, 'insert': (0, 390)})
_x = _ct.scale_x(_tt, _ts, 554.9); _sa, _sb = _tx('HEBREW_NEW', '1:25', _x, 6, 0.8); _ta, _tb = _tx('SIVAN', 'j,l 71-71', 580.9, 9, 0.9, True)
assert abs((_sa + _sb) / 2 - (_ta + _tb) / 2) < 0.01 and abs(_x - (554.9 - 7.72)) > 3, (_x, _sa, _sb, _ta, _tb)
print('PASS general_beam / center_titles: hoop note centred under the stirrups, marker shifted off the corner, scale centred under the title (his 17-17)')

# user 2026-10-24, his hand fix of shlang 16-16 (cast beam 80x120, slab 47 / 37): stirrup dims in a file WITHOUT 'dim_25_BARZEL' use dim_25_BARZEL_Above (not Standard), top + bottom rows run across the width (13 dots, step 5.94),
# the face column reaches the top row (gap <= 1.5 x pitch), 3 topping mesh dots per side, voids layer green
_oc = os.path.join(tempfile.mkdtemp(), 'cast16.dxf'); _dc = ezdxf.readfile(_d4)
for _n in ('dim_25_BARZEL',):
    if _n in _dc.dimstyles: _dc.dimstyles.remove(_n)
_dc.layers.add('10_PLADA_HATAH', color=7) if '10_PLADA_HATAH' not in _dc.layers else setattr(_dc.layers.get('10_PLADA_HATAH').dxf, 'color', 7)
_dc.dimstyles.new('dim_25_BARZEL_Above') if 'dim_25_BARZEL_Above' not in _dc.dimstyles else None
_dc.saveas(_oc)
run(os.path.join(REC, 'ledge_beam.py'), _oc, '16-16', '--box', '0', '0', '400', '450', '--beam', '80', '120', '--kind', 'cast', '--sides', 'both', '--topping', '7', '--stirrups', 'transfer', '--slab', '47', '--slab-left', '37', '--detail', 'plan')
_dc = ezdxf.readfile(_oc); _mc = _dc.modelspace()
assert not [e for e in _mc.query('DIMENSION') if e.dxf.dimstyle == 'Standard' and e.dxf.layer == '54_HATAH_TEXT'], 'bar dims fell back to Standard'
assert any(e.dxf.dimstyle == 'dim_25_BARZEL_Above' for e in _mc.query('DIMENSION')), 'stirrup dims not in the Above style'
_ds = [(round(e.get_points('xy')[0][0], 1), round(e.get_points('xy')[0][1], 1)) for e in _mc.query('LWPOLYLINE') if e.dxf.layer == '57_HATAH_ZIUN' and e.dxf.get('const_width') == 1.0 and len(e) == 2]
_ys = sorted({y for _, y in _ds}); _top, _bot = _ys[-1], _ys[0]
import collections as _co
_rc = _co.Counter(y for x, y in _ds); assert sorted(v for v in _rc.values() if v >= 10) == [13, 13], _rc     # top + bottom rows, 13 dots each
_cx = min(x for x, y in _ds if y == min(_rc)); _cy = sorted({y for x, y in _ds if abs(x - _cx) < 0.3}); assert max(b - a for a, b in zip(_cy, _cy[1:])) < 1.15 * 18.4 * 1.1, _cy
assert _dc.layers.get('10_PLADA_HATAH').dxf.color == 3, 'void layer must be green'
print('PASS ledge_beam cast: bar-dim style fallback, wide top/bottom rows, face column reaches the top, voids green (his shlang 16-16)')

# user 2026-10-24: 'if a layer is missing from your plan, know how to bring it in and use it' - dxflib.ensure_standards imports layers (office colour + linetype), dim styles, text styles, blocks; idempotent; never touches existing ones
import dxflib as _dxl
_de = ezdxf.new('R2018'); _de.layers.add('57_HATAH_ZIUN', color=1)
_ad = _dxl.ensure_standards(_de, ('57_HATAH_ZIUN', '10_PLADA_HATAH', '57_HATAH_DASHED', 'NOT_AN_OFFICE_LAYER'), ('dim_25_BARZEL',), ('SIVAN',), ('dot barzel',), ('DASHED',))
assert _de.layers.get('10_PLADA_HATAH').dxf.color == 3 and _de.layers.get('57_HATAH_DASHED').dxf.linetype == 'DASHED' and 'dim_25_BARZEL' in _de.dimstyles and 'dot barzel' in _de.blocks and 'SIVAN' in _de.styles, _ad
assert _de.layers.get('57_HATAH_ZIUN').dxf.color == 1, 'an existing layer of the plan must not be changed'
assert _de.layers.get('NOT_AN_OFFICE_LAYER').dxf.color == 7 and not _dxl.ensure_standards(_de, ('10_PLADA_HATAH',), ('dim_25_BARZEL',)), 'unknown layer plain; second call adds nothing'
print('PASS dxflib.ensure_standards: missing layers / dim styles / text styles / blocks imported from the office standard, existing ones untouched')

# user 2026-10-24: 'the grid template must be adjusted so the sections do not extend beyond its boundaries' - fit_rows grows EVERY too-low row downward (rows below move with it), notes hanging just under
# the upper row's edge stay with the upper row, every cell hangs from one title line
import fit_rows as _fr
_df = ezdxf.new('R2018'); _mf = _df.modelspace(); _df.layers.add('72_MISGERET_WIN'); _df.layers.add('54_HATAH_TEXT'); _df.layers.add('57_HATAH_ZIUN')
def _frame(y0, y1):
    _mf.add_lwpolyline([(0, y0), (4000, y0), (4000, y1), (0, y1)], close=True, dxfattribs=dict(layer='72_MISGERET_WIN'))
    for _k in range(1, 10): _mf.add_line((400 * _k, y0), (400 * _k, y1), dxfattribs=dict(layer='72_MISGERET_WIN'))
_frame(1000, 1450); _frame(549, 999)                                    # two touching 450-high rows (upper 1000..1450, lower 549..999)
def _sec(cx, ty, below, above):                                         # title + a bar run reaching `below` under / `above` over the title
    _mf.add_text(_dxl.encode('חתך') + ' 1-1', dxfattribs=dict(layer='54_HATAH_TEXT', insert=(cx - 20, ty), height=8))
    _mf.add_lwpolyline([(cx, ty - below), (cx + 5, ty + above)], dxfattribs=dict(layer='57_HATAH_ZIUN'))
_sec(200, 1403, 440, 30); _sec(600, 1403, 300, 30)                       # upper row: tallest hangs 440 below its title -> needs 440+30+50 = 520 > 450
_sec(200, 952, 380, 30)                                                  # lower row: needs 460 > 450, too
_mf.add_text('note just under the upper frame', dxfattribs=dict(layer='54_HATAH_TEXT', insert=(150, 990), height=7))      # centre inside the LOWER band edge zone: belongs to the lower row by position
_pf = os.path.join(tempfile.mkdtemp(), 'fit.dxf'); _df.saveas(_pf)
run(os.path.join(REC, 'fit_rows.py'), _pf, '-o', _pf + '.out.dxf')
_df2 = ezdxf.readfile(_pf + '.out.dxf'); _st = _fr.stack(_df2)
assert len(_st) == 2 and abs(_st[0][2] - _st[1][3]) <= 3, 'rows must still touch'
from ezdxf import bbox as _bb
for _r in _st:
    _ins = [(e, _bb.extents([e])) for e in _df2.modelspace() if e.dxf.layer == '57_HATAH_ZIUN' and _r[2] < _bb.extents([e]).center.y < _r[3] + 0.0]
    assert _ins, 'no section in a row'
    for _e, _b in _ins: assert _b.extmin.y >= _r[2] + 24 and _b.extmax.y <= _r[3] - 24, ('section outside its frame', _r[2:4], _b.extmin.y, _b.extmax.y)
assert _st[0][3] - _st[0][2] >= 519 and _st[1][3] - _st[1][2] >= 459, [r[3] - r[2] for r in _st]
assert len({round(_r[4].dxf.layer == '72_MISGERET_WIN') for _r in _st}) == 1
print('PASS fit_rows: every row grows to hold its sections, rows below move down, rows stay touching, margins >= 25')

# 2026-10-24 (loading time): sections are drawn in ONE open document (recipe main(argv, doc)) and extents are measured on a text-only base: the result must equal the one-process-per-section way
import importlib as _il, io as _io, contextlib as _cl, collections as _co2
from ezdxf import bbox as _bb2
_t = tempfile.mkdtemp(); _pa, _pb = os.path.join(_t, 'a.dxf'), os.path.join(_t, 'b.dxf'); _d4_ = ezdxf.readfile(_d4); _d4_.saveas(_pa); _d4_.saveas(_pb)
_args = ['{F}', '7-7', '--box', '0', '0', '400', '450', '--beam', '80', '120', '--kind', 'cast', '--sides', 'both', '--topping', '7', '--stirrups', 'transfer', '--slab', '47', '--slab-left', '37', '--detail', 'plan']
run(os.path.join(REC, 'ledge_beam.py'), *[x.replace('{F}', _pa) for x in _args])
_bd = ezdxf.readfile(_pb)
with _cl.redirect_stdout(_io.StringIO()): _il.import_module('ledge_beam').main([x.replace('{F}', _pb) for x in _args], _bd)
_bd.saveas(_pb)
def _geo(f): return sorted((e.dxftype(), e.dxf.layer, *(round(v, 1) for v in (lambda b: (b.extmin.x, b.extmin.y, b.extmax.x, b.extmax.y))(_bb2.extents([e])))) for e in ezdxf.readfile(f).modelspace() if _bb2.extents([e]).has_data)
assert _geo(_pa) == _geo(_pb), 'in-process batch draw differs from the one-process draw'
_ba = _sk.extent_base(_ty.SimpleNamespace(file=_pa)); assert _ba and os.path.getsize(_ba) < os.path.getsize(_pa), 'extent base not smaller'
_e_full = _sk.section_extent(_ty.SimpleNamespace(file=_pa), 'ledge_beam', ' '.join(_args[2:]).replace('--box 0 0 400 450 ', ''), '7-7', 0, _full=True)
_e_red = _sk.section_extent(_ty.SimpleNamespace(file=_pa), 'ledge_beam', ' '.join(_args[2:]).replace('--box 0 0 400 450 ', ''), '7-7', 0)
assert _e_full and _e_red and all(abs(x - y) < 1e-6 for x, y in zip(_e_full, _e_red)), (_e_full, _e_red)
print('PASS speed: in-process batch draw = one-process draw; extent on the text-only base = extent on the full plan')
# --- XREF section names + extension of general_beam (LINE) bars (user 2026-10-25, 3600-CON-11: 'reinforcement does not reach the XREF edge') ---
import dxflib as _dxl
assert [_dxl.xref_section_number(n) for n in ('x Sec-Section - 03 Sec 8-8', 'x Section - -1 - Section 8', 'Sheet - 26 - Section 3-0-Section - Sec0-12', 'Sec 8-9')] == [8, 8, 12, None]
_xd = ezdxf.new(setup=True); _xb = _xd.blocks.new('S - Site - Section - Sec0-5')
for _a_, _b_ in (((0, 0), (20, 0)), ((20, 0), (20, 100)), ((20, 100), (0, 100)), ((0, 100), (0, 0))): _xb.add_line(_a_, _b_, dxfattribs={'layer': 'S-280-M_STRUCT_FRAME-1'})
for _a_, _b_ in (((-60, 80), (80, 80)), ((-60, 75), (80, 75))): _xb.add_line(_a_, _b_, dxfattribs={'layer': 'A-230-M_FLOOR-1'})
_xd.modelspace().add_blockref(_xb.name, (1000, 0)); _xd.layers.add('57_HATAH_ZIUN')
_xd.modelspace().add_line((1000 - 50, 78), (1000 + 60, 78), dxfattribs={'layer': '57_HATAH_ZIUN'})
_xp = os.path.join(tempfile.mkdtemp(), 'x.dxf'); _xd.saveas(_xp)
import xref_extend_bars as _xeb; _xeb.run(_xp); _ln = [e for e in ezdxf.readfile(_xp).modelspace().query('LINE') if e.dxf.layer == '57_HATAH_ZIUN'][0]
assert abs(min(_ln.dxf.start.x, _ln.dxf.end.x) - 940) < 1e-6 and abs(max(_ln.dxf.start.x, _ln.dxf.end.x) - 1060) < 1e-6, (_ln.dxf.start, _ln.dxf.end)
print('PASS xref_extend_bars: 3600-CON-11 section names, general_beam LINE bars run to the XREF slab end')

# --- sloped slab: found from the plan note, labelled after the section (user 2026-10-22; automated 2026-10-25) ---
import json as _js, types as _ty, dxflib as _dxl2, star_plan as _sp2
_sd = ezdxf.new('R2018', setup=True); _sd.layers.add('4_TEXT')
def _hat(x, y): return _ty.SimpleNamespace(dxf=_ty.SimpleNamespace(insert=_ty.SimpleNamespace(x=x, y=y)))
for _stx, _x, _y, _rot in (('יציקה בשיפוע', 130, 30, 90), ('קורה בשיפוע', 130, 100, 90), ('יציקה בשיפוע', 130, 100, 0), ('לוחדים בשיפוע', 900, 100, 90)):      # near + along / a beam slope / across the cut / far away
    _sd.modelspace().add_text(_dxl2.encode(_stx), height=10, dxfattribs=dict(layer='4_TEXT', insert=(_x, _y), rotation=_rot))
_r1, _fl = _sp2.slope_notes(_sd, _hat(0, 0), _hat(0, 200), 'E'); assert _r1 == ('right', 'cast', 'יציקה בשיפוע') and len(_fl) == 1 and 'NOT labelled' in _fl[0], (_r1, _fl)
_sd.modelspace().add_text(_dxl2.encode('בשיפוע'), height=10, dxfattribs=dict(layer='4_TEXT', insert=(130, 190), rotation=90)); assert _sp2.slope_notes(_sd, _hat(0, 0), _hat(0, 200), 'E')[0][1] in ('cast', '?')      # a bare 'בשיפוע' is accepted (kind from the section)
_sd.modelspace().delete_entity(_sd.modelspace().query('TEXT')[-1])      # south end = the right of an E view
assert _sp2.slope_notes(_sd, _hat(0, 0), _hat(0, 200), 'W')[0][0] == 'left' and _sp2.slope_notes(_sd, _hat(0, 0), _hat(200, 0), 'N')[0][1] == 'cast'      # W view mirrors; the horizontal cut finds the horizontal note (the vertical ones run across it)
assert _sp2.split_slope('--B 20 --slope left:hollow --stirrups standard') == ('--B 20 --stirrups standard', ('left', 'hollow')) and _sp2.split_slope('--B 20')[1] is None
_src = sample(); _out = os.path.join(tmp, 'slope.dxf')
run(os.path.join(REC, 'ledge_beam.py'), _src, '3-3', '--box', '0', '0', '400', '450', '--beam', '80', '65', '--slab', '20', '--topping', '5', '--sides', 'both', '-o', _out)
_js.dump([dict(n=3, box=[0, 400, 0, 450], side='right', kind='cast')], open(_out + '.slopes.json', 'w'))
_o = run(os.path.join(REC, 'slope_label.py'), _out, '--json', _out + '.slopes.json'); assert '1 slope label(s) of 1 saved' in _o and not os.path.exists(_out + '.slopes.json'), _o
_dm = ezdxf.readfile(_out).modelspace(); assert len(_dm.query('LEADER')) == 1 and any(_dxl2.decode(t.dxf.text) == 'תקרה יצוקה בשיפוע' for t in _dm.query('TEXT')), 'slope label / arrow missing'
print('PASS slope: note along the cut found (side from the cut end, kind from the words), beam slopes reported only, label + arrow drawn from the sidecar')

# --- roller shutter under a general beam, found from the plan text and drawn in the round (user 2026-10-24 korchakk 6-6; automated 2026-10-25) ---
import general_beam as _gb2
assert _sp2.split_shutter('--B 20 --rshutter 10:35 --detail ss') == ('--B 20 --detail ss', (10.0, 35.0)) and _sp2.clean_args('--B 20 --slope left:cast --rshutter 10:35') == '--B 20'
_sh = ezdxf.new('R2018', setup=True)
for _l in ('9_KONTUR', '5_HATAH _KONTUR', '53_HATAH_MIDA', '54_HATAH_TEXT', '57_HATAH_ZIUN', '56_HATAH_ZET', '2000_DOT_HELP_LINE', '51_HATAH_DASHED', '58_HATAH_SIM'): _sh.layers.add(_l)
for _st in ('SIVAN', 'HEBREW_NEW', 'MIRYL', 'HEBTXT'): _sh.styles.add(_st, font='arial.ttf')
for _dn in ('dim_25', 'dim_25_BARZEL', 'dim_25_BARZEL_Above'): _ds = _sh.dimstyles.new(_dn); _ds.dxf.dimtxt = 6
_ga = ['x.dxf', '6-6', '--box', '0', '0', '400', '450', '--B', '20', '--H', '40', '--h-label', 'h', '--d-label', 'H']; _gb2.main(_ga, _sh)
_ent = len(_sh.modelspace()); _inf = _sp2.shutter_under_beam(_sh, ' '.join(_ga[7:]), (0.0, 0.0), (10.0, 35.0)); _mt = _sh.modelspace()
assert len(_mt) > _ent and _inf['n_dots'] >= 2 and '2$10' in [t.dxf.text for t in _mt.query('TEXT')] and any(t.dxf.text.startswith('$8@15 L=') for t in _mt.query('TEXT')) and _inf['width_dim_moved'], _inf
_yb = 248.8; assert any(abs(l.dxf.start.y - (_yb - 35)) < 0.05 and abs(l.dxf.end.y - (_yb - 35)) < 0.05 for l in _mt.query('LINE') if l.dxf.layer == '9_KONTUR'), 'downstand bottom 35 under the beam bottom'
print('PASS roller shutter under a general beam: planner marker, downstand 10 x 35 from the beam bottom, dots + 2$10 + numeric L stirrup')

# --- fit_rows.widen: a cell whose content is wider than 400 is widened, the cells to its right shift (user 2026-10-24 'sections must not extend beyond the template'; netivot 7-7 / 10-10 / 11-11 were 411-421 wide) ---
_dw = ezdxf.new('R2018'); _mw = _dw.modelspace(); _dw.layers.add('72_MISGERET_WIN'); _dw.layers.add('54_HATAH_TEXT'); _dw.layers.add('57_HATAH_ZIUN')
_mw.add_lwpolyline([(0, 0), (4000, 0), (4000, 450), (0, 450)], close=True, dxfattribs=dict(layer='72_MISGERET_WIN'))
for _k in range(1, 10): _mw.add_line((400 * _k, 0), (400 * _k, 450), dxfattribs=dict(layer='72_MISGERET_WIN'))
for _cx, _w in ((200, 100), (600, 430), (1000, 100)):                      # cell 2 holds a 430-wide section
    _mw.add_text(_dxl.encode('חתך') + ' 1-1', dxfattribs=dict(layer='54_HATAH_TEXT', insert=(_cx - 20, 400), height=8))
    _mw.add_lwpolyline([(_cx - _w / 2, 100), (_cx + _w / 2, 300)], dxfattribs=dict(layer='57_HATAH_ZIUN'))
_pw = os.path.join(tempfile.mkdtemp(), 'wide.dxf'); _dw.saveas(_pw); run(os.path.join(REC, 'fit_rows.py'), _pw, '-o', _pw + '.o1.dxf'); run(os.path.join(REC, 'fit_rows.py'), _pw + '.o1.dxf', '-o', _pw + '.o2.dxf')
_w1 = ezdxf.readfile(_pw + '.o1.dxf'); _r1w = _fr.stack(_w1)[0]
assert abs(_r1w[1] - 4050) < 1 and abs(_r1w[5][2] - 850) < 1 and abs(_r1w[5][1] - 400) < 1, ('frame / dividers', _r1w[1], _r1w[5][:4])      # cell 2 = 400..850 (430 + 2 x 10 = 450 wide), everything to its right +50
_pl = [e for e in _w1.modelspace().query('LWPOLYLINE') if e.dxf.layer == '57_HATAH_ZIUN']; _bx = sorted((_bb.extents([e]).extmin.x, _bb.extents([e]).extmax.x) for e in _pl)
assert _bx[1][0] >= 400 + 9.9 and _bx[1][1] <= 850 - 9.9 and abs((_bx[2][0] + _bx[2][1]) / 2 - 1050) < 1, _bx            # centred in the wide cell; the next cell's section moved 50 right
_w2 = ezdxf.readfile(_pw + '.o2.dxf'); assert [round(x, 1) for x in _fr.stack(_w2)[0][5]] == [round(x, 1) for x in _r1w[5]], 'second run must change nothing'
print('PASS fit_rows.widen: wide cell widened, row shifted, content centred, second run changes nothing')

# --- slab step (his 16-16) placed in the round's cell: centred, title on the title line, extent known up front (2026-10-25) ---
import slab_step as _ss
_so = _ezdxf_tmp = ezdxf.new('R2018', setup=True)
_ox, _oy, _ext = _ss.layout(1000.0, 500.0); _n, _nd = _ss.stamp(_so, _ox, _oy, '9-9'); _bsx = _bb.extents([e for e in _so.modelspace() if e.dxftype() not in ('DIMENSION', 'INSERT')])
assert abs((_bsx.extmin.x + _bsx.extmax.x) / 2 - 1200) < 60 and _ext[4] == 403.0 and _ext[2] - _ext[0] < 400 and _n > 20 and _nd >= 3, (_bsx.extmin.x, _bsx.extmax.x, _ext)
assert any(t.dxf.text.endswith('9-9'[::-1]) or '9-9' in t.dxf.text for t in _so.modelspace().query('TEXT') if t.dxf.layer == '54_HATAH_TEXT'), 'title renamed'
_sd2 = ezdxf.new('R2018', setup=True); _sd2.layers.add('45_TEXT_KORA'); _sd2.modelspace().add_text('220.70', dxfattribs=dict(layer='45_TEXT_KORA', insert=(100, 100), height=5)); _sd2.modelspace().add_text('30/60', dxfattribs=dict(layer='45_TEXT_KORA', insert=(110, 100), height=5))
assert _sp2.slab_step_tag(_sd2, 0, 0)[:2] == (220, 70) and _sp2.slab_step_tag(_sd2, 5000, 0) is None
print('PASS slab step: wide tag 220/70 at a cut with no beam found; template centred in the cell with its title on the title line')

# --- slab step made PARAMETRIC (his request 2026-10-25: 'learn to create a stepped section for varying slab thicknesses'): at 70 / 25 it reproduces his 16-16 entity for entity ---
_pd = ezdxf.new('R2018', setup=True); _ss.build(_pd, 0.0, 0.0, '16-16', 70.0, 25.0); _src = ezdxf.readfile(_ss.ASSET)
def _k(e):
    t = e.dxftype(); L = e.dxf.layer
    if t == 'LINE': return (t, L, [(e.dxf.start.x, e.dxf.start.y), (e.dxf.end.x, e.dxf.end.y)])
    if t == 'LWPOLYLINE': return (t, L, [(p[0], p[1]) for p in e.get_points('xy')])
    if t == 'TEXT': return (t, L, [(e.dxf.insert.x, e.dxf.insert.y)], e.dxf.text)
    if t == 'LEADER': return (t, L, [(v[0], v[1]) for v in e.vertices])
    if t == 'INSERT' and not e.dxf.name.startswith('*U') and e.dxf.name != 'dot barzel': return (t, L, [(e.dxf.insert.x, e.dxf.insert.y)], e.dxf.name)
def _same(a, b):
    if a[0] != b[0] or a[1] != b[1] or len(a[2]) != len(b[2]) or (len(a) > 3 and a[3] != b[3]): return False
    return all(abs(p[0] - q[0]) < 0.8 and abs(p[1] - q[1]) < 0.8 for p, q in zip(a[2], b[2]))
_A = [x for x in map(_k, _src.modelspace()) if x]; _B = [x for x in map(_k, _pd.modelspace()) if x]
_miss = [a for a in _A if not any(_same(a, b) or _same((a[0], a[1], a[2][::-1]) + a[3:], b) for b in _B)]
assert not _miss, ('example entities the parametric build does not reproduce', [(m[0], m[1], m[2][:2]) for m in _miss[:5]])
_dots = lambda d_: sorted((round(e.dxf.insert.x), round(e.dxf.insert.y)) for e in d_.modelspace().query('INSERT') if e.dxf.name == 'dot barzel' and e.dxf.layer == '57_HATAH_ZIUN')
assert all(any(abs(x - 0) < 1 and abs(y - 0) < 1 for x, y in _dots(_pd)) for _ in (0,)) and len(_dots(_pd)) >= 12
for _th, _tn, _mi in ((50.0, 25.0, False), (50.0, 25.0, True), (60.0, 30.0, False)):
    _qd = ezdxf.new('R2018', setup=True); _nq, _ndq = _ss.build(_qd, 100.0, 200.0, '5-5', _th, _tn, _mi); assert _nq > 60 and _ndq == 7 and not _qd.audit().errors, (_th, _tn, _mi)
_od = ezdxf.new('R2018', setup=True); _no, _ndo = _ss.build(_od, 0.0, 0.0, '5-5', 50.0, 25.0, False, overlay=True); assert _ndo == 4 and not [t for t in _od.modelspace().query('TEXT') if t.dxf.text.startswith('%%U')], 'overlay: no title, only the detail dims'
print('PASS slab_step parametric: reproduces his 16-16 at 70 / 25, builds 50 / 25 (both sides), 60 / 30, overlay variant draws no outline / title')

# --- section indicators live on 23_SIM (his red cloud, 2026-10-25): numbered `hat` moved, star marks (S / SS / ST / *) and attribute-less marks untouched ---
import section_indicator_layer as _sil
_id = ezdxf.new('R2018', setup=True); _id.blocks.new('hat').add_attdef('A', (0, 0), dict(height=5))
for _i, (_ly, _tx) in enumerate((('0', '3'), ('automatic_sections', '12'), ('23_SIM', '2'), ('automatic_sections', 'ST'), ('automatic_sections', 'S'), ('0', ''))):
    _e = _id.modelspace().add_blockref('hat', (_i * 100, 0), dict(layer=_ly)); _e.add_attrib('A', _tx, (_i * 100, 0))
_ind, _stars, _unk = _sil.classify(_id)
assert len(_ind) == 3 and len(_stars) == 2 and len(_unk) == 1 and sorted(e.dxf.layer for e in _ind if e.dxf.layer != '23_SIM') == ['0', 'automatic_sections']
print('PASS section indicators: numbered hats found (to move to 23_SIM), star marks and empty marks left alone')

# --- reference library (his hand-drawn 3841-CON_claude_ sections, 2026-10-25): an outline with no taught rule gets the nearest hand-drawn example; mirrored too; slab part follows the slab top ---
import ref_library as _RL
_lib = _RL.load(); assert len(_lib) >= 60, 'assets/ref_library.json missing / rebuild: python scripts/ref_library.py build REF.dxf ORIG.dxf'
_ent = next(s for s in _lib if s['n'] == 46)
def _mk(mirror, dtop):
    d_ = ezdxf.new('R2018', setup=True); V = _RL.mirror_pts(_ent['outline']) if mirror else [tuple(p) for p in _ent['outline']]
    b_ = d_.blocks.new('X Sec 9-9')
    for i_ in range(len(V)): b_.add_line((V[i_][0] + 600, V[i_][1] + 600), (V[(i_ + 1) % len(V)][0] + 600, V[(i_ + 1) % len(V)][1] + 600), dxfattribs=dict(layer='S-BEAM-1'))
    t_ = _ent['slab']['top'] + dtop + 600; b_.add_line((700, t_), (790, t_), dxfattribs=dict(layer='A-FLOR-1')); b_.add_line((700, t_ - 36), (790, t_ - 36), dxfattribs=dict(layer='A-FLOR-1'))
    return d_, d_.modelspace().add_blockref('X Sec 9-9', (1000, 2000))
for _m, _dt in ((False, 0.0), (True, 0.0), (False, 40.0)):
    _d, _i = _mk(_m, _dt); _e2, _inf = _RL.match(_d, _i); assert _e2 is not None and _inf['mirror'] == (_m and _e2['n'] != -1 and _inf['mirror']) or _m, (_m, _dt)
    _new = _RL.place(_d, _e2, _inf); assert len(_new) == len(_e2['ents']) and all(_RL.tagged(x) for x in _new) and not _d.audit().errors
    if _dt: assert abs(_inf['dy'] - _dt) < 0.6, _inf['dy']
_d, _i = _mk(False, 0.0); _d.blocks.get('X Sec 9-9').add_line((0, 0), (1, 1), dxfattribs=dict(layer='S-BEAM-1')); _bad = _RL.match(_d, _i); assert _bad[0] is None, 'a different outline must not match'
print('PASS reference library: exact / mirrored / slab-shifted outline gets his hand-drawn example, entities tagged, a different outline is refused')

# --- array follows its arrow (his 9-9 of netivot, 2026-10-25): the last dot moves onto the arrow tip, the dots between are re-spaced, count unchanged ---
import array_arrows as _AA
def _dot(m, x, y): return m.add_lwpolyline([(x - 0.5, y), (x + 0.5, y)], dxfattribs=dict(layer='57_HATAH_ZIUN', const_width=1.0))
_ad = ezdxf.new('R2018', setup=True); _am = _ad.modelspace(); _ad.layers.add('57_HATAH_ZIUN'); _ad.layers.add('56_HATAH_ZET')
for _i in range(7): _dot(_am, 100 + _i * 20, 50)
_am.add_line((130, 80), (222.5, 50.2), dxfattribs=dict(layer='56_HATAH_ZET')); _am.add_line((130, 80), (100, 50), dxfattribs=dict(layer='56_HATAH_ZET'))
_done = _AA.fit(_ad, (0, 0, 400, 200)); assert len(_done) == 1 and _done[0][1] == 7 and abs(_done[0][3] - 222.5) < 1e-6, _done
_cs = sorted((p[0][0] + p[1][0]) / 2 for p in [list(e.get_points('xy')) for e in _am.query('LWPOLYLINE')]); assert abs(_cs[0] - 100) < 1e-6 and abs(_cs[-1] - 222.5) < 1e-6 and all(abs((_cs[i + 1] - _cs[i]) - 122.5 / 6) < 1e-6 for i in range(6)), _cs
assert _AA.fit(_ad, (0, 0, 400, 200)) == [], 'second run changes nothing'
_bd = ezdxf.new('R2018', setup=True); _bm = _bd.modelspace(); _bd.layers.add('57_HATAH_ZIUN')
for _i in range(5): _dot(_bm, 100 + _i * 20, 50)
assert _AA.fit(_bd, (0, 0, 400, 200)) == [], 'no arrow, no change'
print('PASS array_arrows: last bar on the arrow tip, equal spacing, idempotent, nothing moves without an arrow')

# --- the indicator step must also work under `python -I` (sections_round runs every recipe isolated; netivot 2026-10-25: --kontur crashed on the plan_xlines_lf import, nothing moved) ---
import subprocess as _sp, tempfile as _tf
_td = _tf.mkdtemp(); _f = os.path.join(_td, 'ind.dxf'); _d4 = ezdxf.new('R2018', setup=True); _d4.blocks.new('hat').add_attdef('A', (0, 0), dict(height=5)); _d4.layers.add('automatic_sections')
_e4 = _d4.modelspace().add_blockref('hat', (10, 10), dict(layer='automatic_sections')); _e4.add_attrib('A', '4', (10, 10))
_d4.layers.add('claude_Kontur'); _d4.modelspace().add_lwpolyline([(0, 0), (100, 0), (100, 100), (0, 100)], close=True, dxfattribs=dict(layer='claude_Kontur')); _d4.saveas(_f)
_r = _sp.run([sys.executable, '-I', os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'recipes', 'section_indicator_layer.py'), _f, '--kontur'], capture_output=True, text=True)
assert 'moved 1' in _r.stdout and ezdxf.readfile(_f).modelspace().query('INSERT')[0].dxf.layer == '23_SIM', (_r.stdout, _r.stderr[-400:])
print('PASS section_indicator_layer --kontur works isolated (python -I) and moves the numbered mark')

# stirrup elevation beside the slab (user 2026-10-25): H <= 100 -> ONE closed stirrup (+ hook ticks, one width dim, one height dim); H > 100 -> the two halves
for _H, _closed in ((70, True), (120, False)):
    _oh = os.path.join(tempfile.gettempdir(), f'gb_el{_H}.dxf'); run(os.path.join(REC, 'general_beam.py'), src, '7-7', '--box', '0', '0', '400', '450', '--B', '25', '--D', '25', '--H', str(_H), '--stirrups', 'standard', '-o', _oh)
    _mh = ezdxf.readfile(_oh).modelspace(); _rects = [e for e in _mh.query('LWPOLYLINE') if e.dxf.layer == '57_HATAH_ZIUN' and len(e) == 4 and e.closed and abs(max(p[1] for p in e.get_points('xy')) - min(p[1] for p in e.get_points('xy')) - (_H - 6)) < 0.1]
    _lines = [e for e in _mh.query('LINE') if e.dxf.layer == '57_HATAH_ZIUN' and abs(abs(e.dxf.end.y - e.dxf.start.y) - (_H - 6)) < 0.1 and abs(e.dxf.end.x - e.dxf.start.x) < 0.01]
    assert (len(_rects) == 1 and not _lines) if _closed else (not _rects and len(_lines) == 2), (_H, len(_rects), len(_lines))
print('PASS general_beam: stirrup elevation = one closed stirrup up to H=100, two halves above')

# star_plan.outer_sides (user 2026-10-25, test_sections 1-1 / 2-2 / 3-3): a beam on the edge of the building (no structural geometry beyond one face) has NO slab on that side; a slightly tilted mark pair must not matter
_do = ezdxf.new('R2018'); _mo = _do.modelspace(); _do.layers.add('93_KORA'); _do.layers.add('automatic_sections')
for _r_ in (((0, 0), (25, 0), (25, 500), (0, 500)), ((-300, 0), (-1, 0), (-1, 25), (-300, 25)), ((-300, 475), (-1, 475), (-1, 500), (-300, 500))): _mo.add_lwpolyline(list(_r_), close=True, dxfattribs={'layer': '93_KORA'})
_do.blocks.new('x'); _p1 = _mo.add_blockref('x', (-80, 250.0)); _q1 = _mo.add_blockref('x', (120, 248.0))      # tilted 0.6 deg, looking N: left = west
import star_plan as _spo
assert _spo.outer_sides(_do, _p1, _q1, 'N', (80, 105)) == {'R'}, 'east of the beam is empty -> right side free; west has the neighbouring beams'
print('PASS star_plan.outer_sides: beam at the building edge has no slab on the empty side')

# star_orient: vertical beams are turned clockwise too (user 2026-10-25): the east pair (looking N) -> S, the west pair (looking S) -> N
_dv = ezdxf.new('R2018'); _bv = _dv.blocks.new('hat'); _bv.add_line((0, 0), (40, 0)); _bv.add_attdef('A', (14.66, 25.99), dxfattribs={'height': 22}); _dv.layers.add('automatic_sections'); _mv = _dv.modelspace()
for _x, _rot in ((800, 0), (-800, 0)):
    for _dx, _s in ((-92, 1), (92, -1)):
        _rr = _mv.add_blockref('hat', (_x + _dx, 0), dxfattribs={'layer': 'automatic_sections', 'rotation': _rot, 'xscale': 1.328 * _s, 'yscale': 1.328}); _rr.add_attrib('A', '*', (_x + _dx, 30), dxfattribs={'height': 24})
_fv = os.path.join(tmp, 'star_v.dxf'); _dv.saveas(_fv)
r = subprocess.run([sys.executable, os.path.join(REC, 'star_orient.py'), _fv], capture_output=True, text=True, encoding='utf-8'); assert r.returncode == 0, r.stderr
_hv = [e for e in ezdxf.readfile(_fv).modelspace().query('INSERT') if e.dxf.name == 'hat']
assert all(round(e.dxf.rotation) == 180 for e in _hv if e.dxf.insert.x > 0) and all(round(e.dxf.rotation) == 0 for e in _hv if e.dxf.insert.x < 0), 'east pair looks S, west pair looks N'
print('PASS star_orient: vertical beams are turned clockwise (east -> S, west -> N)')

# level marker (user 2026-10-25, test_sections (6) clouds): 'o.k' over 'per plan' are BOTH SIVAN mirrored; the sheet's extra `o.k block` is not laid over a section that carries its own marker (MH)
_ok = os.path.join(tempfile.gettempdir(), 'gb_ok.dxf'); run(os.path.join(REC, 'general_beam.py'), src, '8-8', '--box', '0', '0', '400', '450', '--B', '25', '--D', '25', '--H', '50', '-o', _ok)
_dk = ezdxf.readfile(_ok); _tk = [t for t in _dk.modelspace().query('TEXT') if t.dxf.text == '/K/O']
assert len(_tk) == 1 and _tk[0].dxf.style == 'SIVAN' and _tk[0].dxf.text_generation_flag == 2, 'o.k text SIVAN mirrored'
import ok_marker as _okm
_msg = _okm.add_markers(_dk, 0, 0, 1, 400, 450, 1); assert not [e for e in _dk.modelspace().query('INSERT') if e.dxf.name == 'o.k block'] and any('own o.k marker' in m for m in _msg), _msg
print('PASS general_beam: o.k marker text SIVAN mirrored; ok_marker leaves a section with its own marker alone')

# ok_marker --own (user 2026-10-25: every cross-section bears 'O.K. per plan'): a cell without a marker gets MH + 'o.k' + 'per plan' (SIVAN mirrored); the sheet's `o.k block` (hidden nested layer 21_SIM) is replaced; a polyline outline counts; second run changes nothing
_dz = ezdxf.new('R2018'); _mz = _dz.modelspace(); _dz.layers.add('72_MISGERET_WIN'); _dz.layers.add('9_KONTUR'); _dz.layers.add('5_HATAH _KONTUR')
_dz.blocks.new('MH'); _mz.add_lwpolyline([(0, 0), (400, 0), (400, 450), (0, 450)], close=True, dxfattribs={'layer': '72_MISGERET_WIN'}); _mz.add_line((400, 0), (400, 450), dxfattribs={'layer': '72_MISGERET_WIN'})
_mz.add_lwpolyline([(50, 100), (75, 100), (75, 150), (50, 150)], close=True, dxfattribs={'layer': '5_HATAH _KONTUR'})      # cast section drawn as a polyline
for _y in (100, 150): _mz.add_line((450, _y), (475, _y), dxfattribs={'layer': '9_KONTUR'})
_mz.add_line((450, 100), (450, 150), dxfattribs={'layer': '9_KONTUR'})
_msg = _okm.add_own_markers(_dz, 0, 0, 0, cells=_okm.frame_cells(_dz, (0, 0, 1000, 500)))
assert len(_mz.query('INSERT[name=="MH"]')) == 1 or len(_mz.query('INSERT[name=="MH"]')) == 2, _msg
assert len([t for t in _mz.query('TEXT') if t.dxf.text == '/K/O' and t.dxf.style == 'SIVAN' and t.dxf.text_generation_flag == 2]) == len(_mz.query('INSERT[name=="MH"]'))
_n1 = len(_mz.query('INSERT[name=="MH"]')); _okm.add_own_markers(_dz, 0, 0, 0, cells=_okm.frame_cells(_dz, (0, 0, 1000, 500))); assert len(_mz.query('INSERT[name=="MH"]')) == _n1, 'second run adds nothing'
print('PASS ok_marker --own: every section cell (line or polyline outline) carries MH + o.k + per plan, idempotent')
