"""candle_guard sets + props: the night town square, the 12 candles, the Snuffer, Mr. Hollis.
Coordinates: candle pedestal at the origin, the forest is to the north (+Y), the open road to the
forest runs north from the square. Characters face -Y at rot=0, so rot=180 faces the forest."""
import math, random
import bpy
from mathutils import Vector
from rbx.core import (D, F, mat, hexc, box, cyl, sphere, plane, card, empty, light, collection, noise,
                      set_interp, fcurves)
from rbx import chars, sets, fx
from rbx.story import _live

PED_R, PED_H = 3.2, 1.6          # pedestal
RING_R = 2.45                     # candle ring radius
C_H, C_R = 1.15, 0.2              # candle height / radius
FLAME_Z = PED_H + C_H + 0.2
EDDIE_SPOT = (0.0, -5.2, 0.0)     # where Eddie guards (south side, facing the forest)
FOREST_Y = 62.0

NIGHT_BLUE = (0.010, 0.016, 0.045)


# ------------------------------------------------------------------ world + lights
def night_world(strength=1.0, glow=0.0):
    """Dark blue gradient sky; glow>0 lifts it toward dawn."""
    w = D.worlds.new("Night"); bpy.context.scene.world = w
    w.use_nodes = True; nt = w.node_tree
    bg = next(n for n in nt.nodes if n.type == "BACKGROUND")
    tc = nt.nodes.new("ShaderNodeTexCoord"); sep = nt.nodes.new("ShaderNodeSeparateXYZ")
    nt.links.new(tc.outputs["Generated"], sep.inputs[0])
    cr = nt.nodes.new("ShaderNodeValToRGB")
    lo = Vector((0.03, 0.05, 0.13)).lerp(Vector((0.95, 0.55, 0.45)), glow)
    hi = Vector((0.004, 0.008, 0.03)).lerp(Vector((0.25, 0.4, 0.8)), glow)
    cr.color_ramp.elements[0].position = 0.48; cr.color_ramp.elements[0].color = (*lo, 1)
    cr.color_ramp.elements[1].position = 0.72; cr.color_ramp.elements[1].color = (*hi, 1)
    nt.links.new(sep.outputs["Z"], cr.inputs[0]); nt.links.new(cr.outputs[0], bg.inputs[0])
    bg.inputs[1].default_value = strength
    return bg


def moonlight(strength=0.35, color=(0.55, 0.65, 1.0)):
    return light("moon_sun", "SUN", (0, 0, 60), strength, color, 3, rot=(55, 0, -150))


# ------------------------------------------------------------------ the square
def square(coll=None, houses=True, forest=True, lamps=True, snow=True):
    c = coll or collection("SQUARE")
    Msnow = mat("snow", hexc("#c9d3e6"), 0.85)
    box("ground", (400, 400, 0.4), (0, 0, -0.2), Msnow, 0, coll=c)
    Mcob = mat("cobble", hexc("#5a5d68"), 0.8)
    cyl("plaza", 16, 0.08, (0, 0, 0.04), Mcob, 48, coll=c)
    Mring = mat("plaza_ring", hexc("#7a7d88"), 0.7)
    cyl("plaza_ring", 16.6, 0.06, (0, 0, 0.03), Mring, 48, coll=c)
    # pedestal
    Mstone = mat("ped_stone", hexc("#8b8d96"), 0.75)
    cyl("ped_base", PED_R + 0.5, 0.45, (0, 0, 0.22), Mstone, 40, bev=0.06, coll=c)
    cyl("ped", PED_R, PED_H, (0, 0, PED_H / 2), Mstone, 40, bev=0.08, coll=c)
    cyl("ped_top", PED_R + 0.2, 0.18, (0, 0, PED_H), mat("ped_top", hexc("#a3a5ae"), 0.6), 40, bev=0.04, coll=c)
    # old brass plate on the front
    box("ped_plate", (1.8, 0.06, 0.7), (0, -PED_R - 0.01, 0.95), mat("brass", hexc("#b08a3a"), 0.35, metal=0.8), 0.02, coll=c)
    if lamps:
        for i in range(6):
            a = math.radians(30 + i * 60)
            street_lamp(f"lamp{i}", (math.sin(a) * 13.5, math.cos(a) * 13.5, 0), c)
    if houses:
        town_ring(c)
    if forest:
        forest_ring(c)
    sphere("moon", 6, (-90, 240, 95), mat("moon_m", (1, 1, 1), 0.5, emit=hexc("#dfe8ff"), estr=6.0), seg=32, coll=c)
    return c


