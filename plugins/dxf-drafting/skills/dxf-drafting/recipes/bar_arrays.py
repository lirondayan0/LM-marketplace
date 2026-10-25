#!/usr/bin/env python
"""Turn the bar dots of section sheets into AutoCAD ASSOCIATIVE ARRAYS (user 2026-10-21: "set up as an array so any engineer can determine and adjust the amount of
reinforcement"; his example = a row of 7 dots, one ARRAYRECT: Items 7, ItemSpacing, Rows 1).

A bar dot = closed 2-vertex polyline, const width 1, on 57_HATAH_ZIUN. Per sheet box:
  1. runs of >= 3 dots with equal step on one y (horizontal) / one x (vertical)  -> 1 array each
  2. what is left, same y, taken two by two (the beam pair, the slab pair)         -> 2-item arrays; odd / unpaired dots stay loose (reported)
  3. a script for accoreconsole (AutoCAD core console, headless) deletes the other dots of each run and ARRAYRECTs the first one (source = left / lowest dot),
     CLAYER = 57_HATAH_ZIUN first (the array INSERT takes the CURRENT layer), DXFOUT writes the result.
  4. verified by the array bodies in the output (+N), dot centres of the original = of the result (virtual explode), every other entity count unchanged.
ARRAYRECT in AutoCAD 2024: _COL n TOTAL-distance (first to last), _R rows DISTANCE-BETWEEN-rows elevation (inconsistent, found by test); COUnt / Spacing prompt order is rows first.
Needs AutoCAD (accoreconsole.exe); the user's open AutoCAD session is not touched. Run it from Python (subprocess), NOT from git-bash: MSYS rewrites the '/i' '/s' switches and the console hangs.

    python bar_arrays.py FILE --box X0 Y0 X1 Y1 [--dry] [--accore PATH]
Snapshot FILE.bak-arrays-HHMMSS, then FILE is replaced by the AutoCAD-saved DXF (same version, everything else identical; checked on the Ramla sheet).
"""
import argparse, glob, json, math, os, shutil, subprocess, sys, tempfile, time
from collections import Counter, defaultdict
import ezdxf

LAYER = '57_HATAH_ZIUN'


def find_accore():
    c = sorted(glob.glob(r'C:\Program Files\Autodesk\AutoCAD *\accoreconsole.exe'))
    if not c: sys.exit('accoreconsole.exe not found (AutoCAD needed)')
    return c[-1]


def dots_in(doc, box):
    x0, y0, x1, y1 = box; out = []
    for e in doc.modelspace().query('LWPOLYLINE'):
        if e.dxf.layer == LAYER and len(e) == 2 and 0.5 <= e.dxf.get('const_width', 0) <= 3.0:      # any bar diameter (Ramla dots 1.0, brenda_karka dots 1.25): chord ~ width
            p = [(a, b) for a, b, *_ in e.get_points()]
            if abs(p[0][1] - p[1][1]) < 1e-6 and abs(abs(p[0][0] - p[1][0]) - e.dxf.const_width) < 0.35 and x0 <= p[0][0] <= x1 and y0 <= p[0][1] <= y1:
                out.append((e.dxf.handle, (p[0][0] + p[1][0]) / 2, p[0][1]))
    for e in doc.modelspace().query('INSERT'):      # his block dots ('dot barzel' on the rebar layer: free-edge shutter column, slab step rows) are bar dots too (2026-10-25: they stayed loose in the round)
        if e.dxf.layer == LAYER and e.dxf.name == 'dot barzel' and x0 <= e.dxf.insert.x <= x1 and y0 <= e.dxf.insert.y <= y1: out.append((e.dxf.handle, e.dxf.insert.x, e.dxf.insert.y))
    return out


