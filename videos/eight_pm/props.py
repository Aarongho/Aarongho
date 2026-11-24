"""eight_pm sets: night street (Eddie's 2-storey house), house interiors, Lily's bedroom,
society vignettes, the Visitor (tall, thin, long pale fingers, huge black eyes, too-wide smile).
Characters face -Y at rot=0."""
import math, os, random
import bpy
from mathutils import Vector
from rbx.core import (D, F, mat, hexc, box, cyl, sphere, plane, card, empty, light, collection, noise,
                      set_interp, fcurves, text)
from rbx import chars, sets
from rbx.story import _live

FONT = next((p for p in ("/usr/share/fonts/opentype/inter/InterDisplay-Black.otf",
                         "/System/Library/Fonts/Supplemental/Arial Black.ttf",
                         "C:/Windows/Fonts/ariblk.ttf") if os.path.exists(p)), None)

RED_LAMP = (1.0, 0.06, 0.04)
WARM_LAMP = (1.0, 0.75, 0.45)


# ------------------------------------------------------------------ world
def night_world(strength=1.0):
    w = D.worlds.new("Night"); bpy.context.scene.world = w
    w.use_nodes = True; nt = w.node_tree
    bg = next(n for n in nt.nodes if n.type == "BACKGROUND")
    tc = nt.nodes.new("ShaderNodeTexCoord"); sep = nt.nodes.new("ShaderNodeSeparateXYZ")
    nt.links.new(tc.outputs["Generated"], sep.inputs[0])
    cr = nt.nodes.new("ShaderNodeValToRGB")
    cr.color_ramp.elements[0].position = 0.48; cr.color_ramp.elements[0].color = (0.04, 0.06, 0.16, 1)
    cr.color_ramp.elements[1].position = 0.72; cr.color_ramp.elements[1].color = (0.006, 0.01, 0.04, 1)
    nt.links.new(sep.outputs["Z"], cr.inputs[0]); nt.links.new(cr.outputs[0], bg.inputs[0])
    bg.inputs[1].default_value = strength
    return bg


def day_world(strength=1.0):
    w = D.worlds.new("Day"); bpy.context.scene.world = w
    w.use_nodes = True
    bg = next(n for n in w.node_tree.nodes if n.type == "BACKGROUND")
    bg.inputs[0].default_value = (0.35, 0.6, 1.0, 1); bg.inputs[1].default_value = strength


def moonlight(strength=0.6):
    return light("moon_sun", "SUN", (0, 0, 60), strength, (0.55, 0.65, 1.0), 3, rot=(55, 0, -150))


def fill(loc, target, energy=250, color=(0.6, 0.7, 1.0), size=6):
    """Soft fill so nothing goes pitch black."""
    return light("fill", "AREA", loc, energy, color, size, target=target)


def sign(name, body, loc, size, color="#ffffff", rot=(90, 0, 0), emit=0.0, parent=None, coll=None):
    m = mat("sign_" + color + str(emit), hexc(color), 0.4, emit=hexc(color) if emit else None, estr=emit)
    return text(name, body, loc, size, m, rot=rot, extrude=0.03, font=FONT, parent=parent, coll=coll)


# ------------------------------------------------------------------ street
def street_lamp(name, loc, coll, red_at=None, red=False):
    Mp = mat("lamp_pole", hexc("#23252c"), 0.5, metal=0.6)
    root = empty(name, loc, coll=coll)
    cyl(name + "_pole", 0.16, 8.0, (0, 0, 4.0), Mp, 12, parent=root, coll=coll)
    box(name + "_arm", (0.2, 2.0, 0.2), (0, 0.9, 7.9), Mp, 0.03, parent=root, coll=coll)
    col = RED_LAMP if red else WARM_LAMP
    Mg = mat(f"{name}_glow", col, 0.3, emit=col, estr=14.0)
    bulb = box(name + "_glass", (0.7, 0.7, 0.45), (0, 1.7, 7.6), Mg, 0.05, parent=root, coll=coll)
    lt = light(name + "_lt", "SPOT", (loc[0], loc[1] + 1.7, 7.3), 2500, col, 0.4, coll=coll, spot=95, blend=0.6,
               rot=(0, 0, 0), shadow=False)
    if red_at is not None and not red:
        bs = Mg.node_tree.nodes["Principled BSDF"].inputs["Emission Color"]
        for c, t in ((WARM_LAMP, red_at - 0.05), (RED_LAMP, red_at + 0.05)):
            bs.default_value = (*c, 1); bs.keyframe_insert("default_value", frame=F(t))
            lt.data.color = c; lt.data.keyframe_insert("color", frame=F(t))
    return root