def street_lamp(name, loc, coll, on=True):
    Mp = mat("lamp_pole", hexc("#23252c"), 0.5, metal=0.6)
    root = empty(name, loc, coll=coll)
    cyl(name + "_pole", 0.14, 7.0, (0, 0, 3.5), Mp, 12, parent=root, coll=coll)
    box(name + "_cap", (0.9, 0.9, 0.25), (0, 0, 7.75), Mp, 0.05, parent=root, coll=coll)
    Mg = mat("lamp_glow", (1, 0.85, 0.55), 0.3, emit=(1.0, 0.78, 0.45), estr=12.0)
    bulb = box(name + "_glass", (0.6, 0.6, 0.6), (0, 0, 7.3), Mg, 0.05, parent=root, coll=coll)
    lt = light(name + "_lt", "POINT", (loc[0], loc[1], 7.0), 900 if on else 0, (1.0, 0.75, 0.45), 0.4, coll=coll)
    return root, bulb, lt


def lamp_off(name, t):
    """Flicker a street lamp, then kill it at t."""
    bulb = D.objects.get(name + "_glass"); lt = D.objects.get(name + "_lt")
    if not bulb or not lt:
        return
    seq = [(-0.25, 900), (-0.2, 80), (-0.15, 900), (-0.08, 50), (-0.04, 700), (0.0, 0)]
    for dt, e in seq:
        lt.data.energy = e
        lt.data.keyframe_insert("energy", frame=F(t + dt))
    for fc in fcurves(lt.data.animation_data.action):
        for kp in fc.keyframe_points:
            kp.interpolation = "CONSTANT"
    sets.set_obj_visible(bulb, t - 1 / 30, True)
    sets.set_obj_visible(bulb, t, False)


HOUSE_COLS = ["#5b4a6a", "#4a5a6e", "#6a5a4a", "#4f5f58", "#5f4a4a", "#56566a"]


def house(name, loc, yaw, coll, seed=0, door_open=None, boards=True, lit=False):
    """Small blocky house whose door faces the square. door_open=(t0, t1) swings the door."""
    rnd = random.Random(seed)
    root = empty(name, loc, coll=coll, rot=(0, 0, yaw))  # yaw in degrees
    w, d, h = rnd.uniform(9, 11), rnd.uniform(8, 9), rnd.uniform(7, 9)
    Mw = mat("house_" + str(seed % 6), hexc(HOUSE_COLS[seed % 6]), 0.85)
    box(name + "_body", (w, d, h), (0, 0, h / 2), Mw, 0.12, parent=root, coll=coll)
    Mr = mat("roof_dark", hexc("#2a1f24"), 0.7)
    for s in (-1, 1):
        box(f"{name}_roof{s}", (w + 1.2, d * 0.62, 0.5), (0, s * d * 0.25, h + d * 0.18), Mr, 0.1,
            rot=(s * -35, 0, 0), parent=root, coll=coll)
    # door on the -Y face (toward the square)
    Mdoor = mat("door_wood", hexc("#3a2618"), 0.7)
    box(name + "_doorhole", (2.0, 0.1, 3.6), (0, -d / 2 - 0.01, 1.8), mat("door_dark", hexc("#050506"), 1.0), 0,
        parent=root, coll=coll)
    hinge = empty(name + "_hinge", (-1.0, -d / 2 - 0.08, 0), parent=root, coll=coll)
    box(name + "_door", (2.0, 0.18, 3.6), (1.0, 0, 1.8), Mdoor, 0.04, parent=hinge, coll=coll)
    if door_open:
        t0, t1 = door_open
        hinge.rotation_euler[2] = 0; hinge.keyframe_insert("rotation_euler", index=2, frame=F(t0))
        hinge.rotation_euler[2] = math.radians(-70); hinge.keyframe_insert("rotation_euler", index=2, frame=F(t1))
    # windows: dark glass with nailed boards (or a faint warm glow)
    Mg = mat("win_lit", (1, 0.8, 0.5), 0.3, emit=(1.0, 0.7, 0.4), estr=1.5) if lit else mat("win_dark", hexc("#0c0f18"), 0.2)
    Mb = mat("board", hexc("#6a4a2e"), 0.8)
    for sx in (-1, 1):
        x = sx * w * 0.3
        box(f"{name}_win{sx}", (1.8, 0.1, 1.8), (x, -d / 2 - 0.02, 4.4), Mg, 0.02, parent=root, coll=coll)
        if boards:
            for k, rz in enumerate((25, -25)):
                box(f"{name}_bd{sx}{k}", (2.3, 0.14, 0.32), (x, -d / 2 - 0.1, 4.4), Mb, 0.02, rot=(0, rz, 0),
                    parent=root, coll=coll)
    return root, hinge


