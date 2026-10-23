"""Regression tests for the XREF-section recipes (2026-10-23): python tests/test_xref.py"""
import os, sys, tempfile
HERE = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, os.path.join(HERE, '..', 'recipes')); sys.path.insert(0, os.path.join(HERE, '..', 'scripts'))
import ezdxf
import xref_extend_bars as EB, xref_text_clear as TC

def build(path):
    d = ezdxf.new('R2010'); m = d.modelspace()
    b = d.blocks.new('X Sec 1-1')
    for a, c in [((0, 0), (110, 0)), ((110, 0), (110, 100)), ((110, 100), (0, 100)), ((0, 100), (0, 0))]: b.add_line(a, c, dxfattribs={'layer': 'S-BEAM-1'})
    for a, c in [((-75, 100), (0, 100)), ((-75, 65), (0, 65)), ((110, 100), (185, 100)), ((110, 65), (185, 65))]: b.add_line(a, c, dxfattribs={'layer': 'A-FLOR-1'})
    b.add_text('+26.40', height=6, dxfattribs={'layer': 'G-ANNO-DIMS-1', 'insert': (42, 139)})   # XREF level marker under the host note
    m.add_blockref('X Sec 1-1', (0, 0))
    if 'SIVAN' not in d.styles: d.styles.new('SIVAN', dxfattribs={'font': 'txt.shx'})
    for l in ('57_HATAH_ZIUN', '51_HATAH_DASHED', '54_HATAH_TEXT', '56_HATAH_ZET'):
        if l not in d.layers: d.layers.add(l)
    m.add_lwpolyline([(-15, 99), (-60, 99)], dxfattribs={'layer': '57_HATAH_ZIUN'})      # left top bar, 15 short of the slab end -75
    m.add_lwpolyline([(125, 99), (170, 99)], dxfattribs={'layer': '57_HATAH_ZIUN'})      # right top bar, 15 short of 185
    for x in (-14.3, -34.3, -54.3): m.add_lwpolyline([(x, 98), (x + 1, 98)], dxfattribs={'layer': '57_HATAH_ZIUN', 'const_width': 1})
    for x in (123.3, 143.3, 163.3): m.add_lwpolyline([(x, 98), (x + 1, 98)], dxfattribs={'layer': '57_HATAH_ZIUN', 'const_width': 1})
    d.saveas(path)

p = os.path.join(tempfile.gettempdir(), 'xref_t.dxf'); build(p)
assert EB.run(p) == 2 and EB.run(p) == 0, 'bars go to the XREF slab end; idempotent'
bars = [e for e in ezdxf.readfile(p).modelspace().query('LWPOLYLINE') if len(e) == 2 and abs(e[0][0] - e[1][0]) > 20]
assert sorted(round(min(e[0][0], e[1][0])) for e in bars) == [-75, 125] or sorted(round(max(e[0][0], e[1][0])) for e in bars) == [-15, 185], 'both bars reach -75 / 185'
print('PASS xref_extend_bars: slab bars reach the XREF slab end, idempotent')
import subprocess; subprocess.run([sys.executable, os.path.join(HERE, '..', 'recipes', 'xref_extend_dots.py'), p, 'apply'], capture_output=True, check=True)
xs = sorted(min(e[0][0], e[1][0]) for e in ezdxf.readfile(p).modelspace().query('LWPOLYLINE') if len(e) == 2 and abs(e[0][0] - e[1][0]) < 1.5)
assert abs(xs[0] + 74.3) < 0.1 and abs(xs[-1] + 1 - 184.3) < 0.1 and len(xs) == 8, ('dot rows must continue to 0.7 from the slab end', xs)
print('PASS xref_extend_dots: dot rows continue at the same spacing to 0.7 from the slab end')
# leader never cut: a note whose polyline shelf has its joint at the LAST point is moved with its forks
d = ezdxf.readfile(p); m = d.modelspace()
m.add_text('X', dxfattribs={'layer': '54_HATAH_TEXT', 'style': 'SIVAN', 'height': 6, 'insert': (50, 140)})
m.add_lwpolyline([(40, 138), (90, 138)], dxfattribs={'layer': '56_HATAH_ZET'}); m.add_line((90, 138), (60, 101), dxfattribs={'layer': '56_HATAH_ZET'})
d.saveas(p)
import math
assert TC.run(p, dry=False) >= 1, 'the note sits on the XREF level marker and must move'
z = [e for e in ezdxf.readfile(p).modelspace() if e.dxf.layer == '56_HATAH_ZET']
pl = [e for e in z if e.dxftype() == 'LWPOLYLINE'][0]; ln = [e for e in z if e.dxftype() == 'LINE'][0]
assert abs(pl[1][0] - ln.dxf.start.x) < 0.05 and abs(pl[1][1] - ln.dxf.start.y) < 0.05, 'leader stays connected'
print('PASS xref_text_clear: leader joint at the polyline end stays connected')
# wall above a beam (his hand-drawn Sec 9): 11 dot rows from 4.6 below the beam top to 4.2 below the wall top, columns 4.2 inside the faces
import xref_wall as XW
cols, rows = XW.wall_dots(-25452.0, -25432.1, 119614.8, 119774.8)
assert len(rows) == 11 and abs(rows[0] - 119610.2) < 0.05 and abs(rows[-1] - 119770.6) < 0.05 and abs(cols[0] + 25447.8) < 0.05 and abs(cols[1] + 25436.3) < 0.05, (len(rows), rows[0], rows[-1], cols)
print('PASS xref_wall: dot rows / columns reproduce his Sec 9 wall')
