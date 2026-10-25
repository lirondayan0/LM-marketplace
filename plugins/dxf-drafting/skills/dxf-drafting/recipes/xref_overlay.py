"""Recipe: REINFORCEMENT OVERLAY on Revit XREF sections (user 2026-10-22, 3841-CON_test.dxf).
  python xref_overlay.py FILE [--dry] [--png OUT] [--only 3,10,14] [--write]
The plan and the sections are Revit XREFs (read-only, cached geometry inside the DXF block definitions). The user's star marks (`hat` pairs on automatic_sections, inside claude_Kontur) say WHERE reinforcement is needed.
 1. every pair -> the XREF section of the Revit section head (numbered pair on the XREF plan 'Level 03 GD', mtexts on G-ANNO-SYMB) NEAREST to it; ambiguous (2nd candidate < 1.5x as far) is flagged UNVERIFIED;
 2. the XREF section's concrete outline (S-BEAM-1 lines + A-FLOR-1 slabs + A-FLOR-MCUT topping line) is read -> W, H, S (panel), T (topping), ledge sides; supported = slabs flush with the beam top and ledge on both sides / one side
    (the hollow-core ledge beam = ledge_beam.build); everything else (slab LOWER than the beam top, wall above, no ledge) is LISTED, not invented (rule 9);
 3. the section is drawn with ledge_beam.OVERLAY = True: ONLY reinforcement (bars, stirrups, leaders, notes, stirrup detail row) in HOST layers, the XREF outline / dims / title / level marker stay the XREF's;
    beam bottom-left of the recipe = stem bottom-left of the XREF section (block coordinates + INSERT point).
S / SS -> standard stirrups, ST -> transfer stirrups (the mark that cuts it); one drawing per XREF section."""
import argparse, math, os, shutil, sys, re, time
HERE = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, HERE); sys.path.insert(0, os.path.join(HERE, '..', 'scripts'))
import ezdxf
from ezdxf.math import is_point_in_polygon_2d, Vec2
import ledge_beam as LB
from dxflib import load_profile, XREF_ROLE_LAYERS

def lay(e): return e.dxf.layer.split('$0$')[-1]
def pt(v): return float(v[0]), float(v[1])

def xref_sections(doc):
    """{number: INSERT} of the Revit section XREFs ('... 03 Sec N-N')"""
    out = {}
    for e in doc.modelspace().query('INSERT'):
        m = re.search(r'Sec-Section - 0\d Sec (\d+)-(\d+)$', e.dxf.name)
        if m and m.group(1) == m.group(2): out[int(m.group(1))] = e
        m = re.search(r'Section - -?\d+ - Section (\d+)$', e.dxf.name)   # 4238-CON-1008-1009 naming
        if m: out.setdefault(int(m.group(1)), e)
        m = re.search(r'Section - Sec\d*-(\d+)$', e.dxf.name)   # 3600-CON-11 naming: '... Sheet - 26 - Section 3-0-Section - Sec0-12'
        if m: out.setdefault(int(m.group(1)), e)
    return out

ROLE_LAYERS = XREF_ROLE_LAYERS      # Revit layer names by role (scripts/dxflib.py)