def house2(name, loc, coll, col="#5b4a6a", lily_open=False, open_t=None, door_hinge=True, lit_windows=True):
    """Two-storey house; door faces -Y. Returns dict of parts."""
    root = empty(name, loc, coll=coll)
    W_, D_, H_ = 14, 10, 13
    Mw = mat("hw_" + col, hexc(col), 0.85)
    box(name + "_body", (W_, D_, H_), (0, 0, H_ / 2), Mw, 0.1, parent=root, coll=coll)
    Mr = mat("roof_dark", hexc("#2a1f24"), 0.7)
    for s in (-1, 1):
        box(f"{name}_roof{s}", (W_ + 1.2, D_ * 0.62, 0.5), (0, s * D_ * 0.25, H_ + D_ * 0.18), Mr, 0.1,
            rot=(s * -35, 0, 0), parent=root, coll=coll)
    Mtrim = mat("trim_white", hexc("#e8e6e0"), 0.6)
    fy = -D_ / 2
    # door
    box(name + "_doorhole", (2.4, 0.1, 4.2), (0, fy - 0.01, 2.1), mat("door_dark", hexc("#050506"), 1.0), 0, parent=root, coll=coll)
    hinge = empty(name + "_hinge", (-1.2, fy - 0.1, 0), parent=root, coll=coll)
    box(name + "_door", (2.4, 0.2, 4.2), (1.2, 0, 2.1), mat("door_red", hexc("#5a1a16"), 0.6), 0.04, parent=hinge, coll=coll)
    knob = sphere(name + "_knob", 0.14, (2.05, -0.2, 2.0), mat("brass", hexc("#c9a240"), 0.3, metal=0.9), parent=hinge, coll=coll, seg=12)
    box(name + "_step", (3.4, 1.2, 0.3), (0, fy - 0.6, 0.15), mat("step", hexc("#6a6a70"), 0.8), 0.04, parent=root, coll=coll)
    # windows: (x, z) ground kitchen left, ground right, upstairs left, upstairs right (Lily)
    Mlit = mat("win_lit", (1, 0.8, 0.5), 0.3, emit=(1.0, 0.72, 0.4), estr=2.5)
    Mdark = mat("win_dark", hexc("#0c0f18"), 0.2)
    wins = {}
    for key, x, z in (("kitchen", -4.4, 3.6), ("living", 4.4, 3.6), ("hall_up", -4.4, 9.6), ("lily", 4.4, 9.6)):
        lit = lit_windows and key != "lily"
        box(f"{name}_w_{key}", (2.6, 0.1, 2.6), (x, fy - 0.02, z), Mlit if lit else Mdark, 0.02, parent=root, coll=coll)
        for dx in (-1.4, 1.4):
            box(f"{name}_wt_{key}{dx}", (0.2, 0.25, 2.9), (x + dx, fy - 0.1, z), Mtrim, 0.02, parent=root, coll=coll)
        box(f"{name}_ws_{key}", (3.2, 0.5, 0.2), (x, fy - 0.2, z - 1.45), Mtrim, 0.02, parent=root, coll=coll)
        wins[key] = (loc[0] + x, loc[1] + fy, loc[2] + z)
    # Lily's sash (lower pane) slides up when open
    sash = box(name + "_sash", (2.6, 0.12, 1.3), (4.4, fy - 0.16, 9.6 - 0.65), mat("glass_blue", hexc("#30405a"), 0.05,
               alpha=0.5), 0.02, parent=root, coll=coll)
    if lily_open:
        sash.location[2] = 9.6 + 0.65
    if open_t is not None:
        sash.location[2] = 9.6 - 0.65; sash.keyframe_insert("location", index=2, frame=F(open_t))
        sash.location[2] = 9.6 + 0.65; sash.keyframe_insert("location", index=2, frame=F(open_t + 0.4))
    return dict(root=root, hinge=hinge, knob=knob, sash=sash, wins=wins, front_y=loc[1] + fy)


HOUSE_X = (-44, -22, 0, 22, 44)
HOUSE_COLS = ["#4a5a6e", "#6a5a4a", "#5b4a6a", "#4f5f58", "#5f4a4a"]