HOUSE_SPOTS = []
for _i in range(11):
    _a = math.radians(-150 + _i * 30)       # leave a gap to the north for the forest road
    if abs(_a) < math.radians(20):
        continue
    HOUSE_SPOTS.append((math.sin(_a) * 27, math.cos(_a) * 27, _a))


def town_ring(coll, door_open=None):
    out = []
    for i, (x, y, a) in enumerate(HOUSE_SPOTS):
        yaw = -math.degrees(a)
        r, hg = house(f"house{i}", (x, y, 0), yaw, coll, seed=i,
                      door_open=(door_open[0] + i * 0.05, door_open[1] + i * 0.05) if door_open else None)
        out.append(hg)
    return out


def forest_ring(coll, seed=11):
    rnd = random.Random(seed)
    Mt = mat("pine", hexc("#0f1f1c"), 0.9)
    Mtr = mat("trunk", hexc("#1d1410"), 0.9)
    k = 0
    for ring in range(3):
        n = 40 + ring * 14
        for j in range(n):
            a = j / n * math.tau + rnd.uniform(-0.05, 0.05)
            r = 48 + ring * 9 + rnd.uniform(-3, 3)
            x, y = math.sin(a) * r, math.cos(a) * r
            if y < 10 and ring == 0 and rnd.random() < 0.4:
                continue
            h = rnd.uniform(12, 20)
            cyl(f"tr{k}", 0.4, 3, (x, y, 1.5), Mtr, 6, coll=coll)
            cyl(f"pn{k}", rnd.uniform(3.0, 4.2), h, (x, y, 3 + h / 2), Mt, 8, r2=0.05, coll=coll)
            k += 1