def section_params(doc, ins):
    """read the concrete outline of one XREF section. Returns (params | None, reason, bottom-left in HOST coordinates).
    params: kind 'ledge' (hollow-core ledge beam: ledge_beam.build, per-side panel drop) or 'cast' (no ledge: general_beam, per-side slab D / level drop), wall = (x0, x1, top) when a wall rises above the beam."""
    blk = doc.blocks.get(ins.dxf.name); ix, iy = ins.dxf.insert.x, ins.dxf.insert.y
    L = [s for s in blk if s.dxftype() == 'LINE']
    beam = [(pt(s.dxf.start), pt(s.dxf.end)) for s in L if lay(s) in ROLE_LAYERS['beam']]
    if not beam:
        ys_ = sorted({round(pt(s_.dxf.start)[1], 1) for s_ in L if lay(s_) in ROLE_LAYERS['floor'] and abs(s_.dxf.start.y - s_.dxf.end.y) < 0.5}, reverse=True)
        if len(ys_) == 3:      # a slab with a thickness STEP, flush top, no beam = his 16-16 (parametric since 2026-10-25, slab_step.build, UNVERIFIED beyond 70 / 25)
            vx_ = [round(pt(s_.dxf.start)[0], 1) for s_ in L if lay(s_) in ROLE_LAYERS['floor'] and abs(s_.dxf.start.x - s_.dxf.end.x) < 0.5]; xf_ = vx_[0] if vx_ else None
            low = [(min(s_.dxf.start.x, s_.dxf.end.x), max(s_.dxf.start.x, s_.dxf.end.x)) for s_ in L if lay(s_) in ROLE_LAYERS['floor'] and abs(s_.dxf.start.y - s_.dxf.end.y) < 0.5 and abs(round(s_.dxf.start.y, 1) - ys_[2]) < 0.2]
            if xf_ is None or not low: return None, f'slab STEP {ys_[0] - ys_[2]:g} / {ys_[0] - ys_[1]:g}: the step face was not found', None
            return dict(kind='step', thick=ys_[0] - ys_[2], thin=ys_[0] - ys_[1], mirror=low[0][0] > xf_ - 0.5), 'ok', (xf_ + ix, ys_[2] + iy)
        return None, 'no beam outline (' + '/'.join(ROLE_LAYERS['beam']) + ')', None
    xs = [p[0] for a, b in beam for p in (a, b)]; ys = [p[1] for a, b in beam for p in (a, b)]
    x0, x1, yb, yt = min(xs), max(xs), min(ys), max(ys); H, W = yt - yb, x1 - x0; xc = (x0 + x1) / 2
    wl = [pt(p) for s in L if lay(s) in ROLE_LAYERS['wall'] for p in (s.dxf.start, s.dxf.end)]
    wall = (min(p[0] for p in wl), max(p[0] for p in wl), max(p[1] for p in wl)) if wl else None
    hor = [(a[1], min(a[0], b[0]), max(a[0], b[0])) for a, b in beam if abs(a[1] - b[1]) < 0.5]
    flr = [(pt(s.dxf.start), pt(s.dxf.end)) for s in L if lay(s) in ROLE_LAYERS['floor']]
    cut = [(pt(s.dxf.start)[1], pt(s.dxf.start)[0], pt(s.dxf.end)[0]) for s in L if lay(s) == 'A-FLOR-MCUT']
    side = {}
    for sd in ('left', 'right'):
        # a slab line belongs to a side when it reaches OUT of the beam on that side (a top line may run straight over the beam: 4238-CON, Sec 20)
        inn = (lambda xa, xb: min(xa, xb) < x0 - 0.5) if sd == 'left' else (lambda xa, xb: max(xa, xb) > x1 + 0.5)
        ys_ = [a_[1] for a_, b_ in flr if abs(a_[1] - b_[1]) < 0.5 and inn(a_[0], b_[0])]
        cy = [y for y, xa, xb in cut if inn(xa, xb)]
        xe = x0 if sd == 'left' else x1
        led = [(y, xa, xb) for y, xa, xb in hor if yb + 0.5 < y < yt - 0.5 and (abs(xa - xe) < 0.5 if sd == 'left' else abs(xb - xe) < 0.5)]
        side[sd] = dict(top=max(ys_) if ys_ else None, soffit=min(ys_) if ys_ else None, T=(max(ys_) - max(cy)) if ys_ and cy else None, ledge=led[0][0] if led else None)
    if side['left']['top'] is None and side['right']['top'] is None: return None, 'no slabs found', None
    tops = [sd['top'] for sd in side.values() if sd['top'] is not None]; sofs = [sd['soffit'] for sd in side.values() if sd['soffit'] is not None]
    if tops and max(tops) > yt + 0.5 and any(abs(s - yt) < 0.5 for s in sofs):   # the S-BEAM-1 outline stops at the slab soffit: the beam top is the slab top (downstand beam, slab runs over it)
        yt = max(tops); H = yt - yb
    for sd in side.values(): sd['drop'] = (yt - sd['top']) if sd['top'] is not None else 0.0
    bl = (x0 + ix, yb + iy); lg, rg = side['left']['ledge'], side['right']['ledge']; Ts = [sd['T'] for sd in side.values() if sd['T'] is not None]
    P = dict(W=W, H=H, T=Ts[0] if Ts else 5.0, wall=wall, drop_left=side['left']['drop'], drop_right=side['right']['drop'])
    need = [(side[k]['top'], side[k]['T'], g_) for k, g_ in (('left', lg), ('right', rg)) if g_ is not None]
    if any(t is None or T is None for t, T, _ in need): return None, 'a ledge was found but the slab top / topping line beside it cannot be read (no slab line on that side) - read the cut by hand', None      # bound file 3841-CON_25.10: one such section crashed the whole scan (TypeError)
    if lg is not None and rg is not None:
        P.update(kind='ledge', sides='both', S_left=(side['left']['top'] - side['left']['T']) - lg, S_right=(side['right']['top'] - side['right']['T']) - rg)
        P['S'] = P['S_left']
    elif lg is not None or rg is not None:
        sd = side['left'] if lg is not None else side['right']; S_ = (sd['top'] - sd['T']) - (lg if lg is not None else rg)
        P.update(kind='ledge', sides='left' if lg is not None else 'right', S_left=None, S_right=None, S=S_)
        P['drop_right' if lg is not None else 'drop_left'] = 0.0
    else:
        if wall: return None, 'wall above a beam without ledges - no rule', None
        one = 'right' if side['left']['top'] is None else ('left' if side['right']['top'] is None else None)      # agreement 2026-10-25 (attempt untaught sections): an EDGE beam, slab on one side, the other face runs to the top (the user's cast L edge beam, general_beam sides=..), UNVERIFIED
        if one:
            sd = side[one]; P.update(kind='cast', sides=one, Dl=0.0, Dr=0.0, dl=0.0, dr=0.0); P['D' + one[0]] = sd['top'] - sd['soffit']; P['d' + one[0]] = sd['drop']
        else: P.update(kind='cast', Dl=side['left']['top'] - side['left']['soffit'], Dr=side['right']['top'] - side['right']['soffit'], dl=side['left']['drop'], dr=side['right']['drop'])
    return P, 'ok', bl