def street(coll=None, red=False, red_at=None, lily_open=False, open_t=None, lit=True):
    c = coll or collection("STREET")
    box("ground", (400, 400, 0.4), (0, 0, -0.2), mat("grass_night", hexc("#24331f"), 0.95), 0, coll=c)
    box("road", (300, 9, 0.06), (0, -6, 0.03), mat("asphalt", hexc("#2e3038"), 0.8), 0, coll=c)
    box("walk", (300, 3, 0.2), (0, 0.4, 0.1), mat("sidewalk", hexc("#6a6c74"), 0.8), 0.02, coll=c)
    box("walk2", (300, 3, 0.2), (0, -12.4, 0.1), mat("sidewalk", hexc("#6a6c74"), 0.8), 0.02, coll=c)
    Md = mat("dash", hexc("#d8c060"), 0.6)
    for i in range(-12, 13):
        box(f"dash{i}", (2.2, 0.25, 0.02), (i * 6, -6, 0.07), Md, 0, coll=c)
    houses = {}
    for i, x in enumerate(HOUSE_X):
        houses[x] = house2(f"h{i}", (x, 12, 0), c, HOUSE_COLS[i], lily_open=(lily_open and x == 0),
                           open_t=(open_t if x == 0 else None), lit_windows=lit)
        # path to the door
        box(f"path{i}", (2.4, 5.5, 0.08), (x, 4.2, 0.05), mat("path", hexc("#7a7a80"), 0.8), 0, coll=c)
    for i, x in enumerate((-33, -11, 11, 33)):
        street_lamp(f"lamp{i}", (x, -0.6, 0), c, red_at=(red_at + i * 0.35) if red_at is not None else None, red=red)
    # houses across the street (silhouettes)
    for i, x in enumerate((-40, -18, 4, 26, 48)):
        box(f"far{i}", (13, 9, 11), (x, -26, 5.5), mat("far_house", hexc("#1d2230"), 0.9), 0.1, coll=c)
        box(f"farw{i}", (2.2, 0.1, 2.2), (x + 3, -21.44, 7), mat("win_lit", (1, 0.8, 0.5), 0.3, emit=(1.0, 0.72, 0.4), estr=1.5), 0, coll=c)
    rnd = random.Random(4)
    Mt = mat("pine", hexc("#0f1f1c"), 0.9)
    for k in range(40):
        x = rnd.uniform(-90, 90); y = rnd.uniform(26, 60)
        h = rnd.uniform(12, 20)
        cyl(f"pn{k}", rnd.uniform(3, 4.5), h, (x, y, h / 2), Mt, 8, r2=0.05, coll=c)
    sphere("moon", 5, (-60, 200, 80), mat("moon_m", (1, 1, 1), 0.5, emit=hexc("#dfe8ff"), estr=6.0), seg=32, coll=c)
    return c, houses


def clock_tower(loc=(0, 70, 0), coll=None, t_ring=(), hour=8.0):
    c = coll or collection("TOWER")
    root = empty("tower", loc, coll=c)
    Ms = mat("tower_stone", hexc("#4a4a55"), 0.8)
    box("tw_body", (8, 8, 25.5), (0, 0, 12.75), Ms, 0.1, parent=root, coll=c)
    for sx in (-1, 1):
        for sy in (-1, 1):
            box(f"tw_pil{sx}{sy}", (1.2, 1.2, 4.6), (sx * 3.4, sy * 3.4, 27.8), Ms, 0.05, parent=root, coll=c)
    light("bell_lt", "POINT", (0, -6, 28), 800, (1.0, 0.8, 0.5), 0.5, coll=c, shadow=False)
    box("tw_top", (9.5, 9.5, 1), (0, 0, 30.5), Ms, 0.1, parent=root, coll=c)
    cyl("tw_roof", 6.5, 8, (0, 0, 35), mat("roof_dark", hexc("#2a1f24"), 0.7), 4, r2=0.1, rot=(0, 0, 45), parent=root, coll=c)
    face = cyl("tw_face", 3.0, 0.3, (0, -4.05, 20.5), mat("clock_face", hexc("#f2ead2"), 0.5, emit=hexc("#f2ead2"), estr=1.5),
               40, rot=(90, 0, 0), parent=root, coll=c)
    Mh = mat("clock_hand", hexc("#151515"), 0.5)
    for k, (ln, ang) in enumerate(((1.7, hour / 12 * 360), (2.5, (hour % 1) * 360))):
        piv = empty(f"tw_hand{k}", (0, -4.3, 20.5), parent=root, coll=c)
        box(f"tw_handb{k}", (0.18, 0.08, ln), (0, 0, ln / 2), Mh, 0.02, parent=piv, coll=c)
        piv.rotation_euler[1] = math.radians(ang)
    # bell in the open belfry
    bp = empty("bell_piv", (0, 0, 28.6), parent=root, coll=c)
    cyl("bell", 1.8, 2.4, (0, 0, -1.4), mat("bell_m", hexc("#b08a3a"), 0.3, metal=0.9), 24, r2=0.7, parent=bp, coll=c)
    for t in t_ring:
        for dt, a in ((-0.15, 0), (0.0, 28), (0.35, -20), (0.7, 10), (1.0, 0)):
            bp.rotation_euler[0] = math.radians(a); bp.keyframe_insert("rotation_euler", index=0, frame=F(t + dt))
    return root


