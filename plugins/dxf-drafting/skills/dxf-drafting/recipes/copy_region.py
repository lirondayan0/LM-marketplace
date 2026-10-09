"""Recipe: copy a finished drawing (everything inside a box) to another place, optionally renumbering its title. For the user's GENERAL sections (section 5 = wall + slab detail
for elevator shafts and stairwells) that are not redrawn per plan but reused as they are.
  python copy_region.py FILE --box X0 Y0 X1 Y1 --to X0' Y0' [--retitle OLD NEW] [--cell-layer 72_MISGERET_WIN] [--dry] [-o OUT]
Copies every entity whose bounding-box centre lies in the box (not the white-cell lines / user markup); `--general N` uses the box of the user's general section N from the profile (`general_sections`), translated by (X0' - X0, Y0' - Y0). Dimensions are re-rendered at the new place
(their geometry block is shared, so a plain translate would leave the picture behind). `--retitle 5-5 6-6` rewrites section titles. Writes a timestamped snapshot first."""
import argparse, os, sys
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'scripts'))
from dxflib import *
from ezdxf.entities import DimStyleOverride

def main():
    ap = argparse.ArgumentParser(); ap.add_argument('file'); ap.add_argument('--box', nargs=4, type=float); ap.add_argument('--general', help="N: take the box (and title) of the user's general section N from the profile"); ap.add_argument('--profile', default='israeli-structural'); ap.add_argument('--to', nargs=2, type=float, required=True)
    ap.add_argument('--retitle', nargs=2); ap.add_argument('--skip-layers', default='72_MISGERET_WIN,SHINUIM-TIKUNIM'); ap.add_argument('-o'); ap.add_argument('--dry', action='store_true')
    a = ap.parse_args()
    if a.general:
        g = load_profile(a.profile)['general_sections'][a.general]; a.box = a.box or g['box']; a.retitle = a.retitle or None
        print('general section', g['title'], '-', g['what'])
    if not a.box: sys.exit('give --box or --general N')
    skip = set(a.skip_layers.split(',')); doc = ezdxf.readfile(a.file); msp = doc.modelspace(); x0, y0, x1, y1 = a.box
    dx, dy = a.to[0] - x0, a.to[1] - y0; todo = []
    for e in list(msp):
        if e.dxf.layer in skip: continue
        try: b = bbox.extents([e])
        except Exception: continue
        if b.has_data and x0 < b.center.x < x1 and y0 < b.center.y < y1: todo.append(e)
    print(f'{len(todo)} entities in the box, copy by ({dx:.1f}, {dy:.1f})')
    if a.dry: return
    out = a.o or a.file
    if out == a.file: backup(a.file, 'copy')
    n = 0
    for e in todo:
        c = e.copy(); msp.add_entity(c); c.translate(dx, dy, 0)
        if c.dxftype() == 'DIMENSION':
            try: DimStyleOverride(c).render()
            except Exception as ex: print('  dimension not re-rendered:', ex)
        elif c.dxftype() == 'TEXT' and a.retitle and a.retitle[0] in c.dxf.text: c.dxf.text = c.dxf.text.replace(a.retitle[0], a.retitle[1])
        n += 1
    doc.saveas(out); print('copied', n, 'entities; saved', out, '| audit errors', len(ezdxf.readfile(out).audit().errors))

if __name__ == '__main__': main()
