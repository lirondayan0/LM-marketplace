"""ONE COMMAND for "create the cross-sections" (user 2026-10-21: "next time I ask for a section plan, do it on your own").
Runs the whole STANDING PROCEDURE (conventions/section-drawings.md) on the star markers inside claude_Kontur:
  1 orient the pairs clockwise (star_orient, pairs = file-adjacent hats, --max-y 1e9)
  2 plan (star_plan, read-only): every pair must get a section - a pair that is not drawn is a hard WARNING
  3 find FREE SPACE: to the RIGHT of the plan beyond any other plan copy, 1000 clear of everything (then left / below / above only if impossible)
  4 draw (star_plan --draw --cells-at): rows of 10, titles centred, marks renumbered
  5 finish passes on the new rows: Hebrew notes -> SIVAN, leader fit, layer colours (rebar ACI 4), 'OK per plan' marker ONCE on the sheet (second section)
  5b bar_arrays (AutoCAD accoreconsole): every bar row an associative array
  6 verify: reload + audit, count sections vs pairs, PNG of the rows, short report
  python sections_round.py FILE [--dry] [--side left|right|below|above] [--first N] [--no-kontur] [--png OUT.png]
--dry stops after step 3 (prints the plan and the chosen place). Snapshots are made by the recipes (.bak-*). Refuses to run if the file is locked (.dwl next to it) unless --force."""
import argparse, math, os, re, subprocess, sys
HERE = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, HERE); sys.path.insert(0, os.path.join(HERE, '..', 'scripts'))
import ezdxf
from ezdxf import bbox

ROW_W = 4000.0; ROW_H_GUESS = 560.0; GAP = 300.0; PER_ROW = 10; SKIP = ('XLINE', 'RAY')


def run(*args):
    r = subprocess.run([sys.executable, '-I', *map(str, args)], capture_output=True, text=True, encoding='utf-8', errors='replace', cwd=HERE)
    return '\n'.join(l for l in (r.stdout + r.stderr).splitlines() if 'copy process ignored' not in l)


def kontur_box(doc):
    from plan_xlines_lf import kontur_loops
    L = kontur_loops(doc.modelspace()); xs = [p[0] for l in L for p in l]; ys = [p[1] for l in L for p in l]
    return (min(xs), min(ys), max(xs), max(ys)) if xs else None


def boxes(doc):
    out = []
    for e in doc.modelspace():
        if e.dxftype() in SKIP: continue
        try: b = bbox.extents([e], fast=True)
        except Exception: continue
        if b.has_data and max(abs(b.extmin.x), abs(b.extmax.x), abs(b.extmin.y), abs(b.extmax.y)) < 5e6 and b.extmax.x - b.extmin.x < 60000: out.append((b.extmin.x, b.extmin.y, b.extmax.x, b.extmax.y))
    return out


def free(boxes_, x0, y0, x1, y1): return not any(b[0] < x1 and b[2] > x0 and b[1] < y1 and b[3] > y0 for b in boxes_)


def find_place(doc, rows, kb, side=None):
    """row origin (x, y of the first row's bottom-left) in empty space beside the plan. USER RULE 2026-10-21: the template goes to the RIGHT of the plan (beyond any other plan copy), ~1000 clear of every other
    entity, its top ~350 below the plan's top edge (his own placement of brenda_karka: x -81359, 995 right of the neighbouring plan, y 179931..180414 for a plan top of 180765). Left / below / above only when the right is impossible."""
    bs = boxes(doc); H = ROW_H_GUESS * rows; kx0, ky0, kx1, ky1 = kb; CLEAR = 1000.0
    cands = {'right': (kx1 + GAP, ky1 - 350 - H), 'left': (kx0 - GAP - ROW_W, ky1 - 350 - H), 'below': (kx0, ky0 - GAP - H), 'above': (kx0, ky1 + GAP)}
    for name in ([side] if side else ['right', 'left', 'below', 'above']):
        x, y = cands[name]
        for k in range(0, 80):                                  # slide away from the plan until the rectangle (+ clearance) is empty
            dx = {'left': -k * 250, 'right': k * 250}.get(name, 0); dy = {'below': -k * 250, 'above': k * 250}.get(name, 0)
            if free(bs, x + dx - CLEAR, y + dy - CLEAR, x + dx + ROW_W + CLEAR, y + dy + H + CLEAR): return x + dx, y + dy, name
    return None