# ------------------------------------------------------------------ interiors
def room(prefix, origin=(0, 0, 0), size=(16, 12, 8), wall="#c9b89a", floor="#6a4a32", coll=None, ceiling_light=True,
         light_energy=500, windows=(), doors=(), omit=()):
    """Box room, floor at z=0. windows/doors: list of (wall, offset, ...) wall in ('N','S','E','W').
    windows: (wall, off, z, w, h) -> returns sash objects; doors: (wall, off, w, h, color) -> hinge empties."""
    c = coll or collection("ROOM_" + prefix)
    ox, oy, oz = origin
    W_, D_, H_ = size
    Mw = mat(prefix + "_wall", hexc(wall), 0.9)
    box(prefix + "_floor", (W_ + 1, D_ + 1, 0.3), (ox, oy, oz - 0.15), sets.planks(prefix + "_planks", hexc(floor), hexc(floor),
        hexc("#2a1a10"), 0.5) if False else mat(prefix + "_fl", hexc(floor), 0.7), 0, coll=c)
    box(prefix + "_ceil", (W_ + 1, D_ + 1, 0.3), (ox, oy, oz + H_ + 0.15), mat(prefix + "_ce", hexc("#e8e2d6"), 0.9), 0, coll=c)
    openings = {k: [] for k in "NSEW"}
    for wnd in windows:
        openings[wnd[0]].append(("w",) + tuple(wnd[1:]))
    for d in doors:
        openings[d[0]].append(("d",) + tuple(d[1:]))
    out = {"sash": {}, "door": {}, "win": {}}
    for wl in "NSEW":
        if wl in omit:
            continue
        along_x = wl in "NS"
        span = W_ if along_x else D_
        sgn = 1 if wl in "NE" else -1
        pos = (oy + sgn * D_ / 2) if along_x else (ox + sgn * W_ / 2)
        holes = []
        for o in openings[wl]:
            if o[0] == "w":
                _, off, z, w, h = o
                holes.append((off - w / 2, off + w / 2, z - h / 2, z + h / 2))
            else:
                _, off, w, h, col = o
                holes.append((off - w / 2, off + w / 2, 0, h))
        _wall_with_holes(f"{prefix}_{wl}", along_x, pos, span, H_, holes, Mw, c, ox, oy, oz, sgn)
        for o in openings[wl]:
            if o[0] == "w":
                _, off, z, w, h = o
                cx, cy = (ox + off, pos) if along_x else (pos, oy + off)
                Mt = mat("trim_white", hexc("#e8e6e0"), 0.6)
                thick = (w + 0.4, 0.5, 0.2) if along_x else (0.5, w + 0.4, 0.2)
                box(f"{prefix}_sill{wl}{off}", thick, (cx, cy, oz + z - h / 2 - 0.1), Mt, 0.02, coll=c)
                box(f"{prefix}_head{wl}{off}", thick, (cx, cy, oz + z + h / 2 + 0.1), Mt, 0.02, coll=c)
                sz = (w, 0.1, h / 2) if along_x else (0.1, w, h / 2)
                sash = box(f"{prefix}_sash{wl}{off}", sz, (cx, cy, oz + z - h / 4), mat("glass", hexc("#9fb4d0"), 0.05,
                           alpha=0.18), 0.02, coll=c)
                box(f"{prefix}_upper{wl}{off}", sz, (cx + (0 if along_x else -0.12 * sgn), cy + (-0.12 * sgn if along_x else 0),
                    oz + z + h / 4), mat("glass", hexc("#9fb4d0"), 0.05, alpha=0.18), 0.02, coll=c)
                out["sash"][(wl, off)] = sash
                out["win"][(wl, off)] = (cx, cy, oz + z)
            else:
                _, off, w, h, col = o
                cx, cy = (ox + off, pos) if along_x else (pos, oy + off)
                hx, hy = (cx - w / 2, cy) if along_x else (cx, cy - w / 2)
                hinge = empty(f"{prefix}_dh{wl}{off}", (hx, hy, oz), coll=c, rot=(0, 0, 0 if along_x else 90))
                box(f"{prefix}_door{wl}{off}", (w, 0.2, h), (w / 2, 0, h / 2), mat("door_" + col, hexc(col), 0.6), 0.03,
                    parent=hinge, coll=c)
                iy = -0.2 * sgn if along_x else 0.2 * sgn
                kn = sphere(f"{prefix}_knob{wl}{off}", 0.14, (w - 0.35, iy, 2.0), mat("brass", hexc("#c9a240"), 0.3,
                            metal=0.9), parent=hinge, coll=c, seg=12)
                box(f"{prefix}_bolt{wl}{off}", (0.5, 0.12, 0.14), (w - 0.35, iy, 2.7), mat("steel", hexc("#9aa0aa"),
                    0.3, metal=0.9), 0.02, parent=hinge, coll=c)
                out["door"][(wl, off)] = (hinge, kn)
    if ceiling_light:
        light(prefix + "_ceil_lt", "AREA", (ox, oy, oz + H_ - 0.3), light_energy, (1.0, 0.85, 0.65), 3, rot=(0, 0, 0), coll=c)
        cyl(prefix + "_lamp", 0.7, 0.2, (ox, oy, oz + H_ - 0.12), mat("lamp_shade", (1, 0.9, 0.7), 0.4, emit=(1, 0.85, 0.6),
            estr=4.0), 24, coll=c)
    return out


