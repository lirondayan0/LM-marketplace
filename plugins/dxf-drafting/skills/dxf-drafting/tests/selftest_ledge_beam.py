"""Reproduce ground-floor example 2-2 (beam 80x75, hollow-core 25 + topping 7, slabs both sides) with recipes/ledge_beam.build and compare the bar dots
with the ones measured on the user's example (beam-left coordinates). Run: python tests/selftest_ledge_beam.py"""
import os, sys
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'recipes'))
import importlib.util
spec = importlib.util.spec_from_file_location('lb', os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'recipes', 'ledge_beam.py'))
src = open(spec.origin, encoding='utf-8').read().replace("if __name__ == '__main__': main()", '')
ns = {'__file__': spec.origin}; exec(compile(src, spec.origin, 'exec'), ns)
g = ns['build'](80, 75, 25, 7, 'both')
exp = {(4.5, 4.5), (14.7, 4.5), (24.8, 4.5), (35.0, 4.5), (45.1, 4.5), (55.3, 4.5), (65.4, 4.5), (75.5, 4.5),
       (4.5, 21.4), (4.5, 38.3), (75.5, 21.4), (75.5, 38.3),
       (19.5, 38.5), (19.5, 54.5), (19.5, 70.4), (60.5, 38.5), (60.5, 54.5), (60.5, 70.4),
       (25.4, 70.4), (31.3, 70.4), (37.1, 70.4), (43.0, 70.4), (48.8, 70.4), (54.7, 70.4),
       (-33.8, 71), (-13.8, 71), (6.2, 71), (73.9, 71), (93.9, 71), (113.9, 71)}
got = set(g['dots']); miss = [e for e in exp if not any(abs(e[0]-q[0]) < .35 and abs(e[1]-q[1]) < .35 for q in got)]
extra = [q for q in got if not any(abs(e[0]-q[0]) < .35 and abs(e[1]-q[1]) < .35 for e in exp)]
print(f'example dots {len(exp)}, generated {len(got)}, missing {miss}, extra {extra}')
print('tall stirrups', [(round(a, 1), round(b, 1)) for a, b, c, d in g['tall']], '(example: 18..48 and 32..62, y 3..72)')
assert not miss and not extra, 'dots differ from example 2-2'
import ezdxf, tempfile
doc = ezdxf.new('R2018'); ns['add_dot'](doc.modelspace(), 10, 10, '0')
dot = list(doc.modelspace())[0]; assert dot.dxf.const_width == 1.0 and dot.closed, 'dots must be solid (const_width = diameter)'
print('PASS ledge_beam reproduces example 2-2 dots; dots are solid')