def template_params(doc, ins):
    """no taught rule for this outline: the nearest HAND-DRAWN example of the reference library (scripts/ref_library.py, his 3841-CON_claude_ file) -> (P, why, bl) or (None, why, None)"""
    import ref_library as RL
    ent, info = RL.match(doc, ins)
    if ent is None: return None, info, None
    return dict(kind='template', ent=ent, info=info), 'ok', info['anchor']

def resolve(doc, ins):
    """(P, why, bottom-left) of an XREF section by the order of trust: taught rule (section_params) -> the nearest hand-drawn example of the reference library (template; he drew it) -> junction (my judgment, UNVERIFIED)"""
    P, why, bl = section_params(doc, ins)
    if P is not None: return P, why, bl
    P2, why2, bl2 = template_params(doc, ins)
    if P2 is not None: return P2, why2, bl2
    import xref_junction as XJ
    if XJ.read(doc, ins)['walls']:
        from ezdxf import bbox as BB; e_ = BB.extents(list(doc.blocks.get(ins.dxf.name)))
        return dict(kind='junction'), 'ok', (e_.extmin.x + ins.dxf.insert.x, e_.extmin.y + ins.dxf.insert.y)
    return None, f'{why}; {why2}', None

def read_marks(doc):
    """user's star pairs inside claude_Kontur: [{mark, rot, c}]"""
    msp = doc.modelspace(); kont = [[(p[0], p[1]) for p in e.get_points('xy')] for e in msp.query('LWPOLYLINE') if e.dxf.layer == 'claude_Kontur']
    hats = [e for e in msp.query('INSERT') if e.dxf.name == 'hat' and e.dxf.layer == 'automatic_sections']
    used, out = set(), []
    for i, h in enumerate(hats):
        if i in used: continue
        for j, g in enumerate(hats):
            if j > i and j not in used and abs(h.dxf.insert.x - g.dxf.insert.x) < 300 and abs(h.dxf.insert.y - g.dxf.insert.y) < 300 and h.attribs[0].dxf.text == g.attribs[0].dxf.text and round(h.dxf.rotation) == round(g.dxf.rotation):
                used |= {i, j}; c = ((h.dxf.insert.x + g.dxf.insert.x) / 2, (h.dxf.insert.y + g.dxf.insert.y) / 2)
                if not kont or any(is_point_in_polygon_2d(Vec2(c), [Vec2(p) for p in k]) >= 0 for k in kont):
                    out.append(dict(hats=[h, g], mark=h.attribs[0].dxf.text, rot=round(h.dxf.rotation), c=c, horiz=abs(h.dxf.insert.x - g.dxf.insert.x) > abs(h.dxf.insert.y - g.dxf.insert.y)))
                break
    return out