# ------------------------------------------------------------------ candles
class Candles:
    """The 12 candles. lit: set of candle numbers (1..12) burning at the start of the shot."""

    def __init__(self, lit=range(1, 13), coll=None, light_energy=55, center=(0, 0, 0), scale=1.0):
        self.c = coll or collection("CANDLES")
        self.flames, self.lights, self.pos = {}, {}, {}
        cx, cy, cz = center
        Mw = mat("wax", hexc("#efe4c8"), 0.55, emit=hexc("#f3c88a"), estr=0.15)
        Mwick = mat("wick", hexc("#151210"), 0.9)
        Mf = mat("flame", (1, 0.7, 0.3), 0.3, emit=(1.0, 0.55, 0.15), estr=45.0)
        Mfc = mat("flame_core", (1, 1, 0.9), 0.3, emit=(1.0, 0.92, 0.7), estr=80.0)
        s = scale
        for n in range(1, 13):
            a = math.radians((n - 1) * 30)            # clock layout: candle 12 at the back (+Y)... 1 at 30 deg
            x, y = cx + math.sin(a) * RING_R * s, cy + math.cos(a) * RING_R * s
            base_z = cz + PED_H
            h = C_H * s * (0.85 + 0.3 * ((n * 37) % 10) / 10)
            cyl(f"candle{n}", C_R * s, h, (x, y, base_z + h / 2), Mw, 16, bev=0.03, coll=self.c)
            cyl(f"drip{n}", C_R * s * 1.08, 0.1 * s, (x, y, base_z + h - 0.05 * s), Mw, 16, coll=self.c)
            cyl(f"wick{n}", 0.025 * s, 0.18 * s, (x, y, base_z + h + 0.07 * s), Mwick, 6, coll=self.c)
            fz = base_z + h + 0.3 * s
            root = empty(f"flame{n}", (x, y, fz), coll=self.c)
            sphere(f"flame{n}_o", 0.11 * s, (0, 0, 0), Mf, (1, 1, 2.1), parent=root, coll=self.c, seg=12)
            sphere(f"flame{n}_i", 0.055 * s, (0, 0, -0.05 * s), Mfc, (1, 1, 1.8), parent=root, coll=self.c, seg=10)
            noise(root, "rotation_euler", 0, 0.12, 2.5)
            noise(root, "rotation_euler", 1, 0.12, 3.0)
            noise(root, "scale", 2, 0.12, 2.0)
            lt = light(f"cl{n}", "POINT", (x, y, fz + 0.1), light_energy * s * s, (1.0, 0.55, 0.2), 0.08, coll=self.c)
            self.flames[n], self.lights[n], self.pos[n] = root, lt, (x, y, fz)
            if n not in lit:
                self._set(n, 1, False)
        self.energy = light_energy * s * s

    def _set(self, n, frame, on):
        fl, lt = self.flames[n], self.lights[n]
        fl.scale = (1, 1, 1) if on else (0.001,) * 3
        fl.keyframe_insert("scale", frame=frame)
        lt.data.energy = self.energy if on else 0.0
        lt.data.keyframe_insert("energy", frame=frame)

    def out(self, n, t, smoke=True):
        """Candle n dies at t: flame stretches sideways, shrinks to nothing, a smoke wisp rises."""
        fl, lt = self.flames[n], self.lights[n]
        fl.scale = (1, 1, 1); fl.keyframe_insert("scale", frame=F(t - 0.12))
        fl.rotation_euler[0] = 0; fl.keyframe_insert("rotation_euler", index=0, frame=F(t - 0.12))
        fl.scale = (0.7, 0.7, 1.6); fl.keyframe_insert("scale", frame=F(t - 0.04))
        fl.rotation_euler[0] = math.radians(-50); fl.keyframe_insert("rotation_euler", index=0, frame=F(t - 0.04))
        fl.scale = (0.001,) * 3; fl.keyframe_insert("scale", frame=F(t + 0.03))
        lt.data.energy = self.energy; lt.data.keyframe_insert("energy", frame=F(t - 0.05))
        lt.data.energy = 0.0; lt.data.keyframe_insert("energy", frame=F(t + 0.03))
        if smoke:
            wisp(f"wisp{n}_{int(t * 100)}", self.pos[n], t, self.c)

    def light_up(self, n, t):
        fl, lt = self.flames[n], self.lights[n]
        fl.scale = (0.001,) * 3; fl.keyframe_insert("scale", frame=F(t - 0.03))
        fl.scale = (1.5, 1.5, 1.7); fl.keyframe_insert("scale", frame=F(t + 0.06))
        fl.scale = (1, 1, 1); fl.keyframe_insert("scale", frame=F(t + 0.2))
        lt.data.energy = 0.0; lt.data.keyframe_insert("energy", frame=F(t - 0.03))
        lt.data.energy = self.energy * 2; lt.data.keyframe_insert("energy", frame=F(t + 0.05))
        lt.data.energy = self.energy; lt.data.keyframe_insert("energy", frame=F(t + 0.25))

    def shrink(self, n, t0, t1, k=0.4):
        fl, lt = self.flames[n], self.lights[n]
        fl.scale = (1, 1, 1); fl.keyframe_insert("scale", frame=F(t0))
        fl.scale = (k, k, k); fl.keyframe_insert("scale", frame=F(t1))
        lt.data.energy = self.energy; lt.data.keyframe_insert("energy", frame=F(t0))
        lt.data.energy = self.energy * k; lt.data.keyframe_insert("energy", frame=F(t1))


def wisp(name, p, t, coll, n=5, rise=2.2, seed=0):
    rnd = random.Random(hash(name) % 1000 + seed)
    Ms = mat("wisp_thin", (0.6, 0.62, 0.68), 0.9, emit=(0.15, 0.16, 0.2), estr=0.2, alpha=0.22)
    for i in range(n):
        d = i * 0.1
        ob = sphere(f"{name}_{i}", 0.07, p, Ms, coll=coll, seg=12)
        ob.scale = (0.01,) * 3
        ob.keyframe_insert("scale", frame=F(t + d - 0.02))
        ob.keyframe_insert("location", frame=F(t + d))
        ob.scale = (0.8, 0.8, 2.2)
        ob.keyframe_insert("scale", frame=F(t + d + 0.25))
        ob.location = (p[0] + rnd.uniform(-0.5, 0.5), p[1] + rnd.uniform(-0.5, 0.5), p[2] + rise * rnd.uniform(0.7, 1.2))
        ob.scale = (1.3, 1.3, 2.6)
        ob.keyframe_insert("location", frame=F(t + d + 1.2))
        ob.scale = (0.01,) * 3
        ob.keyframe_insert("scale", frame=F(t + d + 1.4))


