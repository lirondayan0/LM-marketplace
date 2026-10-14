"""plan_restyle.py FILE OUT [--from-layer L] [--layer L2 --style S]  -  move MY tagged dims (xdata CLAUDE_ROWS 'xline_dims') to the layer/style of the user's NEW sample dimension, keeping every text position.
Default target = plan_xlines_lf.dim_template(ms) (sample dim in a cloud on claude_DIM / claude outside the plan); default --from-layer = the layer holding most of my tagged dims that differs from the target.
Technique (DIM.dxf 2026-10-14, 602 dims): set layer+dimstyle, then DimStyleOverride.set_location(old_text_midpoint, leader=False, relative=False) BEFORE render() - plain render() resets all texts (602 moved). Run plan_repair.py after (text collisions), write in place only after a snapshot + mtime check."""
import sys, os, argparse, collections
R_ = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, R_); sys.path.insert(0, os.path.join(R_, '..', 'scripts'))
import ezdxf
from ezdxf.entities import DimStyleOverride
ap = argparse.ArgumentParser(); ap.add_argument('src'); ap.add_argument('dst'); ap.add_argument('--from-layer'); ap.add_argument('--layer'); ap.add_argument('--style')
a = ap.parse_args(); doc = ezdxf.readfile(a.src); ms = doc.modelspace()
own = lambda d: d.has_xdata('CLAUDE_ROWS') and any(t.value == 'xline_dims' for t in d.get_xdata('CLAUDE_ROWS'))
if not (a.layer and a.style):
    import plan_xlines_lf as lf
    t = lf.dim_template(ms); a.layer, a.style = a.layer or t[0], a.style or t[1]
mine = [d for d in ms.query('DIMENSION') if own(d)]
src = a.from_layer or collections.Counter(d.dxf.layer for d in mine if (d.dxf.layer, d.dxf.dimstyle) != (a.layer, a.style)).most_common(1)[0][0]
n = 0
for d in mine:
    if d.dxf.layer != src: continue
    t0 = d.dxf.text_midpoint; d.dxf.layer = a.layer; d.dxf.dimstyle = a.style
    o = DimStyleOverride(d); o.set_location(t0, leader=False, relative=False); o.render(); n += 1
print('restyled', n, 'dims from', src, 'to', a.layer, a.style); doc.saveas(a.dst)