def revit_heads(doc, plan_dxf=None):
    """numbered section head pairs of the XREF plan (GD): [{n, c (host), horiz}]. The plan XREF block may be EMPTY in the host (4238-CON-1008-1009, 2026-10-23): then read the DWG converted to DXF (--plan-dxf, accoreconsole DXFOUT) and place it at the INSERT point."""
    ins = next(e for e in doc.modelspace().query('INSERT') if re.search(r'(Level 03|LEV_[-\w]+|Structural Plan - [-\w ]+?) GD$', e.dxf.name)); b = doc.blocks.get(ins.dxf.name); ox, oy = ins.dxf.insert.x, ins.dxf.insert.y
    if plan_dxf and len(b) == 0: b = ezdxf.readfile(plan_dxf).modelspace()
    nums = []
    for e in b:
        if e.dxftype() == 'MTEXT' and ('G-ANNO-SYMB' in e.dxf.layer or 'Z-050-M_SECTION' in e.dxf.layer):      # Revit layer of the numbered section heads: G-ANNO-SYMB (4238) or Z-050-M_SECTION (3600-CON-11)
            t = e.text.split(';')[-1].replace('}', '').strip()
            if re.fullmatch(r'\d+', t): nums.append((int(t), e.dxf.insert.x + ox, e.dxf.insert.y + oy))
    used, pairs = set(), []
    for i, (t, x, y) in enumerate(nums):
        if i in used: continue
        best = None
        for j, (t2, x2, y2) in enumerate(nums):
            if j != i and j not in used and t2 == t:
                d = math.hypot(x - x2, y - y2)
                if best is None or d < best[0]: best = (d, j)
        if best and best[0] < 600:
            j = best[1]; used |= {i, j}; pairs.append(dict(n=t, c=((x + nums[j][1]) / 2, (y + nums[j][2]) / 2), horiz=abs(x - nums[j][1]) > abs(y - nums[j][2])))
    if not pairs: raise RuntimeError('no numbered section heads in the plan XREF block' + (' (the block is EMPTY: the XREF was unloaded when the DXF was saved - give the plan as a separate DXF)' if len(b) == 0 else ' (layers G-ANNO-SYMB / Z-050-M_SECTION)'))
    return pairs

def match(marks, heads):
    for m in marks:
        c = sorted((math.hypot(h['c'][0] - m['c'][0], h['c'][1] - m['c'][1]), h['n']) for h in heads if h['horiz'] == m['horiz'])
        m['sec'] = c[0][1]; m['dist'] = c[0][0]
        alt = next((d for d, n in c[1:] if n != c[0][1]), None); m['ambiguous'] = bool(alt and alt < 1.5 * c[0][0]); m['alt'] = next((n for d, n in c[1:] if n != c[0][1]), None)
    return marks