# ------------------------------------------------------------------ the Snuffer
class Snuffer:
    """Tall robed shadow. No legs: the robe dissolves into smoke. Blade arms. Sharp slit eyes
    (start closed: eyes_open(t) snaps them open). Front faces -Y at rot=0."""

    def __init__(self, loc=(0, 30, 0), rot=0, coll=None, scale=1.0, eyes=False, name="Snuffer"):
        self.name = name
        c = self.c = coll or collection("SNUFFER")
        self.root = empty(name + "_root", loc, coll=c, rot=(0, 0, rot))
        self.root.scale = (scale,) * 3
        self.body = empty(name + "_body", (0, 0, 0), parent=self.root, coll=c)
        Mr = mat("robe", hexc("#07070a"), 0.95)
        Mr2 = mat("robe_edge", hexc("#111118"), 0.9)
        # robe: wide at the hem, narrow at the shoulders
        cyl(name + "_robe", 2.2, 8.5, (0, 0, 5.2), Mr, 24, parent=self.body, coll=c, r2=1.15)
        cyl(name + "_hem", 2.35, 0.6, (0, 0, 1.2), Mr2, 24, parent=self.body, coll=c, r2=2.2)
        # tattered hem strips
        for i in range(14):
            a = i / 14 * math.tau
            box(f"{name}_tat{i}", (0.7, 0.18, 1.4 + (i % 3) * 0.4), (math.sin(a) * 2.25, math.cos(a) * 2.25, 0.6), Mr, 0.03,
                rot=(0, 0, -math.degrees(a)), parent=self.body, coll=c)
        # hood
        self.head = empty(name + "_head", (0, 0, 10.0), parent=self.body, coll=c)
        sphere(name + "_hood", 1.45, (0, 0.15, 0.5), Mr, (1.0, 1.05, 1.35), parent=self.head, coll=c, seg=24)
        cyl(name + "_hoodtip", 0.9, 1.6, (0, 0.5, 2.0), Mr, 12, r2=0.05, rot=(-25, 0, 0), parent=self.head, coll=c)
        # the void inside the hood (pure black) + rim
        sphere(name + "_void", 1.0, (0, -0.75, 0.35), mat("void", (0, 0, 0), 1.0, spec=0.0), (0.95, 0.5, 1.15),
               parent=self.head, coll=c, seg=20)
        cyl(name + "_rim", 1.2, 0.25, (0, -1.0, 0.4), Mr2, 24, rot=(90, 0, 0), parent=self.head, coll=c, r2=1.3)
        # sharp slit eyes
        Me = mat("snuff_eye", (1, 1, 1), 0.3, emit=hexc("#e8f4ff"), estr=60.0)
        self.eyes = []
        for sx in (-1, 1):
            e = empty(f"{name}_eyep{sx}", (sx * 0.38, -1.32, 0.55), parent=self.head, coll=c)
            sphere(f"{name}_eye{sx}", 0.26, (0, 0, 0), Me, (1.0, 0.25, 0.12), rot=(0, sx * -18, 0), parent=e, coll=c, seg=12)
            self.eyes.append(e)
            e.scale = (1, 1, 1) if eyes else (1, 1, 0.01)
        self.eye_light = light(name + "_eyelt", "POINT", (0, -1.8, 0.6), 0, (0.8, 0.9, 1.0), 0.3, coll=c)
        self.eye_light.parent = self.head
        self.eye_light.location = (0, -1.8, 0.6)
        if eyes:
            self.eye_light.data.energy = 40
        # faint frosty mouth glow
        self.mouth = sphere(name + "_mouth", 0.32, (0, -1.25, -0.25), mat("frost", (0.8, 0.9, 1.0), 0.4,
                            emit=hexc("#9fc8ff"), estr=6.0), (1.2, 0.3, 0.5), parent=self.head, coll=c, seg=12)
        # blade arms: shoulder pivots, long tapering spikes
        self.shL = empty(name + "_shL", (1.3, 0, 8.6), parent=self.body, coll=c)
        self.shR = empty(name + "_shR", (-1.3, 0, 8.6), parent=self.body, coll=c)
        Mb = mat("blade", hexc("#0d0d12"), 0.35, metal=0.5)
        for piv, nm in ((self.shL, "L"), (self.shR, "R")):
            cyl(f"{name}_sleeve{nm}", 0.55, 2.4, (0, 0, -1.2), Mr, 12, parent=piv, coll=c, r2=0.4)
            cyl(f"{name}_arm{nm}", 0.32, 4.5, (0, 0, -4.4), Mb, 8, parent=piv, coll=c, r2=0.12)
            cyl(f"{name}_blade{nm}", 0.12, 3.2, (0, 0, -8.2), Mb, 6, parent=piv, coll=c, r2=0.0)
            for k, (ang, ln) in enumerate(((22, 2.0), (-22, 1.6))):
                cyl(f"{name}_claw{nm}{k}", 0.08, ln, (math.sin(math.radians(ang)) * 0.6, 0, -6.9),
                    Mb, 6, parent=piv, coll=c, r2=0.0, rot=(0, ang + 180, 0))
        self.arms(1, (8, 12), (8, 12))
        # smoke feet: dark puffs pooling and churning under the hem
        Msm = mat("shadow_smoke", hexc("#0a0a10"), 1.0, alpha=0.75)
        Msm2 = mat("shadow_smoke2", hexc("#1a1a24"), 1.0, alpha=0.45)
        rnd = random.Random(3)
        self.smoke = []
        for i in range(18):
            a = rnd.uniform(0, math.tau); r = rnd.uniform(0.3, 2.8)
            ob = sphere(f"{name}_sm{i}", rnd.uniform(0.6, 1.2), (math.sin(a) * r, math.cos(a) * r, rnd.uniform(0.0, 1.4)),
                        Msm if i % 2 else Msm2, (1.3, 1.3, 0.8), parent=self.body, coll=c, seg=12)
            for ax in range(3):
                noise(ob, "location", ax, 0.35, 10 + i)
            noise(ob, "scale", 0, 0.2, 8 + i)
            self.smoke.append(ob)
        noise(self.body, "location", 2, 0.12, 30)
        noise(self.body, "rotation_euler", 1, 0.02, 40)

    def arms(self, t, L=(8, 12), R=(8, 12)):
        """(forward, out) degrees like Char.pose."""
        f = F(t) if t > 1 else 1
        for piv, (fwd, out), side in ((self.shL, L, 1), (self.shR, R, -1)):
            piv.rotation_euler = (math.radians(-fwd), math.radians(-out * side), 0)
            piv.keyframe_insert("rotation_euler", frame=f)

    def reach(self, t, k=1.0):
        self.arms(t, (70 * k, 18), (55 * k, 22))

    def at(self, t, loc, rot=None, interp="BEZIER"):
        self.root.location = loc
        self.root.keyframe_insert("location", frame=F(t))
        set_interp(self.root, "location", F(t), interp)
        if rot is not None:
            self.root.rotation_euler[2] = math.radians(rot)
            self.root.keyframe_insert("rotation_euler", index=2, frame=F(t))

    def step(self, t, p0, p1, dur=0.18):
        """Teleport-like lurch from p0 to p1 ending at t (the THUD), holding still before and after."""
        self.at(t - dur, p0, interp="CONSTANT")
        self.at(t - dur * 0.6, p0)
        self.at(t, p1)
        for i, ob in enumerate(self.smoke[:6]):
            pass

    def eyes_open(self, t, dur=0.08):
        for e in self.eyes:
            e.scale = (1, 1, 0.01); e.keyframe_insert("scale", frame=F(t))
            e.scale = (1.1, 1, 1.4); e.keyframe_insert("scale", frame=F(t + dur))
            e.scale = (1, 1, 1); e.keyframe_insert("scale", frame=F(t + dur + 0.1))
        ld = self.eye_light.data
        ld.energy = 0; ld.keyframe_insert("energy", frame=F(t))
        ld.energy = 40; ld.keyframe_insert("energy", frame=F(t + dur))

    def breath(self, t, dur=1.0, n=10, seed=0):
        """Frosty breath puffs blowing forward (-Y local) out of the mouth."""
        rnd = random.Random(seed)
        Mb = mat("breath", (0.85, 0.92, 1.0), 0.9, emit=(0.6, 0.7, 0.9), estr=0.8, alpha=0.35)
        mw = self.mouth.matrix_world.translation if False else None
        bpy.context.scene.frame_set(F(t))
        p = Vector(self.mouth.matrix_world.translation)
        fwd = self.root.matrix_world.to_quaternion() @ Vector((0, -1, 0))
        for i in range(n):
            ts = t + i * dur / n
            ob = sphere(f"{self.name}_br{int(t * 100)}_{i}", 0.3, tuple(p), Mb, coll=self.c, seg=10)
            ob.scale = (0.01,) * 3
            ob.keyframe_insert("scale", frame=F(ts - 0.02))
            ob.keyframe_insert("location", frame=F(ts))
            ob.scale = (1.5, 1.5, 1.0)
            ob.keyframe_insert("scale", frame=F(ts + 0.2))
            ob.location = tuple(p + fwd * rnd.uniform(4, 6) * self.root.scale[0] + Vector((rnd.uniform(-1, 1), 0, -rnd.uniform(1, 2.5))))
            ob.scale = (3.0, 3.0, 2.0)
            ob.keyframe_insert("location", frame=F(ts + 0.8))
            ob.scale = (0.01,) * 3
            ob.keyframe_insert("scale", frame=F(ts + 0.9))