def _wall_with_holes(name, along_x, pos, span, H_, holes, M, c, ox, oy, oz, sgn, thick=0.4):
    """Wall split into vertical strips around rectangular holes (a0, a1, z0, z1) in wall-local coords."""
    cuts = sorted(set([-span / 2, span / 2] + [h[0] for h in holes] + [h[1] for h in holes]))
    for i in range(len(cuts) - 1):
        a0, a1 = cuts[i], cuts[i + 1]
        if a1 - a0 < 1e-3:
            continue
        mid = (a0 + a1) / 2
        zs = [(0, H_)]
        for h in holes:
            if h[0] <= mid <= h[1]:
                zs = [(0, h[2]), (h[3], H_)]
        for k, (z0, z1) in enumerate(zs):
            if z1 - z0 < 1e-3:
                continue
            w = a1 - a0
            if along_x:
                box(f"{name}_{i}_{k}", (w, thick, z1 - z0), (ox + mid, pos + sgn * thick / 2, oz + (z0 + z1) / 2), M, 0, coll=c)
            else:
                box(f"{name}_{i}_{k}", (thick, w, z1 - z0), (pos + sgn * thick / 2, oy + mid, oz + (z0 + z1) / 2), M, 0, coll=c)


def open_sash(sash, t0=None, opened=True, h=1.5):
    z = sash.location[2]
    if opened and t0 is None:
        sash.location[2] = z + h
        return
    if t0 is not None:
        sash.location[2] = z + (h if opened else 0); sash.keyframe_insert("location", index=2, frame=F(t0))
        sash.location[2] = z + (0 if opened else h); sash.keyframe_insert("location", index=2, frame=F(t0 + 0.12))


def curtains(prefix, center, wall="N", width=3.4, h=4.0, blow=True, coll=None, color="#c86a8a"):
    M = mat("curtain_" + color, hexc(color), 0.8)
    x, y, z = center
    sgn = 1 if wall in "NE" else -1
    out = []
    for s in (-1, 1):
        if wall in "NS":
            piv = empty(f"{prefix}_cp{s}", (x + s * (width / 2 + 0.2), y - sgn * 0.5, z + h / 2), coll=coll)
            box(f"{prefix}_c{s}", (0.9, 0.08, h), (-s * 0.35, 0, -h / 2), M, 0.02, parent=piv, coll=coll)
        else:
            piv = empty(f"{prefix}_cp{s}", (x - sgn * 0.5, y + s * (width / 2 + 0.2), z + h / 2), coll=coll)
            box(f"{prefix}_c{s}", (0.08, 0.9, h), (0, -s * 0.35, -h / 2), M, 0.02, parent=piv, coll=coll)
        if blow:
            noise(piv, "rotation_euler", 0, 0.35, 6)
            noise(piv, "rotation_euler", 1, 0.25, 8)
        out.append(piv)
    return out


# Lily's bedroom (its own location). North wall (+Y) has the window, east wall (+X) the closet.
LILY = (300.0, 0.0, 0.0)
LILY_SIZE = (14, 12, 8)
LILY_WIN = (LILY[0] + 1.5, LILY[1] + 6.0, 4.0)       # window centre (on north wall)
BED = (LILY[0] - 3.5, LILY[1] + 2.0)