def draw_wall_note(doc, P, ins):
    """wall above the beam (the XREF draws the wall): leader from the wall top + the two SIVAN note lines copied from the user's template (brenda_karka, 'beam with a wall rising above'). UNVERIFIED layout."""
    msp = doc.modelspace(); x0, x1, top = P['wall']; z = '56_HATAH_ZET'; T = LB.PROF['layers']['text']
    X, Y = (x0 + x1) / 2 + ins.dxf.insert.x, top + ins.dxf.insert.y
    ex, ey = X + 40, Y - 12
    msp.add_lwpolyline([(X, Y - 3), (ex, ey), (ex + 90, ey)], dxfattribs=dict(layer=z))
    for raw, dy in (('zhui ehru,', 3.0), ('zhui  kph ', 12.0)):
        msp.add_text(raw, height=6.0, dxfattribs=dict(layer=T, style='SIVAN', width=0.8, text_generation_flag=2, insert=(ex + 88, ey + dy)))

def draw_junction(doc, num, ins, P, bl, kind):
    """wall / slab junction sections (xref_junction): reinforcement over the XREF outline + the usual finishing passes"""
    import xref_junction as XJ, rebar_color, sivan_text, leader_fit
    from ezdxf import bbox as BB
    msp = doc.modelspace(); before = {e.dxf.handle for e in msp}; tmpl = LB.template_texts(doc)
    print('   junction:', XJ.draw_section(doc, num, ins, tmpl, kind))
    e_ = BB.extents(list(doc.blocks.get(ins.dxf.name))); ix, iy = ins.dxf.insert.x, ins.dxf.insert.y
    box = (e_.extmin.x + ix - 150, e_.extmin.y + iy - 200, e_.extmax.x - e_.extmin.x + 300, e_.extmax.y - e_.extmin.y + 400)
    rebar_color.colour_box(doc, box); sivan_text.convert_box(doc, box); leader_fit.fit_box(doc, box)
    return [e for e in msp if e.dxf.handle not in before], None

def draw_step(doc, num, ins, P, bl, kind):
    """slab with a thickness step and no beam: his 16-16 from rules (slab_step.build, overlay = reinforcement, notes and the U-bar detail only); bl = (step face x, thick soffit y) in host coordinates"""
    import slab_step as SS, rebar_color, sivan_text, leader_fit
    msp = doc.modelspace(); before = {e.dxf.handle for e in msp}; ox, oy = bl[0] - SS.XF, bl[1] - SS.S0
    SS.build(doc, ox, oy, f'{num}-{num}', P['thick'], P['thin'], P['mirror'], overlay=True)
    box = (ox - 200, oy - 300, 520, 560); rebar_color.colour_box(doc, box); sivan_text.convert_box(doc, box); leader_fit.fit_box(doc, box)
    return [e for e in msp if e.dxf.handle not in before], None