def scorch(name, loc, yaw=0, coll=None, s=1.0, t=None):
    """A huge scorched footprint in the snow (appears at t)."""
    Mk = mat("scorch", hexc("#0b0a0a"), 1.0)
    root = empty(name, loc, coll=coll, rot=(0, 0, yaw))
    obs = [sphere(name + "_a", 1.0 * s, (0, 0, 0.02), Mk, (0.9, 1.8, 0.03), parent=root, coll=coll, seg=16)]
    for i, x in enumerate((-0.6, -0.2, 0.2, 0.6)):
        obs.append(sphere(f"{name}_t{i}", 0.28 * s, (x * s, -2.0 * s, 0.02), Mk, (1, 1.5, 0.03), parent=root, coll=coll, seg=10))
    Mh = mat("scorch_glow", hexc("#3a1a10"), 1.0, emit=hexc("#ff5a1a"), estr=0.6)
    obs.append(sphere(name + "_g", 0.75 * s, (0, 0, 0.025), Mh, (0.8, 1.5, 0.02), parent=root, coll=coll, seg=16))
    if t is not None:
        for ob in obs:
            sets.set_obj_visible(ob, t - 1 / 30, False)
            sets.set_obj_visible(ob, t, True)
    return root


def footprint_trail(prefix, p0, p1, n, t0=None, t1=None, coll=None, s=1.0):
    """n scorched prints from p0 to p1, appearing one by one from t0 to t1."""
    out = []
    p0, p1 = Vector(p0), Vector(p1)
    d = p1 - p0
    yaw = math.degrees(math.atan2(d.x, -d.y))
    side = Vector((-d.y, d.x, 0)).normalized() if d.length else Vector((1, 0, 0))
    for i in range(n):
        k = i / max(1, n - 1)
        p = p0 + d * k + side * (1.3 * s if i % 2 else -1.3 * s)
        t = None if t0 is None else t0 + (t1 - t0) * k
        out.append(scorch(f"{prefix}{i}", tuple(p), yaw, coll, s, t))
    return out