def main():
    ap = argparse.ArgumentParser(); ap.add_argument('file'); ap.add_argument('--dry', action='store_true'); ap.add_argument('--side', choices=['left', 'right', 'below', 'above']); ap.add_argument('--first', type=int, default=1)
    ap.add_argument('--no-kontur', action='store_true', help='work on every unnumbered pair (only when the file has no claude_Kontur)'); ap.add_argument('--png'); ap.add_argument('--force', action='store_true'); a = ap.parse_args()
    f = os.path.abspath(a.file)
    if not a.force and (os.path.exists(f + '.dwl') or os.path.exists(os.path.splitext(f)[0] + '.dwl')): sys.exit('the file is open in CAD (.dwl): save + close it first (or --force)')
    doc = ezdxf.readfile(f); kb = kontur_box(doc); kont = [] if a.no_kontur else ['--kontur']
    if not kb and not a.no_kontur: sys.exit('no closed claude_Kontur: nothing is in scope (use --no-kontur only if the user wants every mark)')
    print('1 orient'); print(run(os.path.join(HERE, 'star_orient.py'), f, '--max-y', '1e9', '--tidy', 'W').strip().splitlines()[-2:])
    print('2 plan'); plan = run(os.path.join(HERE, 'star_plan.py'), f, *kont, '--max-y', '1e9', '--first', a.first); print(plan)
    if 'no unnumbered' in plan: sys.exit('nothing to do: no unnumbered S / SS / ST pairs inside claude_Kontur')
    nsec = len(re.findall(r'^section \d+-\d+:', plan, re.M)); undrawn = re.findall(r'^NOT DRAWN: (.*)$', plan, re.M)
    if undrawn: print('WARNING - pairs NOT drawn (read each cut by hand, the user wants every pair):', *undrawn, sep='\n  ')
    rows = max(1, math.ceil(nsec / PER_ROW)); doc = ezdxf.readfile(f); place = find_place(doc, rows, kb or (min(b[0] for b in boxes(doc)), min(b[1] for b in boxes(doc)), max(b[2] for b in boxes(doc)), max(b[3] for b in boxes(doc))), a.side)
    if not place: sys.exit('no free space found beside the plan: choose a place with the user')
    x, y, side = place; print(f'3 free space: {side} of the plan, rows at ({x:.0f}, {y:.0f}), {rows} row(s) for {nsec} section(s)')
    if a.dry: return
    print('4 draw'); print('\n'.join(run(os.path.join(HERE, 'star_plan.py'), f, *kont, '--max-y', '1e9', '--first', a.first, '--cells-at', x, y, '--draw').splitlines()[-14:]))
    doc = ezdxf.readfile(f); bs = [b for b in boxes(doc) if b[0] >= x - 50 and b[2] <= x + ROW_W + 50 and b[1] >= y - rows * 1500 and b[3] <= y + rows * 1500 + ROW_H_GUESS]
    box = (x - 50, min(b[1] for b in bs) - 20, ROW_W + 100, max(b[3] for b in bs) - min(b[1] for b in bs) + 40) if bs else (x - 50, y - 1500, ROW_W + 100, 3000 + ROW_H_GUESS)
    print('5 finish passes on', [round(v) for v in box])
    for rec in ('sivan_text.py', 'leader_fit.py', 'rebar_color.py'): print(' ', rec, run(os.path.join(HERE, rec), f, '--box', *box).strip().splitlines()[-1:])
    print('  mid_note_fit', run(os.path.join(HERE, 'mid_note_fit.py'), f, '--box', *box).strip().splitlines()[-2:])      # user 2026-10-22: the middle-steel note overlaps nothing
    # 'OK per plan' level marker (user 2026-10-21): the user's `o.k block` on EVERY section, from his reference marker in the file (or the block definition)
    print('  ok_marker', run(os.path.join(HERE, 'ok_marker.py'), f, '--cells', x, box[1], nsec, '--cell-h', box[3], '--once', 2 if nsec > 1 else 1).strip().splitlines()[-1:])
    # BAR ARRAYS (user 2026-10-21: the reinforcement of the sections is drawn as associative ARRAYS) - LAST write step: AutoCAD (accoreconsole) saves the file
    print('  align_row', run(os.path.join(HERE, 'align_row.py'), f, '--near', box[0] + 10, box[1] + 10).strip().splitlines()[:1])      # user 2026-10-22: all sections of a row hang from ONE title line
    print('  cell_dupes', run(os.path.join(HERE, 'cell_dupes.py'), f, '--fix').strip().splitlines()[-2:])                                    # user 2026-10-22: no doubled reinforcement
    print('  text_overlap', run(os.path.join(HERE, 'text_overlap.py'), f, '--fix').strip().splitlines()[-1:])                            # user 2026-10-22: no overlapping text
    import glob
    if glob.glob(r'C:\Program Files\Autodesk\AutoCAD *\accoreconsole.exe'): print('  bar_arrays', run(os.path.join(HERE, 'bar_arrays.py'), f, '--box', box[0], box[1], box[0] + box[2], box[1] + box[3]).strip().splitlines()[-2:])
    else: print('  bar_arrays NOT RUN: accoreconsole.exe not found - tell the user, the dots are loose')
    # COVERAGE (user 2026-10-21: a 380-apart pair was silently missed): every hat pair inside the kontur must be numbered, WARNINGs of the recipes must reach the report
    cov = ezdxf.readfile(f); hs = [e for e in cov.modelspace().query('INSERT') if e.dxf.name == 'hat' and e.dxf.layer.lower() == 'automatic_sections' and e.attribs]
    from ezdxf.math import is_point_in_polygon_2d, Vec2
    try:
        from plan_xlines_lf import kontur_loops; loops = kontur_loops(cov.modelspace())
    except Exception: loops = []
    inside = [h for h in hs if not loops or any(is_point_in_polygon_2d(Vec2(h.dxf.insert.x, h.dxf.insert.y), [Vec2(q[0], q[1]) for q in L]) >= 0 for L in loops)]
    unnum = [(round(h.dxf.insert.x), round(h.dxf.insert.y), h.attribs[0].dxf.text) for h in inside if not h.attribs[0].dxf.text.strip().isdigit()]
    print(f'  COVERAGE: {len(inside)} marks inside the kontur = {len(inside) // 2} pairs; unnumbered marks left: {unnum or 0}' + ('  <-- A PAIR WAS NOT DRAWN: pairing window / unreadable cut, fix before reporting' if unnum else ''))
    print('  CHECK the log above for WARNING lines (stirrup row beyond the table, section wider than its cell, pairs not drawn): they go into the report')
    d2 = ezdxf.readfile(f); aud = d2.audit(); print('6 verify: audit errors', len(aud.errors), '| numbered pairs left unnumbered:', len(re.findall(r'^NOT DRAWN', run(os.path.join(HERE, 'star_plan.py'), f, *kont, '--max-y', '1e9'), re.M)))
    png = a.png or os.path.join(os.path.dirname(f), 'sections_round_check.png')
    print(run(os.path.join(HERE, '..', 'scripts', 'dxf_inspect.py'), f, 'png', box[0], box[0] + box[2], box[1], box[1] + box[3], png).strip().splitlines()[-1:], 'render ->', png, '(READ IT: titles, notes in SIVAN, rebar light blue, nothing overlapping)')
    print('REPORT: per section beam / slab / stirrups as printed in step 2; UNVERIFIED = slab sides copied / beam level assumed (read the planner notes), H=40 for untagged beams, stirrup row beyond the table; bar_arrays run when AutoCAD is installed.')


if __name__ == '__main__': main()
