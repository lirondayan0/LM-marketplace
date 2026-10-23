"""Recipe: WALL RISING ABOVE A BEAM on a Revit XREF section - reinforcement as the user drew it by hand in 3841-CON_test Sec 9 (2026-10-23).
  imported by xref_overlay.draw_section (replaces the old note-only draw_wall_note). Geometry relative to the wall (face xl / xr, top yw) and the beam (bottom yb, top ybt):
  1. horizontal wall bars = two dot columns at xl + 4.2 / xr - 4.2, rows from ybt - 4.6 up to yw - 4.2 in EQUAL steps <= STEP_H (16.1; his 160.4 span = 11 dots) -> arrays later (bar_arrays);
  2. vertical bars: face bar with hooks = C polyline  (xr-3, yb+3) -> (xl+2.9, yb+3) -> (xl+2.9, yw-3) -> (xr-3, yw-3)  (hooks 14 both ends, runs down through the whole beam);
     other face = straight bar (xr-3, ybt-13) -> (xr-3, yw-3);
  3. '2$12' note on the two top dots (fork joint 7.6 left of the wall, 15.5 below its top; shelf 20.2 left; text 1.0 above the shelf);
  4. wall-reinforcement note ('zhui ehru,' over 'zhui  kph ' = 'wall reinforcement per plan'), leader from the face column at ~69 % of the wall height, elbow 33.5 left / 14.3 down, shelf to the left;
  5. BAR SHAPE DETAIL to the right of everything (X0 = XREF right edge + 37.3): two mirrored C shapes (vertical H_bar = yw - yb - 6, hooks 14 at both ends), dims 14 / H_bar (dim_25_BARZEL_Above on 54_HATAH_TEXT),
     label ' $8@15 L=<H_bar+14>' rotated 90 beside each vertical (his L=258 for 244: L = H_bar + 14), leader from the middle of the shape to BOTH section bars with leader dots (width 1.75).
  Bar size 8 @ 15 is HIS number (nearest example, rule 9 = never invented); only the lengths scale with the wall."""
import math
import ledge_beam as LB

STEP_H = 16.1; COV_D = 4.2; COV_V = 3.0; HOOK = 14.0; LABEL = ' $8@15 L=%d'
Z = '56_HATAH_ZET'; RB = '57_HATAH_ZIUN'; T = '54_HATAH_TEXT'

def wall_dots(xl, xr, ybt, yw):
    y0, y1 = ybt - 4.6, yw - COV_D; n = max(2, math.ceil((y1 - y0) / STEP_H - 1e-9) + 1)
    return [xl + COV_D, xr - COV_D], [y0 + (y1 - y0) * i / (n - 1) for i in range(n)]

def draw_wall(doc, xl, xr, yb, ybt, yw, shape_x0):
    """xl, xr = wall faces, yb / ybt = beam bottom / top, yw = wall top, shape_x0 = x of the left vertical of the bar-shape detail (all host coordinates)"""
    msp = doc.modelspace(); cols, rows = wall_dots(xl, xr, ybt, yw)
    for x in cols:
        for y in rows: LB.add_dot(msp, x, y, RB)
    yt, ys = yw - COV_V, yb + COV_V; xL, xR = xl + 2.9, xr - COV_V
    msp.add_lwpolyline([(xR, ys), (xL, ys), (xL, yt), (xR, yt)], dxfattribs=dict(layer=RB))
    msp.add_lwpolyline([(xR, ybt - 13.0), (xR, yt)], dxfattribs=dict(layer=RB))
    tx = dict(layer=T, style='HEBREW_NEW', height=6.0, width=0.8)
    # 2$12 on the two top dots
    jx, jy = xl - 7.6, yw - 15.5
    msp.add_lwpolyline([(jx, jy), (jx - 20.2, jy)], dxfattribs=dict(layer=Z))
    msp.add_line((jx, jy), (xr - 4.3, yw - 3.9), dxfattribs=dict(layer=Z)); msp.add_line((jx, jy), (xl + 4.8, yw - 4.4), dxfattribs=dict(layer=Z))
    msp.add_text('2$12', dxfattribs=dict(tx, insert=(jx - 17.9, jy + 1.0)))
    # wall note: leader from the left column near 69 % of the wall height
    k = min(range(len(rows)), key=lambda i: abs(rows[i] - (ybt + 0.69 * (yw - ybt)))); ty = rows[k] + 3.2; tipx = xl + COV_D
    ex, ey = tipx - 33.5, ty - 14.3
    msp.add_lwpolyline([(tipx, ty), (ex, ey), (ex - 36.9, ey)], dxfattribs=dict(layer=Z))
    for raw, dy, dx in (('zhui ehru,', 3.0, 2.5), ('zhui  kph ', 12.0, -1.3)):      # his positions: text x = elbow + 2.5 / - 1.3 (mirrored SIVAN hangs left of its insert point)
        msp.add_text(raw, dxfattribs=dict(layer=T, style='SIVAN', height=6.0, width=0.8, text_generation_flag=2, insert=(ex + dx, ey + dy)))
    # bar shape detail (two mirrored C shapes) + dims + labels + leader to both section bars
    Hb = yt - ys; sa, sb = shape_x0, shape_x0 + 33.7      # left vertical / right vertical (his -25340.2 / -25306.5)
    for xv, d in ((sa, 1), (sb, -1)):
        msp.add_lwpolyline([(xv, ys), (xv, yt), (xv + d * HOOK, yt)], dxfattribs=dict(layer=RB)); msp.add_lwpolyline([(xv, ys), (xv + d * HOOK, ys)], dxfattribs=dict(layer=RB))
        for yy in (ys, yt):
            dm = msp.add_linear_dim(base=(xv + d * HOOK / 2, yy), p1=(xv, yy), p2=(xv + d * HOOK, yy), angle=0, dimstyle='dim_25_BARZEL_Above', dxfattribs=dict(layer=T)); dm.render()
        dm = msp.add_linear_dim(base=(xv, ys), p1=(xv, ys), p2=(xv, yt), angle=90, dimstyle='dim_25_BARZEL_Above', dxfattribs=dict(layer=T)); dm.render()
        lx, ly = xv - 2.8, ys + Hb * 0.457
        msp.add_text(LABEL % round(Hb + HOOK), dxfattribs=dict(tx, rotation=90, halign=1, insert=(lx, ly), align_point=(lx, ly)))
    jy2 = ybt + 90.2 * (yw - ybt) / 160.2; jx2 = sa + 4.3        # his leader joint: y = beam top + 90.2 for a 160.2 wall
    msp.add_line((sa, jy2), (sb + 0.7, jy2), dxfattribs=dict(layer=Z))
    msp.add_line((jx2, jy2), (xL, jy2 - 4.1), dxfattribs=dict(layer=Z)); msp.add_lwpolyline([(jx2, jy2), (xR, jy2 - 6.1)], dxfattribs=dict(layer=Z))
    for xv in (sa, sb):
        msp.add_lwpolyline([(xv - 0.7, jy2), (xv + 0.8, jy2)] if xv == sa else [(xv - 0.8, jy2), (xv + 0.7, jy2)], dxfattribs=dict(layer=Z, const_width=1.75))
    return dict(rows=len(rows), n_dots=2 * len(rows), L=round(Hb + HOOK))