# ------------------------------------------------------------------ cast
def hollis(t0, t1, expr="neutral", smoke=False):
    H = chars.Char("Hollis", skin="#e9cdb4", shirt="#4a3a2e", pants="#2e2a26", hair="slick", hair_color="#d8d8d8",
                   face="mustache", sleeves="long", extras=("beard:#e8e8e8", "collar:#2a2420"))
    # long coat flaps over the legs
    Mc = mat("hollis_coat", hexc("#4a3a2e"), 0.8)
    box("Hollis_coatL", (1.05, 1.1, 1.6), (0.52, 0, -0.75), Mc, 0.06, parent=H.hip, coll=H.coll)
    box("Hollis_coatR", (1.05, 1.1, 1.6), (-0.52, 0, -0.75), Mc, 0.06, parent=H.hip, coll=H.coll)
    _live(H, t0, t1, expr)
    if smoke:
        Msm = mat("shadow_smoke2", hexc("#1a1a24"), 1.0, alpha=0.45)
        for i in range(5):
            ob = sphere(f"Hollis_sm{i}", 0.45, (random.uniform(-1, 1), random.uniform(-0.6, 0.6), 0.3), Msm,
                        (1.3, 1.3, 0.7), parent=H.root, coll=H.coll, seg=10)
            for ax in range(3):
                noise(ob, "location", ax, 0.25, 9 + i)
    return H