def lily_room(open_window=True, slam_t=None, closet_t=None, lamp=True, night=True, bright=False):
    c = collection("LILYROOM")
    R = room("lr", LILY, LILY_SIZE, wall="#b9a7c9", floor="#5a3e2e", coll=c, ceiling_light=bright, light_energy=900,
             windows=[("N", 1.5, 4.0, 3.4, 4.0)], doors=[("E", -2.0, 3.0, 6.0, "#e8e2d6"), ("S", 3.0, 2.8, 6.0, "#7a5236")])
    sash = R["sash"][("N", 1.5)]
    if open_window:
        open_sash(sash, None, True, 2.0)
    if slam_t is not None:
        z = sash.location[2]
        sash.keyframe_insert("location", index=2, frame=F(slam_t - 0.1))
        sash.location[2] = z - 2.0
        sash.keyframe_insert("location", index=2, frame=F(slam_t))
    closet, ck = R["door"][("E", -2.0)]
    # closet interior: pitch black void behind the door
    box("closet_void", (2.0, 3.2, 6.2), (LILY[0] + 8.1, LILY[1] - 2.0, 3.1), mat("void", (0, 0, 0), 1.0, spec=0.0), 0, coll=c)
    if closet_t is not None:
        closet.keyframe_insert("rotation_euler", index=2, frame=F(closet_t))
        closet.rotation_euler[2] = math.radians(90 + 35)
        closet.keyframe_insert("rotation_euler", index=2, frame=F(closet_t + 1.6))
        set_interp(closet, "rotation_euler", F(closet_t), "BEZIER", "EASE_IN_OUT")
    # bed
    bx, by = BED
    Mbed = mat("bed_wood", hexc("#6a4a32"), 0.6)
    box("bed_frame", (4.6, 8.4, 1.2), (bx, by - 1.0, 0.6), Mbed, 0.08, coll=c)
    box("bed_head", (4.6, 0.4, 3.4), (bx, by + 3.0, 1.7), Mbed, 0.08, coll=c)
    box("mattress", (4.2, 7.8, 0.6), (bx, by - 1.0, 1.5), mat("sheet", hexc("#f2e8f0"), 0.9), 0.15, coll=c)
    box("blanket", (4.4, 5.0, 0.5), (bx, by - 2.4, 1.85), mat("blanket", hexc("#e86aa0"), 0.85), 0.2, coll=c)
    box("pillow", (3.0, 1.4, 0.6), (bx, by + 2.1, 2.0), mat("pillow", hexc("#ffffff"), 0.9), 0.25, coll=c)
    # nightstand + nightlight
    box("stand", (1.6, 1.6, 2.2), (bx + 3.4, by + 2.4, 1.1), Mbed, 0.06, coll=c)
    if lamp:
        sphere("nightlight", 0.4, (bx + 3.4, by + 2.4, 2.6), mat("nl", (1, 0.8, 0.5), 0.3, emit=(1.0, 0.7, 0.4), estr=8), seg=16, coll=c)
        light("nl_lt", "POINT", (bx + 3.4, by + 1.8, 3.2), 140, (1.0, 0.7, 0.4), 0.3, coll=c, shadow=False)
    # teddy bear on the floor, rug
    cyl("rug", 3.0, 0.05, (LILY[0] + 1, LILY[1] - 1, 0.03), mat("rug", hexc("#6a8ac8"), 0.9), 32, coll=c)
    teddy("teddy", (LILY[0] + 2.5, LILY[1] - 3.5, 0), c)
    # moonlight through the window + curtains
    if night:
        light("moon_in", "AREA", (LILY_WIN[0], LILY_WIN[1] + 4, LILY_WIN[2] + 3), 900, (0.55, 0.65, 1.0), 4,
              target=(LILY_WIN[0], LILY_WIN[1] - 6, 0), coll=c)
    curtains("lc", (LILY_WIN[0], LILY_WIN[1], LILY_WIN[2] + 2.3), "N", 3.4, 4.6, blow=open_window, coll=c)
    return dict(sash=sash, closet=closet)


def teddy(name, loc, coll=None):
    root = empty(name, loc, coll=coll)
    M = mat("teddy", hexc("#a8743a"), 0.9)
    sphere(name + "_b", 0.55, (0, 0, 0.55), M, (1, 0.9, 1.1), parent=root, coll=coll, seg=16)
    sphere(name + "_h", 0.42, (0, 0, 1.4), M, parent=root, coll=coll, seg=16)
    for s in (-1, 1):
        sphere(f"{name}_e{s}", 0.16, (s * 0.32, 0, 1.75), M, parent=root, coll=coll, seg=10)
    return root