def draw_section(doc, num, ins, P, bl, kind):
    """draw the reinforcement of XREF section `num` over the XREF outline; returns the new entities"""
    if P.get('kind') == 'junction':
        try: return draw_junction(doc, num, ins, P, bl, kind)
        except Exception as ex:                                  # xref_junction could not read this one: the library example, else say so (never kill the whole run)
            print(f'   Sec {num}: WARNING junction recipe failed ({type(ex).__name__}: {ex}) - NOT DRAWN'); return [], None
    if P.get('kind') == 'step': return draw_step(doc, num, ins, P, bl, kind)
    if P.get('kind') == 'template':
        import ref_library as RL
        print(f"   Sec {num}: TEMPLATE (UNVERIFIED approximation, rule 9): {P['info']['note']}" + ('' if P['info']['hollow'] == P['info']['ref_hollow'] else '; slab type differs from the example (hollow / solid)'))
        return RL.place(doc, P['ent'], P['info']), None
    msp = doc.modelspace(); LB.apply_profile('israeli-structural'); LB.OVERLAY = True
    LB.STIRRUPS = 'transfer' if kind == 'ST' else 'standard'; LB.STIRRUP_SPACING = load_profile('israeli-structural')['stirrup_tables'][LB.STIRRUPS]['note']; LB.H_SYM = None; LB.SOLID_SYM = None
    before = {e.dxf.handle for e in msp}; tmpl = LB.template_texts(doc); g = None
    if P['kind'] == 'ledge':
        g = LB.build(P['W'], P['H'], P.get('S') or P['S_left'], P['T'], P['sides'], P['S_left'], P['S_right'], drop_left=P['drop_left'], drop_right=P['drop_right'])
        LB.draw(doc, g, bl[0], bl[1], f'{num}-{num}', tmpl)
    else:
        import general_beam as GB; GB.OVERLAY = True
        lab = {'B': None, 'H': None, 'D': None, 'B-6': None, 'H-6': None}
        GB.draw(doc, P['W'], max(P['Dl'], P['Dr']) if P.get('sides') else min(P['Dl'], P['Dr']), P['H'], bl[0], bl[1], f'{num}-{num}', tmpl, lab, 0.0, LB.STIRRUPS, P['Dl'], P['Dr'], P['dl'], P['dr'], P.get('sides', 'both'))
    if P.get('wall'):
        import xref_wall; from ezdxf import bbox as BB
        ix, iy = ins.dxf.insert.x, ins.dxf.insert.y; x0w, x1w, topw = P['wall']; ext = BB.extents(list(doc.blocks.get(ins.dxf.name)))
        xref_wall.draw_wall(doc, x0w + ix, x1w + ix, bl[1], bl[1] + P['H'], topw + iy, ext.extmax.x + ix + 37.3)
    below = max(200.0, P['H'] + 120.0)                  # the stirrup elevation of a cast beam hangs under the section (general_beam BELOW): down to H + ~110
    box = (bl[0] - 120, bl[1] - below, 400, below + 200)
    import rebar_color, sivan_text, leader_fit
    rebar_color.colour_box(doc, box); sivan_text.convert_box(doc, box); leader_fit.fit_box(doc, box)
    class A: pass
    a = A(); a.box = list(box); a.detail = {'S': 'plan', 'ST': 'plan', 'SS': 'ss'}[kind]; LB.apply_detail(doc, a)
    return [e for e in msp if e.dxf.handle not in before], g