def runs(items, same, pos, tol=0.35):
    g = defaultdict(list)
    for it in items: g[round(same(it) / 0.5)].append(it)
    ks = sorted(g); groups = []; cur = []
    for k in ks:
        if cur and k - cur[-1] > 1: groups.append(cur); cur = []
        cur.append(k)
    if cur: groups.append(cur)
    out, left = [], []
    for grp in groups:
        its = sorted((i for k in grp for i in g[k]), key=pos); i = 0
        while i < len(its):
            best = None
            for j in range(i + 1, len(its)):
                st = pos(its[j]) - pos(its[i])
                if st < 2: continue
                run = [its[i], its[j]]; nxt = pos(its[j]) + st
                for k in range(j + 1, len(its)):
                    if abs(pos(its[k]) - nxt) < tol: run.append(its[k]); nxt += st
                    elif pos(its[k]) > nxt + tol: break
                if len(run) >= 3: best = run
                break
            if best:
                ids = {x[0] for x in best}; out.append(best); its = [x for x in its if x[0] not in ids]
            else: left.append(its[i]); i += 1
    return out, left


def plan_arrays(dots):
    """-> ([(dir 'H'|'V', source handle, n, total length, [other handles])], [loose handles])"""
    H, left = runs(dots, lambda t: t[2], lambda t: t[1]); V, left = runs(left, lambda t: t[1], lambda t: t[2])
    arr = []
    for r in H:
        P = sorted(r, key=lambda t: t[1]); arr.append(('H', P[0][0], len(P), P[-1][1] - P[0][1], [q[0] for q in P[1:]]))
    for r in V:
        P = sorted(r, key=lambda t: t[2]); arr.append(('V', P[0][0], len(P), P[-1][2] - P[0][2], [q[0] for q in P[1:]]))
    g = defaultdict(list)
    for h, x, y in left: g[(int((x - 94660) // 400), round(y))].append((x, y, h))     # one section cell = 400 wide
    rest = []
    for v in g.values():
        v.sort()
        for i in range(0, len(v) - 1, 2):
            if v[i + 1][0] - v[i][0] >= 5: arr.append(('H', v[i][2], 2, v[i + 1][0] - v[i][0], [v[i + 1][2]]))
            else: rest += [v[i], v[i + 1]]
        if len(v) % 2: rest.append(v[-1])
    gv = defaultdict(list)
    for x, y, h in rest: gv[(int((x - 94660) // 400), round(x))].append((y, h))
    loose = []
    for v in gv.values():
        v.sort()
        if len(v) == 2 and v[1][0] - v[0][0] >= 5: arr.append(('V', v[0][1], 2, v[1][0] - v[0][0], [v[1][1]]))
        else: loose += [h for _, h in v]
    return arr, loose


def script(arr, out_dxf, log):
    # a FROZEN / off layer cannot become current: CLAYER silently fails and the arrays land on the previous layer (netivot 2026-10-24: claude_Kontur) -> thaw first, then PROVE it
    L = ['(setvar "FILEDIA" 0)', '(setvar "CMDECHO" 0)', '(setvar "ARRAYASSOC" 1)', '(command "_.-LAYER" "_T" "%s" "_ON" "%s" "_U" "%s" "")' % (LAYER, LAYER, LAYER),
         '(setvar "CLAYER" "%s")' % LAYER, '(setq f (open "%s" "w"))' % log,
         '(write-line (strcat "CLAYER " (if (= (strcase (getvar "CLAYER")) "%s") "ok" (strcat "FAILED, current layer is " (getvar "CLAYER")))) f)' % LAYER]
    for k, h, n, tot, others in arr:
        L += ['(entdel (handent "%s"))' % o for o in others]
        a = '"_COL" %d %.4f "_R" 1 1.0 0.0' % (n, tot) if k == 'H' else '"_COL" 1 1.0 "_R" %d %.4f 0.0' % (n, tot / (n - 1))
        L.append('(setq r (vl-catch-all-apply \'vl-cmdf (list "_.ARRAYRECT" (handent "%s") "" "_AS" "_Yes" %s "_X")))' % (h, a))
        L.append('(write-line (strcat "%s " (if (vl-catch-all-error-p r) (vl-catch-all-error-message r) "ok")) f)' % h)
    return '\n'.join(L + ['(close f)', '(command "_.DXFOUT" "%s" "")' % out_dxf, 'QUIT', 'Y']) + '\n'


def centres(doc, box):
    out = []
    def walk(ents):
        for e in ents:
            if e.dxftype() == 'LWPOLYLINE' and len(e) == 2 and 0.5 <= e.dxf.get('const_width', 0) <= 3.0:
                p = [(a, b) for a, b, *_ in e.get_points()]
                if abs(p[0][1] - p[1][1]) < 1e-6 and abs(abs(p[0][0] - p[1][0]) - e.dxf.const_width) < 0.35: out.append(((p[0][0] + p[1][0]) / 2, p[0][1]))
            elif e.dxftype() == 'INSERT' and e.dxf.name == 'dot barzel': out.append((e.dxf.insert.x, e.dxf.insert.y))
            elif e.dxftype() == 'INSERT': walk(e.virtual_entities())
    walk([e for e in doc.modelspace() if e.dxf.layer == LAYER and e.dxftype() in ('LWPOLYLINE', 'INSERT')])
    return [c for c in out if box[0] <= c[0] <= box[2] and box[1] <= c[1] <= box[3]]


def same_dots(A, B, tol=0.3):
    """Every dot of A has exactly one partner within tol in B (array spacing = mean step, so up to ~0.1 of drift)."""
    if len(A) != len(B): return False
    grid = defaultdict(list)
    for q in B: grid[(round(q[0]), round(q[1]))].append(q)
    for p in A:
        c = [q for dx in (-1, 0, 1) for dy in (-1, 0, 1) for q in grid[(round(p[0]) + dx, round(p[1]) + dy)] if abs(q[0] - p[0]) < tol and abs(q[1] - p[1]) < tol]
        if not c: return False
        grid[(round(c[0][0]), round(c[0][1]))].remove(c[0])
    return True


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('file'); ap.add_argument('--box', nargs=4, type=float, required=True); ap.add_argument('--dry', action='store_true'); ap.add_argument('--accore')
    a = ap.parse_args(); doc = ezdxf.readfile(a.file)
    arr, loose = plan_arrays(dots_in(doc, a.box))
    print(f'{len(arr)} arrays ({sum(1 for x in arr if x[0] == "H")} horizontal, {sum(1 for x in arr if x[0] == "V")} vertical), {len(loose)} dots stay loose')
    if a.dry or not arr: return
    tmp = tempfile.mkdtemp(prefix='arr', dir='C:\\' if os.name == 'nt' else None)       # short ASCII path: the console dislikes long / Hebrew ones
    work, out, log, scr = (os.path.join(tmp, n) for n in ('work.dxf', 'final.dxf', 'res.txt', 'run.scr'))
    shutil.copy2(a.file, work)
    open(scr, 'w').write(script(arr, out.replace('\\', '/'), log.replace('\\', '/')))
    subprocess.run([a.accore or find_accore(), '/i', work, '/s', scr, '/l', 'en-US'], stdout=subprocess.DEVNULL, timeout=900)
    bad = [l for l in open(log) if not l.strip().endswith(' ok')] if os.path.exists(log) else ['no log']
    if bad or not os.path.exists(out): sys.exit('AutoCAD run failed: %s' % bad[:3])
    new = ezdxf.readfile(out); nb = lambda d: sum(1 for x in d.objects if x.dxftype() == 'ACDBASSOCARRAYACTIONBODY')
    ca = Counter((e.dxftype(), e.dxf.layer) for e in doc.modelspace()); cb = Counter((e.dxftype(), e.dxf.layer) for e in new.modelspace())
    diff = {k for k in set(ca) | set(cb) if ca[k] != cb[k]}
    ni = lambda d: sum(1 for e in d.modelspace().query('INSERT') if e.dxf.name.startswith('*U') and e.dxf.layer == LAYER)    # INSERTs, not bodies: deleted arrays leave orphan bodies
    assert ni(new) - ni(doc) == len(arr), 'array count'
    assert not new.layers.get(LAYER).is_frozen() and new.layers.get(LAYER).is_on(), f'{LAYER} is hidden in the result'
    assert diff <= {('LWPOLYLINE', LAYER), ('INSERT', LAYER)}, diff
    assert same_dots(centres(doc, a.box), centres(new, a.box)), 'dot positions changed'
    shutil.copy2(a.file, f'{a.file}.bak-arrays-{time.strftime("%H%M%S")}'); shutil.copy2(out, a.file)
    print('written; dot centres identical, other entities unchanged')


if __name__ == '__main__':
    main()
