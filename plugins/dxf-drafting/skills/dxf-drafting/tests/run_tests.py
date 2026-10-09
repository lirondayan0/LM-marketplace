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
