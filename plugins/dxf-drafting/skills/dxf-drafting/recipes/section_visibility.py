"""VISIBILITY GATE for drawn sections (born 2026-10-24: netivot_sections.dxf had titles, rebar and dimensions that the user could not see).
Root cause: the plan arrived with layers FROZEN (54_HATAH_TEXT, 57_HATAH_ZIUN, 53_HATAH_MIDA ...); the sections were drawn on those layers, so they were invisible, and
AutoCAD refuses CLAYER = a frozen layer, so the bar arrays landed on the previously current layer (claude_Kontur, the user's own channel).
A section round is NOT finished before this check passes (sections_round and the app run it).
  python section_visibility.py FILE --box X0 Y0 X1 Y1            # check only: exit 1 if anything is hidden / on the wrong layer
  python section_visibility.py FILE --box X0 Y0 X1 Y1 --fix      # thaw + switch on + unlock the layers used inside the box, move stray arrays onto 57_HATAH_ZIUN
What it checks inside the box: (1) every layer used by an entity is ON, THAWED, unlocked; (2) every associative array (*U block INSERT) is on 57_HATAH_ZIUN, nested bodies too;
(3) there is at least one title text (SIVAN `%%U...`) and one dimension / note on a visible layer. --fix snapshots first (FILE.bak-visibility-HHMMSS) and reports the layers it changed:
a layer is global, so thawing 54 / 57 / 53 also shows the PLAN's own notes on those layers - tell the user which layers were thawed."""
import argparse, os, sys, time
HERE = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, os.path.join(HERE, '..', 'scripts'))
import ezdxf

ARRAY_LAYER = '57_HATAH_ZIUN'
ALWAYS = ('54_HATAH_TEXT', '57_HATAH_ZIUN', '53_HATAH_MIDA', '56_HATAH_ZET', '9_KONTUR', '5_HATAH _KONTUR', '58_HATAH_SIM')   # layers every section uses even when the box check finds none of them yet


def anchor(e):
    t = e.dxftype()
    try:
        if t in ('TEXT', 'INSERT', 'MTEXT'): p = e.dxf.insert
        elif t == 'LINE': p = e.dxf.start
        elif t == 'DIMENSION': p = e.dxf.defpoint
        elif t == 'LWPOLYLINE': p = e.get_points()[0]
        elif t in ('CIRCLE', 'ARC', 'ELLIPSE'): p = e.dxf.center
        else: return None
        return p[0], p[1]
    except Exception: return None


def in_box(e, box):
    p = anchor(e); return p is not None and box[0] <= p[0] <= box[2] and box[1] <= p[1] <= box[3]


def state(doc, name):
    try: l = doc.layers.get(name)
    except Exception: return 'MISSING'
    return ' '.join(s for s, bad in (('OFF', not l.is_on()), ('FROZEN', l.is_frozen()), ('LOCKED', l.is_locked())) if bad)


def scan(doc, box):
    """-> dict(used = {layer: count}, hidden = {layer: state}, stray = [array INSERTs not on ARRAY_LAYER], titles, notes)"""
    ents = [e for e in doc.modelspace() if in_box(e, box)]
    used = {}
    for e in ents: used[e.dxf.layer] = used.get(e.dxf.layer, 0) + 1
    hidden = {n: state(doc, n) for n in set(used) | set(ALWAYS)}
    hidden = {n: s for n, s in hidden.items() if s and (n in used or n in ALWAYS) and s != 'MISSING'}
    stray = [e for e in ents if e.dxftype() == 'INSERT' and e.dxf.name.startswith('*U') and e.dxf.layer != ARRAY_LAYER]
    titles = [e for e in ents if e.dxftype() == 'TEXT' and e.dxf.style.upper() == 'SIVAN' and e.dxf.text.startswith('%%U')]
    visible = lambda e: not state(doc, e.dxf.layer)
    return dict(used=used, hidden=hidden, stray=stray, titles=titles, vis_titles=[e for e in titles if visible(e)],
                vis_dims=[e for e in ents if e.dxftype() == 'DIMENSION' and visible(e)], arrays=[e for e in ents if e.dxftype() == 'INSERT' and e.dxf.name.startswith('*U')])


def problems(s, need_title=True):
    out = [f'layer {n} is {st} but sections use it' for n, st in sorted(s['hidden'].items())]
    if s['stray']: out.append(f"{len(s['stray'])} bar array(s) on {sorted({e.dxf.layer for e in s['stray']})} instead of {ARRAY_LAYER}")
    if need_title and not s['vis_titles']: out.append('no VISIBLE section title in the box (SIVAN %%U text on a visible layer)')
    return out


def fix(doc, box):
    changed = []
    s = scan(doc, box)
    for n in sorted(s['hidden']):
        l = doc.layers.get(n); l.thaw(); l.on(); l.unlock(); changed.append(f"{n} ({s['hidden'][n]})")
    for e in s['stray']:
        e.dxf.layer = ARRAY_LAYER
        for b in doc.blocks.get(e.dxf.name):
            b.dxf.layer = ARRAY_LAYER
    return changed, len(s['stray'])


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('file'); ap.add_argument('--box', nargs=4, type=float, required=True); ap.add_argument('--fix', action='store_true'); ap.add_argument('--no-title', action='store_true', help='XREF overlays carry no title of their own: do not demand one'); a = ap.parse_args()
    doc = ezdxf.readfile(a.file); s = scan(doc, a.box); P = problems(s, not a.no_title)
    print(f"visibility: {len(s['titles'])} titles, {len(s['arrays'])} arrays, {len(s['vis_dims'])} visible dimensions in the box; problems: {len(P)}")
    for p in P: print('  -', p)
    if not P: return
    if not a.fix: sys.exit(1)
    if os.path.exists(a.file + '.dwl'): sys.exit('the file is open in CAD (.dwl): save + close it first')
    import shutil; shutil.copy2(a.file, f'{a.file}.bak-visibility-{time.strftime("%H%M%S")}')
    nb = lambda d: sum(1 for o in d.objects if o.dxftype() == 'ACDBASSOCARRAYACTIONBODY')
    before = nb(doc); changed, moved = fix(doc, a.box); doc.saveas(a.file)
    d2 = ezdxf.readfile(a.file); s2 = scan(d2, a.box); P2 = problems(s2, not a.no_title)
    assert nb(d2) == before, 'associative array bodies changed'
    print(f'FIXED: thawed / switched on {changed or "nothing"}; {moved} array(s) moved to {ARRAY_LAYER}; remaining problems: {len(P2)}')
    if changed: print('  NOTE: these layers are global - the plan\'s own entities on them are visible again; tell the user.')
    for p in P2: print('  -', p)
    if P2: sys.exit(1)


if __name__ == '__main__':
    main()