def matchbox(name, loc, coll=None, parent=None):
    root = empty(name, loc, coll=coll, parent=parent)
    box(name + "_box", (0.5, 0.3, 0.12), (0, 0, 0), mat("matchbox", hexc("#c8361e"), 0.6), 0.02, parent=root, coll=coll)
    return root


def match_stick(name, coll=None, parent=None, loc=(0, 0, 0), lit_t=None, die_t=None):
    root = empty(name, loc, coll=coll, parent=parent)
    cyl(name + "_stick", 0.03, 0.7, (0, 0, 0), mat("match_wood", hexc("#e0c38a"), 0.7), 6, parent=root, coll=coll)
    sphere(name + "_head", 0.06, (0, 0, 0.37), mat("match_head", hexc("#b22a1a"), 0.6), (1, 1, 1.3), parent=root, coll=coll, seg=8)
    fl = sphere(name + "_fl", 0.09, (0, 0, 0.5), mat("flame", (1, 0.7, 0.3), 0.3, emit=(1.0, 0.55, 0.15), estr=45.0),
                (1, 1, 2), parent=root, coll=coll, seg=10)
    fl.scale = (0.001,) * 3
    fl.keyframe_insert("scale", frame=1)
    if lit_t is not None:
        fl.keyframe_insert("scale", frame=F(lit_t - 0.03))
        fl.scale = (1.4, 1.4, 2.6); fl.keyframe_insert("scale", frame=F(lit_t + 0.04))
        fl.scale = (1, 1, 2); fl.keyframe_insert("scale", frame=F(lit_t + 0.12))
    if die_t is not None:
        fl.keyframe_insert("scale", frame=F(die_t - 0.04))
        fl.scale = (0.001,) * 3; fl.keyframe_insert("scale", frame=F(die_t + 0.02))
    return root


def hand_flame(name, ch, coll=None, energy=60):
    """A flame held in Eddie's cupped hands (in front of his chest)."""
    root = empty(name, (0, -1.4, 3.3), parent=ch.root, coll=coll)
    sphere(name + "_o", 0.14, (0, 0, 0), mat("flame", (1, 0.7, 0.3), 0.3, emit=(1.0, 0.55, 0.15), estr=45.0), (1, 1, 2.1),
           parent=root, coll=coll, seg=12)
    sphere(name + "_i", 0.07, (0, 0, -0.05), mat("flame_core", (1, 1, 0.9), 0.3, emit=(1.0, 0.92, 0.7), estr=80.0),
           (1, 1, 1.8), parent=root, coll=coll, seg=10)
    noise(root, "rotation_euler", 0, 0.15, 2.5)
    lt = light(name + "_lt", "POINT", (0, -1.5, 3.5), energy, (1.0, 0.55, 0.2), 0.1, coll=coll)
    lt.parent = ch.root
    lt.location = (0, -1.6, 3.6)
    fx.flicker(lt, 0.3, 2.0)
    return root, lt


def desk_fan(name, loc, coll=None, rot=0):
    root = empty(name, loc, coll=coll, rot=(0, 0, rot))
    Mf = mat("fan_white", hexc("#dcdce0"), 0.4)
    cyl(name + "_base", 0.6, 0.15, (0, 0, 0.08), Mf, 20, parent=root, coll=coll)
    cyl(name + "_neck", 0.08, 1.2, (0, 0, 0.7), Mf, 8, parent=root, coll=coll)
    cyl(name + "_cage", 0.75, 0.3, (0, 0, 1.4), mat("fan_cage", hexc("#9aa0aa"), 0.3, metal=0.6), 20, rot=(90, 0, 0),
        parent=root, coll=coll)
    hub = empty(name + "_hub", (0, -0.18, 1.4), parent=root, coll=coll)
    for k in range(3):
        box(f"{name}_bl{k}", (0.3, 0.04, 0.65), (0, 0, 0.32), Mf, 0.02, parent=hub, coll=coll, rot=(0, k * 120, 0))
    return root, hub


def trash_can(name, loc, coll=None):
    root = empty(name, loc, coll=coll)
    Mm = mat("can_metal", hexc("#6a707a"), 0.5, metal=0.6)
    cyl(name + "_can", 0.9, 2.2, (0, 0, 1.1), Mm, 20, parent=root, coll=coll, r2=1.0)
    return root