# ------------------------------------------------------------------ the Visitor
class Visitor:
    """Very tall, thin, dark grey body; pale head with huge black eyes and a too-wide smile;
    arms ending in long pale fingers (5 per hand)."""

    def __init__(self, loc=(0, 0, 0), rot=0, scale=1.0, name="Visitor", coll=None, smile=True):
        c = self.c = coll or collection("VISITOR")
        self.name = name
        self.root = empty(name + "_root", loc, coll=c, rot=(0, 0, rot))
        self.root.scale = (scale,) * 3
        Mb = mat("vis_body", hexc("#16161c"), 0.8)
        Mp = mat("vis_pale", hexc("#d9d6d0"), 0.55)
        self.hip = empty(name + "_hip", (0, 0, 7.0), parent=self.root, coll=c)
        box(name + "_torso", (1.5, 0.8, 5.0), (0, 0, 2.5), Mb, 0.2, parent=self.hip, coll=c)
        for s, nm in ((1, "L"), (-1, "R")):
            piv = empty(f"{name}_hp{nm}", (s * 0.45, 0, 0), parent=self.hip, coll=c)
            box(f"{name}_leg{nm}", (0.45, 0.45, 7.0), (0, 0, -3.5), Mb, 0.1, parent=piv, coll=c)
            setattr(self, "hp" + nm, piv)
        self.neck = empty(name + "_neck", (0, 0, 5.0), parent=self.hip, coll=c)
        cyl(name + "_neckb", 0.22, 1.6, (0, 0, 0.8), Mb, 10, parent=self.neck, coll=c)
        self.head = empty(name + "_head", (0, 0, 2.6), parent=self.neck, coll=c)
        sphere(name + "_skull", 1.15, (0, 0, 0), Mp, (0.95, 0.9, 1.25), parent=self.head, coll=c, seg=24)
        Me = mat("vis_eye", (0, 0, 0), 0.05, spec=1.0)
        for s in (-1, 1):
            sphere(f"{name}_eye{s}", 0.42, (s * 0.45, -0.85, 0.3), Me, (1.0, 0.4, 1.45), rot=(0, s * -12, 0),
                   parent=self.head, coll=c, seg=16)
            sphere(f"{name}_glint{s}", 0.06, (s * 0.38, -1.1, 0.55), mat("glint", (1, 1, 1), 0.3, emit=(1, 1, 1), estr=8),
                   parent=self.head, coll=c, seg=8)
        if smile:
            Mm = mat("vis_mouth", hexc("#120808"), 0.6)
            Mt = mat("vis_teeth", hexc("#f4f0e2"), 0.3)
            for i in range(11):
                a = math.radians(-70 + i * 14)
                x, y, z = math.sin(a) * 0.95, -math.cos(a) * 0.95 * 0.92, -0.55 + (abs(math.sin(a)) ** 1.6) * 0.45
                box(f"{name}_m{i}", (0.3, 0.14, 0.34), (x, y, z), Mm, 0.03, rot=(0, 0, math.degrees(a)), parent=self.head, coll=c)
                box(f"{name}_t{i}", (0.22, 0.15, 0.13), (x * 1.01, y * 1.01, z + 0.06), Mt, 0.02, rot=(0, 0, math.degrees(a)),
                    parent=self.head, coll=c)
        # arms + fingers
        self.sh = {}
        self.fingers = {}
        for s, nm in ((1, "L"), (-1, "R")):
            sh = empty(f"{name}_sh{nm}", (s * 0.95, 0, 4.6), parent=self.hip, coll=c)
            box(f"{name}_arm{nm}", (0.35, 0.35, 5.5), (0, 0, -2.75), Mb, 0.08, parent=sh, coll=c)
            hand = empty(f"{name}_hand{nm}", (0, 0, -5.6), parent=sh, coll=c)
            sphere(f"{name}_palm{nm}", 0.32, (0, 0, 0), Mp, (1, 0.5, 1), parent=hand, coll=c, seg=12)
            fs = []
            for k in range(5):
                fp = empty(f"{name}_fp{nm}{k}", ((k - 2) * 0.16, 0, -0.2), parent=hand, coll=c,
                           rot=(0, (k - 2) * 6 * s, 0))
                cyl(f"{name}_f{nm}{k}", 0.06, 2.4 - abs(k - 2) * 0.25, (0, 0, -1.1), Mp, 8, r2=0.035, parent=fp, coll=c)
                fs.append(fp)
            self.sh[nm] = sh
            self.fingers[nm] = fs
        noise(self.head, "rotation_euler", 1, 0.06, 18)

    def arms(self, t, L=(0, 8), R=(0, 8)):
        f = F(t)
        for nm, (fwd, out), s in (("L", L, 1), ("R", R, -1)):
            p = self.sh[nm]
            p.rotation_euler = (math.radians(-fwd), math.radians(-out * s), 0)
            p.keyframe_insert("rotation_euler", frame=f)

    def curl(self, t, k=1.0, nm=("L", "R")):
        """Fingers curl forward (k=0 straight, 1 hooked)."""
        for n in nm:
            for fp in self.fingers[n]:
                fp.rotation_euler[0] = math.radians(-80 * k)
                fp.keyframe_insert("rotation_euler", index=0, frame=F(t))

    def head_tilt(self, t, deg):
        self.head.rotation_euler[1] = math.radians(deg)
        self.head.keyframe_insert("rotation_euler", index=1, frame=F(t))

    def at(self, t, loc, interp="BEZIER"):
        self.root.location = loc
        self.root.keyframe_insert("location", frame=F(t))
        set_interp(self.root, "location", F(t), interp)

    def walk(self, t0, t1, p0, p1, rate=1.4):
        self.at(t0, p0, "LINEAR"); self.at(t1, p1, "LINEAR")
        t, k = t0, 0
        while t <= t1:
            s = 1 if k % 2 == 0 else -1
            for nm, sg in (("L", 1), ("R", -1)):
                piv = getattr(self, "hp" + nm)
                piv.rotation_euler[0] = math.radians(-22 * s * sg)
                piv.keyframe_insert("rotation_euler", index=0, frame=F(t))
            t += 1 / (rate * 2); k += 1

    def knock(self, t, nm="R"):
        p = self.sh[nm]
        for dt, a in ((-0.12, 70), (0.0, 95), (0.1, 70)):
            p.rotation_euler[0] = math.radians(-a); p.keyframe_insert("rotation_euler", index=0, frame=F(t + dt))