def main():
    ap = argparse.ArgumentParser(); ap.add_argument('file'); ap.add_argument('--dry', action='store_true'); ap.add_argument('--png'); ap.add_argument('--only'); ap.add_argument('--write', action='store_true'); ap.add_argument('--plan-dxf'); ap.add_argument('--keep-marks', action='store_true', help='keep his star marks on the plan (default: a mark is DELETED once its section is drawn - user 2026-10-23)'); ap.add_argument('--all', action='store_true', help='ONLY WHEN THE USER SAYS "every section" (2026-10-23: he wanted just the requested ones): also every XREF section WITHOUT a star mark and without host reinforcement (user 2026-10-23: no wall / beam / slab section without reinforcement; type S by default, UNVERIFIED)'); a = ap.parse_args()
    t0 = time.time(); doc = ezdxf.readfile(a.file); print(f'loaded in {time.time() - t0:.0f}s')
    secs = xref_sections(doc); marks = match(read_marks(doc), revit_heads(doc, a.plan_dxf))
    bysec = {}
    for m in marks: bysec.setdefault(m['sec'], []).append(m)
    if a.all:
        for n, ins in secs.items():
            if n in bysec: continue
            P, why, bl = resolve(doc, ins)
            if P is None: print(f'Sec {n}: NOT DRAWN (no taught rule, no matching reference example, no wall): {why}'); continue
            x0, y0 = bl; has = any(e.dxf.layer == '57_HATAH_ZIUN' and x0 - 200 < e.dxf.insert.x < x0 + 300 and y0 - 100 < e.dxf.insert.y < y0 + 250 for e in doc.modelspace().query('INSERT')) or any(e.dxf.layer == '57_HATAH_ZIUN' and x0 - 200 < e[0][0] < x0 + 300 and y0 - 100 < e[0][1] < y0 + 250 for e in doc.modelspace().query('LWPOLYLINE'))
            if has: print(f'Sec {n}: already has reinforcement - skipped'); continue
            bysec[n] = [dict(mark='S', c=(x0, y0), rot=0, horiz=True, sec=n, dist=0.0, ambiguous=False, alt=None, unmarked=True, junction=(P or {}).get('kind') == 'junction')]
    todo = []
    for n in sorted(bysec):
        P, why, bl = resolve(doc, secs[n]); ms = bysec[n]
        kinds = sorted({m['mark'] for m in ms})
        print(f"Sec {n}: marks {[(m['mark'], round(m['c'][0]), round(m['c'][1]), round(m['dist']), 'AMBIGUOUS vs ' + str(m['alt']) if m['ambiguous'] else '') for m in ms]}")
        if P is None: print('   NOT DRAWN:', why); continue
        print('   ', {k: (round(v, 1) if isinstance(v, float) else v) for k, v in P.items() if v is not None and k not in ('ent', 'info')}, 'bottom-left', tuple(round(v, 1) for v in bl), ('UNVERIFIED: marks of different kinds ' + str(kinds)) if len(kinds) > 1 else '')
        todo.append((n, secs[n], P, bl, ms[0]['mark']))
    if a.only: todo = [t for t in todo if t[0] in {int(x) for x in a.only.split(',')}]
    if a.dry and not a.png: return
    drawn = []
    for n, ins, P, bl, kind in todo: drawn.append((n, draw_section(doc, n, ins, P, bl, kind)))
    if a.write and not a.keep_marks:        # user 2026-10-23: 'after you create the section, delete the mark for it that I indicated on the plan' (only the marks of the sections drawn now)
        gone = 0
        for n, ins, P, bl, kind in todo:
            for m in bysec.get(n, []):
                for h in m.get('hats', []): doc.modelspace().delete_entity(h); gone += 1
        print(f'deleted {gone} star-mark blocks of the sections drawn')
    if a.png:
        import matplotlib; matplotlib.use('Agg'); import matplotlib.pyplot as plt
        fig, axs = plt.subplots(1, max(1, len(drawn)), figsize=(9 * max(1, len(drawn)), 9)); axs = [axs] if len(drawn) == 1 else list(axs)
        for ax, (n, (new, g)) in zip(axs, drawn):
            ins = secs[n]; ix, iy = ins.dxf.insert.x, ins.dxf.insert.y
            for s in doc.blocks.get(ins.dxf.name):
                if s.dxftype() == 'LINE': ax.plot([s.dxf.start.x + ix, s.dxf.end.x + ix], [s.dxf.start.y + iy, s.dxf.end.y + iy], color='0.3', lw=1.2)
            for e in new:
                t = e.dxftype()
                if t == 'LINE': ax.plot([e.dxf.start.x, e.dxf.end.x], [e.dxf.start.y, e.dxf.end.y], 'g', lw=.6)
                elif t == 'LWPOLYLINE':
                    pp = [(p[0], p[1]) for p in e.get_points('xy')]
                    if len(pp) == 2 and e.dxf.get('const_width', 0) > 0: ax.plot(*zip(*pp), 'b.', ms=3)
                    else: ax.plot([p[0] for p in pp] + ([pp[0][0]] if e.closed else []), [p[1] for p in pp] + ([pp[0][1]] if e.closed else []), 'r' if e.dxf.layer == '57_HATAH_ZIUN' else 'g', lw=.8)
                elif t == 'TEXT': ax.text(e.dxf.insert.x, e.dxf.insert.y, e.dxf.text, fontsize=6, color='m')
            ax.set_aspect('equal'); ax.set_title(f'Sec {n}-{n}')
        plt.savefig(a.png, dpi=70, bbox_inches='tight'); print('png', a.png)
    if a.write:
        out = a.file; stamp = time.strftime('%H%M%S'); bak = f'{out}.bak-xref-{stamp}'
        if os.path.exists(out + '.dwl') or os.path.exists(out + '.dwl2'): sys.exit('file is open in CAD (.dwl) - save + close it, then re-run')
        shutil.copy2(out, bak); print('snapshot', bak); doc.saveas(out); print('saved', out)

if __name__ == '__main__': main()