# ------------------------------------------------------------------ cast
def lily(t0, t1, expr="sleepy", asleep=False):
    L = chars.Char("Lily", skin="#f1dfc6", shirt="#f4a8c8", pants="#f4a8c8", hair="bob", hair_color="#c87a3a",
                   face="girl", sleeves="long", scale=0.78, extras=())
    _live(L, t0, t1, expr)
    if asleep:
        L.face(t0, eyes="closed", mouth="flat")
    return L


def lie_in_bed(L, t):
    """Lily lying on her back in the bed, head on the pillow (+Y end)."""
    bx, by = BED
    L.pose(t, loc=(bx, by - 1.5, 2.2), rot=0)
    L.root.rotation_euler[0] = math.radians(-90)
    L.root.keyframe_insert("rotation_euler", index=0, frame=F(t))


def barnes(t0, t1, expr="happy"):
    B = chars.Char("Barnes", skin="#e9cdb4", shirt="#6a7a4a", pants="#3a342c", hair="bald", face="mustache",
                   sleeves="long", extras=("glasses",))
    return _live(B, t0, t1, expr)


def cat_flap(name, door_hinge, coll=None, open_=True):
    """Small swinging flap at the bottom of a door (door built by house2/room: local x 0..w)."""
    piv = empty(name, (1.2, -0.12, 1.0), parent=door_hinge, coll=coll)
    box(name + "_f", (1.0, 0.06, 0.9), (0, 0, -0.45), mat("flap", hexc("#9aa0aa"), 0.4), 0.02, parent=piv, coll=coll)
    if open_:
        piv.rotation_euler[0] = math.radians(-50)
        noise(piv, "rotation_euler", 0, 0.25, 4)
    return piv


def sill_hands(prefix, sill, t_curl=None, coll=None, curled=True, spread=1.1):
    """Two pale hands gripping a windowsill from outside. sill = (x, y_outer_edge, z_top); fingers reach -Y into the room."""
    Mp = mat("vis_pale", hexc("#d9d6d0"), 0.55)
    out = []
    for s in (-1, 1):
        hand = empty(f"{prefix}_h{s}", (sill[0] + s * spread, sill[1] + 0.6, sill[2] + 0.1), coll=coll)
        sphere(f"{prefix}_palm{s}", 0.3, (0, 0, 0), Mp, (1.1, 1.0, 0.45), parent=hand, coll=coll, seg=12)
        for k in range(5):
            base = empty(f"{prefix}_fb{s}{k}", ((k - 2) * 0.17, -0.2, 0), parent=hand, coll=coll)
            ln = 1.5 - abs(k - 2) * 0.18
            seg1 = empty(f"{prefix}_f1{s}{k}", (0, 0, 0), parent=base, coll=coll)
            cyl(f"{prefix}_fa{s}{k}", 0.055, ln, (0, -ln / 2, 0), Mp, 8, rot=(90, 0, 0), parent=seg1, coll=coll)
            tip = empty(f"{prefix}_f2{s}{k}", (0, -ln, 0), parent=seg1, coll=coll)
            cyl(f"{prefix}_fc{s}{k}", 0.045, ln * 0.8, (0, -ln * 0.4, 0), Mp, 8, rot=(90, 0, 0), parent=tip, coll=coll, r2=0.02)
            ang = 70 if curled else 0
            if t_curl is not None:
                tip.rotation_euler[0] = 0; tip.keyframe_insert("rotation_euler", index=0, frame=F(t_curl[0] + k * 0.08))
                tip.rotation_euler[0] = math.radians(70); tip.keyframe_insert("rotation_euler", index=0, frame=F(t_curl[1] + k * 0.08))
            else:
                tip.rotation_euler[0] = math.radians(ang)
            noise(base, "rotation_euler", 0, 0.05, 10 + k)
        out.append(hand)
    return out
