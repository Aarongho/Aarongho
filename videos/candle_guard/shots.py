"""candle_guard (horror): twelve candles burn in the square; each one that goes out lets the
Snuffer take one step closer. 87 shots keyed to script word indices."""
import os, sys, math, random
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from shotkit import *
from rbx import story
from rbx.story import *
from mathutils import Vector
import props as P

V = Video(__file__)
story.bind(V)

E_POS = (0.0, 5.4, 0.0)           # Eddie guards on the north side, facing the candles (rot 0 = -Y)
E_HEAD = (0.0, 5.4, 4.7)
SN_SCALE = 1.25
N = len(V.words)


def W_(i):
    return V.w(min(i, N - 1))


# ------------------------------------------------------------------ story state
OUT = {1: W_(106) + 0.15, 2: W_(119) + 0.15, 3: W_(124) + 0.15, 4: W_(148) + 0.15, 5: W_(150), 6: W_(151),
       7: W_(169) + 0.15, 8: W_(171), 9: W_(182) + 0.15, 10: W_(184), 11: W_(200) + 0.15}
RELIGHT = {11: W_(258) + 0.3, 10: W_(265) + 0.05, 9: W_(267) + 0.05}
HOOK_END = W_(19)
HOOK_OUT11 = W_(3) + 0.15
DEMO_OUT = W_(36)                 # rule demo: one candle goes out (shot 9, its own little world)

STEPS = [(W_(118), 1), (W_(122), 2), (W_(127) + 0.3, 3), (W_(152), 4), (W_(153), 5), (W_(154), 6),
         (W_(172), 7), (W_(178), 8), (W_(183) + 0.3, 9), (W_(185), 10), (W_(202), 11),
         (W_(261), 10), (W_(266), 9), (W_(268), 8)]
RETREAT = (W_(269), W_(272))
EYES_OPEN = W_(208)
HAND_CANDLE = W_(250)


def k_y(k):
    return 8.9 + (60.0 - 8.9) * (1 - k / 11.0)


def k_at(t):
    if t < HOOK_END:
        return 11
    k = 0
    for ts, kk in STEPS:
        if ts <= t:
            k = kk
    return k


def lit_at(t):
    if t < HOOK_END:
        return {12} if t >= HOOK_OUT11 else {11, 12}
    s = set(range(1, 13))
    for n, ts in OUT.items():
        if ts <= t:
            s.discard(n)
    for n, ts in RELIGHT.items():
        if ts <= t:
            s.add(n)
    return s


# ------------------------------------------------------------------ scene builders
def night(t0, t1, houses=True, forest=True, lamps=True, glow=0.0, moon=0.55, door_open=None):
    P.night_world(1.0, glow)
    P.moonlight(moon)
    c = P.square(houses=False, forest=forest, lamps=lamps)
    if houses:
        P.town_ring(c, door_open=door_open)
    # lamps die one by one in the streetlight beat
    if lamps:
        t_l = [W_(156) + 0.1 + i * 0.32 for i in range(6)]
        for i, tl in enumerate(t_l):
            if tl <= t0:
                lt = D.objects.get(f"lamp{i}_lt")
                if lt:
                    lt.data.energy = 0
                b = D.objects.get(f"lamp{i}_glass")
                if b:
                    b.hide_render = True
            elif tl < t1 + 0.5:
                P.lamp_off(f"lamp{i}", tl)
    if t0 >= W_(162) and door_open is None and houses:
        for ob in D.objects:
            if ob.name.endswith("_hinge"):
                ob.rotation_euler[2] = math.radians(-70)
    return c


def candles(t0, t1, hook=False, hand=False):
    lit = lit_at(t0 + 0.001) if not hook else ({12} if t0 >= HOOK_OUT11 else {11, 12})
    K = P.Candles(lit=lit)
    if hook:
        if t0 <= HOOK_OUT11 < t1:
            K.out(11, HOOK_OUT11)
    else:
        for n, ts in OUT.items():
            if t0 < ts < t1 + 0.1 and ts > t0 + 0.001:
                K.out(n, ts)
        for n, ts in RELIGHT.items():
            if t0 < ts < t1 + 0.1:
                K.light_up(n, ts)
    if hand:
        for nm in ("candle12", "drip12", "wick12", "flame12", "flame12_o", "flame12_i", "cl12"):
            ob = D.objects.get(nm)
            if ob:
                ob.hide_render = True
                if ob.type == "LIGHT":
                    ob.data.energy = 0
    return K


def snow_footprints(t0):
    """Scorched trail from the forest to the edge of the square (exists after it was revealed)."""
    if t0 >= W_(172):
        P.footprint_trail("fp", (0, 46, 0), (0, 12, 0), 9, s=1.1)


def snuffer(t0, t1, eyes=None):
    k0 = k_at(t0 + 0.001)
    if eyes is None:
        eyes = t0 >= EYES_OPEN
    S = P.Snuffer((0, k_y(k0), 0), 0, scale=SN_SCALE, eyes=eyes)
    S.at(t0, (0, k_y(k0), 0))
    prev = k0
    if t0 >= HOOK_END:
        for ts, kk in STEPS:
            if t0 < ts < t1 + 0.05:
                S.step(ts, (0, k_y(prev), 0), (0, k_y(kk), 0))
                prev = kk
        a, b = RETREAT
        if t0 < b and t1 > a:
            S.at(max(a, t0), (0, k_y(prev) if t0 < a else k_y(8) + (k_y(0) - k_y(8)) * (t0 - a) / (b - a), 0))
            S.at(b, (0, k_y(0) + 6, 0))
        elif t0 >= b:
            S.at(t0, (0, k_y(0) + 6, 0))
    if not eyes and t0 < EYES_OPEN < t1:
        S.eyes_open(EYES_OPEN)
    return S


def guard(t0, t1, expr="worried", loc=E_POS, rot=0):
    E = eddie(t0, t1, expr)
    E.pose(t0, loc=loc, rot=rot)
    return E


def thud_fx(t, cam=None, s=1.0):
    sfx(t, "thud", 1.0)
    sfx(t, "boom", 0.35 * s)
    if cam:
        cam.crash(t, cam.cd.lens, cam.cd.lens * 1.08, 0.06)


def hiss(t):
    sfx(t - 0.05, "hiss")


# ================================================================== HOOK (flash-forward)
@S(1, 0, 3, "HOOK: last two flames, pushing in fast, Eddie terrified behind them")
def s01(t0, t1):
    night(t0, t1)
    K = candles(t0, t1, hook=True)
    E = guard(t0, t1, "terror")
    E.act(t0, "brace")
    S = snuffer(t0, t1, eyes=False)
    S.reach(t0, 0.6)
    cam = Cam()
    p11 = K.pos[11]
    cam.key(t0, (p11[0] - 1.5, p11[1] - 4.5, p11[2] + 0.3), (p11[0], p11[1] + 3, p11[2] + 1.2), lens=24, focus=4.0, fstop=2.0)
    cam.key(t1, (p11[0] - 1.1, p11[1] - 3.0, p11[2] + 0.4), (p11[0], p11[1] + 3, p11[2] + 1.1), lens=28, focus=3.0, fstop=2.0)
    cam.handheld(1.6)
    sfx(t0, "wind", 0.5)
    sfx(t0, "rise", 0.6)


@S(2, 3, 5, "Candle eleven goes out: ECU")
def s02(t0, t1):
    night(t0, t1, houses=False)
    K = candles(t0, t1, hook=True)
    S = snuffer(t0, t1, eyes=False)
    p = K.pos[11]
    cam = Cam()
    cam.push(t0, t1, p, 2.6, 1.7, yaw=-20, pitch=6, lens=40, fstop=2.0)
    cam.crash(HOOK_OUT11, 40, 52, 0.08)
    cam.handheld(1.2)
    hiss(HOOK_OUT11)


@S(3, 5, 10, "Eddie CU lit from below by the last candle, darkness behind")
def s03(t0, t1):
    night(t0, t1)
    K = candles(t0, t1, hook=True)
    E = guard(t0, t1, "terror")
    E.pose(t0, armL=(30, 20), armR=(30, 20))
    S = snuffer(t0, t1, eyes=False)
    cam = Cam()
    cam.push(t0, t1, E_HEAD, 6.0, 4.4, yaw=8, pitch=-6, lens=32, yaw1=-4, fstop=2.2)
    cam.crash(W_(9), 32, 40, 0.1)
    cam.handheld(1.4)
    sfx(W_(6), "wind", 0.6)


@S(4, 10, 13, "OTS low: the hood looms over Eddie's head, sharp eyes snap open on 'whispered'")
def s04(t0, t1):
    night(t0, t1)
    K = candles(t0, t1, hook=True)
    E = guard(t0, t1, "terror")
    E.act(t0 + 0.05, "recoil", expr="terror")
    S = snuffer(t0, t1, eyes=False)
    te = W_(11)
    S.eyes_open(te)
    S.reach(t0, 0.8)
    mid = (0, 7.0, 7.2)
    cam = Cam()
    cam.key(t0, orbit_pos(mid, 13, 62, -6), mid, lens=20, focus=E_HEAD, fstop=4)
    cam.key(t1, orbit_pos(mid, 11.5, 56, -6), mid, lens=20, focus=E_HEAD, fstop=4)
    cam.crash(te, 24, 30, 0.08)
    cam.handheld(1.2)
    sfx(te - 0.02, "sting")
    sfx(W_(10), "whisper", 0.8)


@S(5, 13, 19, "Wide low: tiny Eddie, the towering Snuffer behind him, blades rising")
def s05(t0, t1):
    night(t0, t1)
    K = candles(t0, t1, hook=True)
    E = guard(t0, t1, "terror")
    E.act(t0, "hands_head", expr="terror")
    S = snuffer(t0, t1, eyes=True)
    S.arms(t0, (20, 20), (20, 20))
    S.arms(t1, (120, 35), (110, 30))
    cam = Cam()
    cam.push(t0, t1, (0, 7.0, 7.5), 22.0, 17.0, yaw=-12, pitch=-4, lens=22, yaw1=6, fstop=5.6)
    cam.handheld(1.0)
    sfx(W_(16), "drone", 0.8)


# ================================================================== RULE
@S(6, 19, 24, "Aerial over the night town, 12 candles glowing in the square")
def s06(t0, t1):
    night(t0, t1)
    K = candles(t0, t1)
    cam = Cam()
    cam.orbit(t0, t1, (0, 0, 1.5), 48, -30, 15, pitch=48, lens=24, fstop=16, pitch1=40)
    cam.handheld(0.5)
    sfx(t0, "whoosh", 0.7)
    sfx(t0, "crickets", 0.5)


@S(7, 24, 29, "Orbit close on the ring of twelve candles")
def s07(t0, t1):
    night(t0, t1, houses=False)
    K = candles(t0, t1)
    cam = Cam()
    cam.orbit(t0, t1, (0, 0, P.FLAME_Z - 0.3), 7.5, 20, 80, pitch=22, lens=28, fstop=3.5)
    cam.handheld(0.5)
    sfx(t0 + 0.1, "sparkle", 0.4)


@S(8, 29, 32, "Wide square: lamps, houses, moon, candles in the middle")
def s08(t0, t1):
    night(t0, t1)
    K = candles(t0, t1)
    cam = Cam()
    cam.push(t0, t1, (0, 0, 2.5), 30, 24, yaw=-25, pitch=10, lens=22, yaw1=-18, fstop=11)
    cam.handheld(0.6)


@S(9, 32, 37, "Demo: one candle goes out")
def s09(t0, t1):
    night(t0, t1, houses=False)
    K = P.Candles()
    K.out(6, DEMO_OUT)
    p = K.pos[6]
    cam = Cam()
    cam.push(t0, t1, p, 3.6, 2.4, yaw=10, pitch=8, lens=36, fstop=2.2)
    cam.handheld(0.8)
    hiss(DEMO_OUT)


@S(10, 37, 42, "The forest: deep in the trees, a dark robed shape")
def s10(t0, t1):
    night(t0, t1, houses=False)
    K = candles(t0, t1)
    S = P.Snuffer((0, 58, 0), 0, scale=SN_SCALE)
    cam = Cam()
    cam.push(t0, t1, (0, 58, 10), 34, 26, yaw=0, pitch=2, lens=34, fstop=8)
    cam.handheld(0.7)
    sfx(t0 + 0.2, "drone", 0.6)


@S(11, 42, 47, "...take one step closer: THUD, snow kicks up")
def s11(t0, t1):
    night(t0, t1, houses=False)
    K = candles(t0, t1)
    S = P.Snuffer((0, 58, 0), 0, scale=SN_SCALE)
    ts = W_(45)
    S.step(ts, (0, 58, 0), (0, 53, 0))
    puff_snow("ps", (0, 53, 0.3), ts)
    cam = Cam()
    cam.push(t0, t1, (0, 54, 7), 22, 18, yaw=-8, pitch=-2, lens=30, fstop=8)
    thud_fx(ts, cam)
    cam.handheld(1.0)


def puff_snow(name, loc, t, s=1.0):
    Ms = mat("snowpuff", hexc("#cfd8ea"), 0.9, alpha=0.7)
    rnd = random.Random(len(name))
    for i in range(8):
        a = i / 8 * math.tau
        ob = sphere(f"{name}{i}", 0.6 * s, loc, Ms, seg=10)
        ob.scale = (0.01,) * 3
        ob.keyframe_insert("scale", frame=F(t - 0.02))
        ob.keyframe_insert("location", frame=F(t))
        ob.scale = (1.4, 1.4, 0.8)
        ob.location = (loc[0] + math.cos(a) * 3 * s, loc[1] + math.sin(a) * 3 * s, loc[2] + rnd.uniform(0.3, 1.2))
        ob.keyframe_insert("scale", frame=F(t + 0.35))
        ob.keyframe_insert("location", frame=F(t + 0.35))
        ob.scale = (0.01,) * 3
        ob.keyframe_insert("scale", frame=F(t + 0.8))


@S(12, 47, 53, "High angle: twelve scorched footprints from the forest to the square")
def s12(t0, t1):
    night(t0, t1)
    K = candles(t0, t1)
    P.footprint_trail("demo", (0, 50, 0), (0, 12, 0), 12, t0 + 0.1, W_(51), s=1.1)
    cam = Cam()
    cam.key(t0, (14, 52, 26), (0, 38, 0), lens=24, fstop=16)
    cam.key(t1, (12, 20, 22), (0, 4, 1), lens=24, fstop=16, ease="EASE_IN_OUT")
    cam.handheld(0.6)
    for i in range(4):
        sfx(t0 + 0.2 + i * 0.6, "thud", 0.35)


# ================================================================== SOCIETY
def vignette_world():
    P.night_world(1.0)
    P.moonlight(0.4)
    box("vg_ground", (200, 200, 0.4), (0, 0, -0.2), mat("snow", hexc("#c9d3e6"), 0.85), 0)
    P.forest_ring(collection("VG"), seed=5)
    light("vg_fill", "AREA", (0, -10, 6), 300, (0.7, 0.8, 1.0), 8, target=(0, 0, 3))


@S(13, 53, 60, "Nobody owns a fan: a townie drops a desk fan into the trash under a streetlight")
def s13(t0, t1):
    vignette_world()
    c = collection("VG2")
    P.street_lamp("vl", (3.5, 2.0, 0), c)
    P.house("vh", (0, 8, 0), 0, c, seed=2, lit=True)
    P.trash_can("tc", (1.6, -0.5, 0), c)
    k = townie(3, t0, t1, "angry")
    k.pose(t0, loc=(-1.2, -0.8, 0), rot=-80)
    k.pose(t0, armL=(80, -10), armR=(80, -10))
    fan, hub = P.desk_fan("fan", (0.2, -0.9, 3.1), c, rot=-80)
    td = W_(58)
    fan.keyframe_insert("location", frame=F(td))
    fan.keyframe_insert("rotation_euler", frame=F(td))
    fan.location = (1.6, -0.5, 1.6)
    fan.rotation_euler = (math.radians(40), math.radians(20), math.radians(-60))
    fan.keyframe_insert("location", frame=F(td + 0.3))
    fan.keyframe_insert("rotation_euler", frame=F(td + 0.3))
    hub.keyframe_insert("rotation_euler", index=1, frame=F(t0))
    hub.rotation_euler[1] = math.tau * 6
    hub.keyframe_insert("rotation_euler", index=1, frame=F(t1))
    k.pose(td + 0.15, armL=(40, 10), armR=(40, 10))
    k.act(td + 0.3, "cross", expr="smug")
    cam = Cam()
    cam.push(t0, t1, (0.6, -0.6, 3.0), 9.0, 6.5, yaw=-10, pitch=6, lens=26, fstop=4)
    cam.handheld(0.8)
    sfx(td + 0.3, "clink")
    sfx(td + 0.32, "thud", 0.5)


@S(14, 60, 65, "Every window nailed shut: hammering boards")
def s14(t0, t1):
    vignette_world()
    c = collection("VG2")
    r, hg = P.house("vh", (0, 6, 0), 0, c, seed=4, boards=True)
    k = townie(1, t0, t1, "determined")
    k.pose(t0, loc=(2.9, 0.6, 0), rot=180)
    ham = empty("ham", (0, 0, -1.7), parent=k.shR)
    box("ham_h", (0.12, 0.12, 1.0), (0, 0, 0), mat("ham_wood", hexc("#8a5a32"), 0.6), 0.02, parent=ham)
    box("ham_k", (0.5, 0.25, 0.25), (0, 0, -0.5), mat("ham_metal", hexc("#555a62"), 0.4, metal=0.8), 0.03, parent=ham)
    t = t0 + 0.1
    while t < t1:
        k.pose(t, armR=(170, 10))
        k.pose(t + 0.18, armR=(95, 10))
        sfx(t + 0.18, "hammer", 0.7)
        t += 0.55
    cam = Cam()
    cam.push(t0, t1, (2.4, 2.2, 4.4), 7.0, 5.5, yaw=-30, pitch=4, lens=26, fstop=3.5, yaw1=-20)
    cam.handheld(0.8)


def stool_scene(t0, t1, hollis=True, mug=True, expr="neutral"):
    night(t0, t1)
    K = candles(t0, t1)
    sp = (-5.6, -2.6)
    Mw = mat("stool_wood", hexc("#5a3a22"), 0.7)
    box("stool", (1.6, 1.6, 0.25), (sp[0], sp[1], 1.9), Mw, 0.04)
    for sx in (-1, 1):
        for sy in (-1, 1):
            box(f"stool_l{sx}{sy}", (0.18, 0.18, 1.8), (sp[0] + sx * 0.6, sp[1] + sy * 0.6, 0.9), Mw, 0.02)
    if mug:
        cyl("mug", 0.25, 0.5, (sp[0] + 1.3, sp[1] - 0.6, 0.25), mat("mug_m", hexc("#c8361e"), 0.4), 16)
    H = None
    if hollis:
        H = P.hollis(t0, t1, expr)
        yaw = facing(sp, (0, 0))
        H.pose(t0, loc=(sp[0], sp[1], 0.25), rot=yaw, legL=(85, 4), legR=(85, -4), armL=(40, -20), armR=(40, -20))
    return K, H, sp


@S(15, 65, 70, "Old Mr. Hollis on his stool beside the candles")
def s15(t0, t1):
    K, H, sp = stool_scene(t0, t1, expr="neutral")
    H.face(t0, eyes="wide", mouth="flat")
    cam = Cam()
    cam.push(t0, t1, (sp[0], sp[1], 4.0), 11, 8, yaw=facing(sp, (0, 0)) + 35, pitch=4, lens=24, fstop=4)
    cam.handheld(0.6)


@S(16, 70, 76, "Sixty years: slow orbit, Hollis staring at the flames")
def s16(t0, t1):
    K, H, sp = stool_scene(t0, t1)
    H.face(t0, eyes="wide", mouth="flat")
    look_at(H, t0, (0, 0, 3))
    cam = Cam()
    yaw = facing(sp, (0, 0))
    cam.orbit(t0, t1, (sp[0], sp[1], 4.5), 6.5, yaw - 50, yaw - 10, pitch=6, lens=30, fstop=3)
    cam.handheld(0.5)


@S(17, 76, 80, "He has never slept: ECU huge unblinking eyes, twitch")
def s17(t0, t1):
    K, H, sp = stool_scene(t0, t1)
    H.face(t0, eyes="terror", mouth="flat")
    H.face(W_(78), eyes="wide", mouth="grimace")
    for i in range(4):
        H.pose(t0 + 0.4 + i * 0.5, head=(3 * (-1) ** i, 0, 2 * (-1) ** i))
    head = (sp[0], sp[1], 4.9)
    yaw = facing(sp, (0, 0))
    cam = Cam()
    cam.push(t0, t1, head, 3.4, 2.4, yaw=yaw, pitch=2, lens=40, fstop=2.4)
    cam.crash(W_(78), 40, 50, 0.1)
    cam.handheld(1.0)
    sfx(W_(78), "sting", 0.5)


# ================================================================== PIVOT
@S(18, 80, 83, "But last night: the stool is empty, the wind pushes the mug")
def s18(t0, t1):
    K, H, sp = stool_scene(t0, t1, hollis=False)
    cam = Cam()
    cam.push(t0, t1, (sp[0], sp[1], 2.2), 7.5, 5.5, yaw=facing(sp, (0, 0)) + 20, pitch=10, lens=28, fstop=3)
    cam.handheld(0.8)
    sfx(t0, "wind", 0.6)


@S(19, 83, 88, "Hollis's house: door shut, window dark")
def s19(t0, t1):
    night(t0, t1)
    K = candles(t0, t1)
    x, y, a = P.HOUSE_SPOTS[2]
    cam = Cam()
    cam.push(t0, t1, (x * 0.93, y * 0.93, 4), 13, 9, yaw=-math.degrees(a), pitch=4, lens=26, fstop=6,
             look=(x, y, 4))
    cam.handheld(0.8)


@S(20, 88, 94, "My name is Eddie: nervous, holding the matchbox")
def s20(t0, t1):
    night(t0, t1)
    K = candles(t0, t1)
    E = guard(t0, t1, "worried")
    E.act(t0 + 0.1, "wave", expr="smile")
    E.act(W_(92), "hold", expr="worried")
    P.matchbox("mb", (0, 0, -1.7), parent=E.shL)
    cam = Cam()
    cam.push(t0, t1, E_HEAD, 7.0, 5.2, yaw=-15, pitch=2, lens=28, yaw1=-5, fstop=2.8)
    cam.handheld(0.8)


@S(21, 94, 101, "The only one awake: dark houses, tiny Eddie, crane up")
def s21(t0, t1):
    night(t0, t1)
    K = candles(t0, t1)
    E = guard(t0, t1, "worried")
    E.act(t0, "cross")
    cam = Cam()
    cam.key(t0, (6, -14, 3), (0, 3, 3), lens=24, fstop=8)
    cam.key(t1, (10, -24, 22), (0, 4, 2), lens=24, fstop=8, ease="EASE_IN_OUT")
    cam.handheld(0.5)
    sfx(t0, "crickets", 0.6)


# ================================================================== ESCALATION
@S(22, 101, 104, "Midnight: moon over the treetops")
def s22(t0, t1):
    night(t0, t1)
    K = candles(t0, t1)
    cam = Cam()
    cam.key(t0, (0, 10, 4), (-60, 200, 70), lens=30, fstop=11)
    cam.key(t1, (0, 12, 4.5), (-70, 220, 82), lens=34, fstop=11)
    cam.handheld(0.5)
    sfx(t0 + 0.1, "bell", 0.8)


@S(23, 104, 106, "The wind: flames lean hard, snow blowing")
def s23(t0, t1):
    night(t0, t1, houses=False)
    K = candles(t0, t1)
    for n, fl in K.flames.items():
        fl.rotation_euler[0] = math.radians(-35)
        fl.keyframe_insert("rotation_euler", index=0, frame=F(t0 + 0.3))
    snow_drift(t0, t1)
    cam = Cam()
    cam.push(t0, t1, (0, 0, P.FLAME_Z), 6.5, 5.0, yaw=-60, pitch=12, lens=28, fstop=3)
    cam.handheld(1.2)
    sfx(t0, "wind")


def snow_drift(t0, t1, n=60, center=(0, 0, 3), seed=2):
    rnd = random.Random(seed)
    Ms = mat("flake", (1, 1, 1), 0.5, emit=(0.8, 0.85, 1.0), estr=0.8)
    for i in range(n):
        p = (center[0] + rnd.uniform(-10, 10), center[1] + rnd.uniform(-8, 8), center[2] + rnd.uniform(-2, 5))
        ob = sphere(f"flake{i}", 0.05, p, Ms, seg=6)
        ob.keyframe_insert("location", frame=F(t0))
        ob.location = (p[0] + 12, p[1] + rnd.uniform(-1, 1), p[2] - 2)
        ob.keyframe_insert("location", frame=F(t1))
        set_interp(ob, "location", F(t0), "LINEAR")


def candle_ecu(t0, t1, n, yaw=-15, lens=40):
    night(t0, t1, houses=False)
    K = candles(t0, t1)
    S = snuffer(t0, t1)
    p = K.pos[n]
    cam = Cam()
    cam.push(t0, t1, p, 2.8, 2.0, yaw=yaw, pitch=8, lens=lens, fstop=2.0)
    cam.crash(OUT[n], lens, lens * 1.25, 0.08)
    cam.handheld(1.2)
    hiss(OUT[n])
    return K, cam


@S(24, 106, 107, "Fssst: candle one dies")
def s24(t0, t1):
    candle_ecu(t0, t1, 1)


@S(25, 107, 111, "Candle one went out: Eddie's shock")
def s25(t0, t1):
    night(t0, t1)
    K = candles(t0, t1)
    E = guard(t0, t1, "shock")
    E.act(t0, "shock", expr="shock")
    cam = Cam()
    cam.push(t0, t1, E_HEAD, 5.5, 4.3, yaw=12, pitch=-2, lens=30, fstop=2.4)
    cam.crash(t0 + 0.05, 30, 36, 0.08)
    cam.handheld(1.0)


@S(26, 111, 116, "Far away in the trees")
def s26(t0, t1):
    night(t0, t1, houses=False)
    K = candles(t0, t1)
    S = snuffer(t0, t1)
    cam = Cam()
    cam.push(t0, t1, (0, k_y(0), 9), 40, 32, yaw=4, pitch=3, lens=30, fstop=8, look=(0, k_y(0), 9))
    cam.handheld(0.6)


@S(27, 116, 118, "Something stepped: smoke feet in the snow, low")
def s27(t0, t1):
    night(t0, t1, houses=False)
    K = candles(t0, t1)
    S = snuffer(t0, t1)
    y = k_y(0)
    cam = Cam()
    cam.push(t0, t1, (0, y, 1.5), 12, 9, yaw=-15, pitch=0, lens=30, fstop=4)
    cam.handheld(0.8)
    sfx(t0 + 0.2, "drone", 0.5)


@S(28, 118, 119, "THUD: it lurches out of the trees")
def s28(t0, t1):
    night(t0, t1, houses=False)
    K = candles(t0, t1)
    S = snuffer(t0, t1)
    ts = W_(118)
    puff_snow("ps", (0, k_y(1), 0.3), ts)
    cam = Cam()
    cam.push(t0, t1, (0, k_y(1), 8), 26, 23, yaw=6, pitch=2, lens=30, fstop=8)
    thud_fx(ts, cam)
    cam.handheld(1.4)


@S(29, 119, 120, "Fssst: candle two")
def s29(t0, t1):
    candle_ecu(t0, t1, 2, yaw=20)


@S(30, 120, 122, "Candle two: Eddie looks back over his shoulder")
def s30(t0, t1):
    night(t0, t1)
    K = candles(t0, t1)
    E = guard(t0, t1, "scared")
    E.look(t0 + 0.1, 70, -5)
    E.face(t0 + 0.1, "side_r")
    cam = Cam()
    cam.push(t0, t1, E_HEAD, 5.0, 4.2, yaw=-20, pitch=0, lens=30, fstop=2.4)
    cam.handheld(1.0)


@S(31, 122, 123, "THUD: closer through the trees")
def s31(t0, t1):
    night(t0, t1, houses=False)
    K = candles(t0, t1)
    S = snuffer(t0, t1)
    E = guard(t0, t1, "scared")
    ts = W_(122)
    puff_snow("ps", (0, k_y(2), 0.3), ts)
    cam = Cam()
    cam.key(t0, (1.5, 3.0, 5.2), (0, k_y(2), 8), lens=32, focus=(0, k_y(2), 8), fstop=4)
    cam.key(t1, (1.4, 3.3, 5.2), (0, k_y(2), 8), lens=32, focus=(0, k_y(2), 8), fstop=4)
    thud_fx(ts, cam)
    cam.handheld(1.4)


@S(32, 123, 124, "Closer: ECU Eddie's eyes")
def s32(t0, t1):
    night(t0, t1)
    K = candles(t0, t1)
    E = guard(t0, t1, "terror")
    cam = Cam()
    cam.push(t0, t1, (0, 5.4, 4.9), 2.8, 2.3, yaw=0, pitch=0, lens=45, fstop=2.0)
    cam.handheld(1.2)
    sfx(t0, "whisper", 0.5)


@S(33, 124, 125, "Fssst: candle three")
def s33(t0, t1):
    candle_ecu(t0, t1, 3, yaw=-40)


@S(34, 125, 127, "Candle three: top-down on the ring, three dead")
def s34(t0, t1):
    night(t0, t1, houses=False)
    K = candles(t0, t1)
    E = guard(t0, t1, "scared")
    cam = Cam()
    cam.key(t0, (0, -0.5, 16), (0, 0, 0), lens=30, fstop=11, roll=0)
    cam.key(t1, (0, -0.3, 13), (0, 0, 0), lens=30, fstop=11, roll=8)
    cam.handheld(0.6)


@S(35, 127, 133, "Every dog stopped barking: a dog's ears drop, it lies down and stares")
def s35(t0, t1):
    night(t0, t1)
    K = candles(t0, t1)
    x, y, a = P.HOUSE_SPOTS[4]
    dp = (x * 0.8, y * 0.8, 0)
    d = W.dog("dog", dp, color="#b07a3a")
    d.rotation_euler[2] = math.radians(facing(dp, (0, 30)))
    d.keyframe_insert("rotation_euler", index=2, frame=F(t0))
    d.keyframe_insert("location", frame=F(t0 + 0.6))
    d.location = (dp[0], dp[1], -0.7)
    d.rotation_euler[0] = math.radians(6)
    d.keyframe_insert("location", frame=F(t0 + 1.2))
    d.keyframe_insert("rotation_euler", index=0, frame=F(t0 + 1.2))
    cam = Cam()
    cam.push(t0, t1, (dp[0], dp[1], 2.0), 8.5, 6.5, yaw=facing(dp, (0, 30)) + 20, pitch=6, lens=28, fstop=3.5)
    cam.handheld(0.7)
    sfx(t0 + 0.1, "bark", 0.6)


@S(36, 133, 137, "I grabbed the matches")
def s36(t0, t1):
    night(t0, t1)
    K = candles(t0, t1)
    E = guard(t0, t1, "determined")
    P.matchbox("mb", (0, 0, -1.7), parent=E.shL)
    E.act(t0 + 0.1, "hold", expr="determined")
    cam = Cam()
    cam.push(t0, t1, (0, 4.2, 3.5), 5.5, 4.0, yaw=-25, pitch=10, lens=30, fstop=2.8)
    cam.handheld(1.0)
    sfx(t0 + 0.1, "rattle", 0.8)


def match_shot(t0, t1, strike, die, expr="determined"):
    night(t0, t1)
    K = candles(t0, t1)
    E = guard(t0, t1, expr)
    E.pose(t0, armL=(80, -10), armR=(80, -20))
    P.matchbox("mb", (0, 0, -1.7), parent=E.shL)
    P.match_stick("ms", parent=E.shR, loc=(0.1, 0, -1.8), lit_t=strike, die_t=die)
    if strike:
        E.pose(strike - 0.12, armR=(80, -30))
        E.pose(strike, armR=(80, 0))
        sfx(strike - 0.05, "scratch")
    cam = Cam()
    cam.push(t0, t1, (0, 3.6, 3.3), 3.6, 3.0, yaw=-30, pitch=6, lens=34, fstop=2.2)
    cam.handheld(1.2)
    return E, cam


@S(37, 137, 138, "Scratch: the match flares")
def s37(t0, t1):
    match_shot(t0, t1, W_(137), None)


@S(38, 138, 139, "Out: the match dies instantly")
def s38(t0, t1):
    E, cam = match_shot(t0, t1, None, None, "shock")
    P.match_stick("ms2", parent=E.shR, loc=(0.1, 0, -1.8), lit_t=t0 - 0.2, die_t=W_(138) + 0.05)
    wisp("mw", (0.4, 3.2, 3.4), W_(138) + 0.05)
    sfx(W_(138) + 0.02, "puff", 0.7)


def wisp(name, p, t):
    P.wisp(name, p, t, None, n=3, rise=1.2)


@S(39, 139, 140, "Scratch again")
def s39(t0, t1):
    E, cam = match_shot(t0, t1, W_(139), None, "angry")


@S(40, 140, 141, "Out again: Eddie's face")
def s40(t0, t1):
    night(t0, t1)
    K = candles(t0, t1)
    E = guard(t0, t1, "terror")
    P.match_stick("ms", parent=E.shR, loc=(0.1, 0, -1.8), lit_t=t0 - 0.2, die_t=W_(140) + 0.05)
    E.pose(t0, armR=(95, -20))
    cam = Cam()
    cam.push(t0, t1, E_HEAD, 4.5, 3.8, yaw=15, pitch=-4, lens=32, fstop=2.2)
    cam.handheld(1.2)
    sfx(W_(140) + 0.02, "puff", 0.7)


@S(41, 141, 148, "Every match died: frantic striking, dead matches in the snow")
def s41(t0, t1):
    night(t0, t1)
    K = candles(t0, t1)
    E = guard(t0, t1, "panic")
    P.matchbox("mb", (0, 0, -1.7), parent=E.shL)
    t, i = t0 + 0.1, 0
    while t < t1 - 0.3:
        P.match_stick(f"ms{i}", parent=E.shR, loc=(0.1, 0, -1.8), lit_t=t + 0.1, die_t=t + 0.35)
        E.pose(t, armR=(80, -30), armL=(80, -10))
        E.pose(t + 0.1, armR=(80, 0))
        sfx(t + 0.05, "scratch", 0.6)
        t += 0.6; i += 1
    rnd = random.Random(1)
    for j in range(10):
        st = cyl(f"dead{j}", 0.03, 0.7, (rnd.uniform(-1.5, 1.5), 3.6 + rnd.uniform(-1, 1), 0.05),
                 mat("match_wood", hexc("#e0c38a"), 0.7), 6, rot=(90, 0, rnd.uniform(0, 180)))
    cam = Cam()
    cam.orbit(t0, t1, (0, 5.0, 3.5), 6.5, -40, 20, pitch=14, lens=28, fstop=3)
    cam.handheld(1.4)


@S(42, 148, 149, "Fssst: candle four")
def s42(t0, t1):
    candle_ecu(t0, t1, 4, yaw=-70)


@S(43, 149, 152, "Four, five, six: whip across the ring as they die")
def s43(t0, t1):
    night(t0, t1, houses=False)
    K = candles(t0, t1)
    S = snuffer(t0, t1)
    cam = Cam()
    p5, p6 = K.pos[5], K.pos[6]
    cam.key(t0, orbit_pos(K.pos[4], 3.2, 100, 10), K.pos[4], lens=34, fstop=2.4)
    cam.key(OUT[5] - 0.1, orbit_pos(p5, 3.2, 130, 10), p5, lens=34, fstop=2.4)
    cam.key(OUT[6] - 0.1, orbit_pos(p6, 3.2, 160, 10), p6, lens=34, fstop=2.4)
    cam.key(t1, orbit_pos(p6, 3.6, 165, 12), p6, lens=34, fstop=2.4)
    cam.handheld(1.2)
    hiss(OUT[5]); hiss(OUT[6])
    sfx(OUT[5] - 0.15, "whoosh", 0.6)
    sfx(OUT[6] - 0.15, "whoosh", 0.6)


def thud_shot(t0, t1, ts, k, cam_loc, lens=30):
    night(t0, t1)
    K = candles(t0, t1)
    S = snuffer(t0, t1)
    snow_footprints(t0)
    puff_snow("ps", (0, k_y(k), 0.3), ts)
    tgt = (0, k_y(k), 8)
    cam = Cam()
    cam.key(t0, cam_loc, tgt, lens=lens, fstop=6)
    cam.key(t1, (cam_loc[0] * 0.97, cam_loc[1] + 0.5, cam_loc[2]), tgt, lens=lens, fstop=6)
    thud_fx(ts, cam)
    cam.handheld(1.6)
    return S, cam


@S(44, 152, 153, "THUD (four)")
def s44(t0, t1):
    thud_shot(t0, t1, W_(152), 4, (10, 2, 3))


@S(45, 153, 154, "THUD (five): closer")
def s45(t0, t1):
    thud_shot(t0, t1, W_(153), 5, (-8, 4, 2.5), lens=28)


@S(46, 154, 155, "THUD (six): it reaches the houses")
def s46(t0, t1):
    thud_shot(t0, t1, W_(154), 6, (4, -6, 4.5), lens=26)


@S(47, 155, 162, "The streetlights flicker off one by one")
def s47(t0, t1):
    night(t0, t1)
    K = candles(t0, t1)
    E = guard(t0, t1, "scared")
    S = snuffer(t0, t1)
    cam = Cam()
    cam.push(t0, t1, (0, 0, 4), 34, 28, yaw=150, pitch=14, lens=22, yaw1=175, fstop=11)
    cam.handheld(0.6)
    for i in range(6):
        sfx(W_(156) + 0.1 + i * 0.32 - 0.2, "buzz", 0.5)


@S(48, 162, 169, "Every front door creaks open by itself")
def s48(t0, t1):
    night(t0, t1, door_open=(W_(164), W_(167)))
    K = candles(t0, t1)
    E = guard(t0, t1, "terror")
    E.act(W_(165), "hands_face", expr="terror")
    S = snuffer(t0, t1)
    cam = Cam()
    cam.orbit(t0, t1, (0, 0, 4), 12, -150, -110, pitch=8, lens=22, fstop=8)
    cam.handheld(0.8)
    sfx(W_(164), "door")
    sfx(W_(165), "door", 0.6)
    sfx(W_(166), "door", 0.5)


@S(49, 169, 170, "Fssst: candle seven")
def s49(t0, t1):
    candle_ecu(t0, t1, 7, yaw=170)


@S(50, 170, 172, "Seven, eight: Eddie's terror lit by a shrinking ring")
def s50(t0, t1):
    night(t0, t1)
    K = candles(t0, t1)
    E = guard(t0, t1, "terror")
    E.act(t0, "brace", expr="terror")
    cam = Cam()
    cam.push(t0, t1, E_HEAD, 5.5, 4.4, yaw=-8, pitch=-6, lens=30, fstop=2.4)
    cam.handheld(1.4)
    hiss(OUT[8])


@S(51, 172, 177, "Footprints appear in the snow, top-down")
def s51(t0, t1):
    night(t0, t1)
    K = candles(t0, t1)
    P.footprint_trail("fp", (0, 46, 0), (0, 12, 0), 9, t0 + 0.1, t1 - 0.2, s=1.1)
    cam = Cam()
    cam.key(t0, (6, 44, 24), (0, 34, 0), lens=26, fstop=16)
    cam.key(t1, (6, 26, 22), (0, 16, 0), lens=26, fstop=16, ease="EASE_IN_OUT")
    cam.handheld(0.6)
    for i in range(9):
        sfx(t0 + 0.1 + (t1 - t0 - 0.3) * i / 8, "sizzle", 0.4)


@S(52, 177, 179, "Huge ones: Eddie's sneaker next to a giant print")
def s52(t0, t1):
    night(t0, t1)
    K = candles(t0, t1)
    snow_footprints(t0)
    P.scorch("big", (0.6, 11.0, 0), 0, s=1.1)
    E = guard(t0, t1, "shock", loc=(1.8, 13.0, 0), rot=180)
    E.pose(t0, head=(0, 30, 0))
    E.face(t0, "lookdown")
    cam = Cam()
    cam.push(t0, t1, (1.0, 12.0, 0.4), 6.5, 5.5, yaw=-60, pitch=40, lens=26, fstop=5)
    cam.handheld(0.8)
    sfx(t0, "sting", 0.4)


@S(53, 179, 182, "Walking toward me: low angle down the trail to Eddie")
def s53(t0, t1):
    night(t0, t1)
    K = candles(t0, t1)
    snow_footprints(t0)
    E = guard(t0, t1, "terror", rot=180)
    cam = Cam()
    cam.key(t0, (1.2, 30, 1.0), (0, 6, 3), lens=30, focus=(0, 6, 3), fstop=4)
    cam.key(t1, (1.0, 22, 1.0), (0, 6, 3), lens=30, focus=(0, 6, 3), fstop=4)
    cam.handheld(1.0)
    sfx(t0, "footsteps", 0.6)


@S(54, 182, 183, "Fssst: candle nine")
def s54(t0, t1):
    candle_ecu(t0, t1, 9, yaw=-110)


@S(55, 183, 185, "Nine, ten: two flames left, hands over face")
def s55(t0, t1):
    night(t0, t1)
    K = candles(t0, t1)
    E = guard(t0, t1, "terror")
    E.act(t0 + 0.05, "hands_face", expr="terror")
    cam = Cam()
    cam.push(t0, t1, (0, 2.5, 3.6), 8.0, 6.5, yaw=-25, pitch=12, lens=26, fstop=3)
    cam.handheld(1.4)
    hiss(OUT[10])


@S(56, 185, 195, "A tall shape at the edge of the square: slow push, blade arms")
def s56(t0, t1):
    night(t0, t1)
    K = candles(t0, t1)
    E = guard(t0, t1, "terror", rot=180)
    snow_footprints(t0)
    S = snuffer(t0, t1)
    S.arms(t0 + 0.5, (10, 14), (10, 14))
    S.arms(t1, (35, 30), (30, 26))
    cam = Cam()
    cam.push(t0, t1, (0, k_y(10), 8.5), 26, 19, yaw=10, pitch=0, lens=26, fstop=6, look=(0, k_y(10) - 2, 8))
    cam.handheld(0.8)
    sfx(W_(186), "drone")


@S(57, 195, 197, "No eyes: CU into the black hood")
def s57(t0, t1):
    night(t0, t1, houses=False)
    K = candles(t0, t1)
    S = snuffer(t0, t1)
    hood = (0, k_y(10) - 1.2, 10.0 * SN_SCALE + 0.6)
    cam = Cam()
    cam.push(t0, t1, hood, 7.5, 5.5, yaw=0, pitch=-4, lens=32, fstop=2.8)
    cam.handheld(0.8)


@S(58, 197, 200, "Just a mouth: frosty glow, breath curling out")
def s58(t0, t1):
    night(t0, t1, houses=False)
    K = candles(t0, t1)
    S = snuffer(t0, t1)
    S.breath(t0 + 0.2, t1 - t0)
    m = (0, k_y(10) - 1.6, 10.0 * SN_SCALE + 0.1)
    cam = Cam()
    cam.push(t0, t1, m, 4.5, 3.4, yaw=-12, pitch=-6, lens=36, fstop=2.4)
    cam.handheld(0.8)
    sfx(t0 + 0.2, "breath")


@S(59, 200, 201, "Fssst: candle eleven, frost breath rolls over it")
def s59(t0, t1):
    K, cam = candle_ecu(t0, t1, 11, yaw=10, lens=36)
    puff = mat("breath", (0.85, 0.92, 1.0), 0.9, emit=(0.6, 0.7, 0.9), estr=0.8, alpha=0.35)
    p = K.pos[11]
    for i in range(5):
        ob = sphere(f"fr{i}", 0.4, (p[0], p[1] + 2.5, p[2] + 0.5), puff, seg=10)
        ob.keyframe_insert("location", frame=F(t0 + i * 0.05))
        ob.location = (p[0] + random.uniform(-0.5, 0.5), p[1] - 1.5, p[2] + random.uniform(-0.2, 0.4))
        ob.keyframe_insert("location", frame=F(t1))


@S(60, 201, 202, "Eleven: Eddie lit by one candle")
def s60(t0, t1):
    night(t0, t1, lamps=False)
    K = candles(t0, t1)
    E = guard(t0, t1, "terror")
    E.act(t0, "brace")
    cam = Cam()
    cam.push(t0, t1, E_HEAD, 4.6, 3.9, yaw=-5, pitch=-10, lens=32, fstop=2.0)
    cam.handheld(1.6)


@S(61, 202, 203, "THUD: it's right behind him")
def s61(t0, t1):
    night(t0, t1)
    K = candles(t0, t1)
    E = guard(t0, t1, "terror")
    S = snuffer(t0, t1)
    snow_footprints(t0)
    ts = W_(202)
    cam = Cam()
    cam.push(t0, t1, (0, 7.0, 7.0), 16, 14, yaw=-15, pitch=-2, lens=24, fstop=5.6)
    thud_fx(ts, cam, 1.5)
    cam.handheld(1.8)


@S(62, 203, 208, "Cold breath on my neck: frost curls past his ear, he shivers")
def s62(t0, t1):
    night(t0, t1)
    K = candles(t0, t1)
    E = guard(t0, t1, "terror")
    S = snuffer(t0, t1)
    S.reach(t0, 0.9)
    S.breath(t0 + 0.1, t1 - t0, n=12)
    for i in range(8):
        E.pose(t0 + 0.2 + i * 0.12, torso=(0, 0, 2 * (-1) ** i))
    cam = Cam()
    cam.push(t0, t1, (0, 5.6, 5.4), 5.2, 4.2, yaw=-45, pitch=6, lens=30, fstop=2.4, yaw1=-35)
    cam.handheld(1.2)
    sfx(t0, "breath")


@S(63, 208, 209, "Eddie...: the sharp eyes snap open, ECU")
def s63(t0, t1):
    night(t0, t1, houses=False)
    K = candles(t0, t1)
    S = snuffer(t0, t1, eyes=False)
    hood = (0, k_y(11) - 1.6, 10.0 * SN_SCALE + 0.7)
    cam = Cam()
    cam.push(t0, t1, hood, 4.6, 3.6, yaw=0, pitch=-2, lens=34, fstop=2.4)
    cam.crash(EYES_OPEN + 0.02, 34, 44, 0.08)
    cam.handheld(1.0)
    sfx(EYES_OPEN - 0.02, "sting")
    sfx(EYES_OPEN, "whisper", 0.8)


@S(64, 209, 212, "One candle left: top-down, a single flame shrinking")
def s64(t0, t1):
    night(t0, t1, houses=False, lamps=False)
    K = candles(t0, t1)
    K.shrink(12, t0, t1, 0.55)
    E = guard(t0, t1, "terror")
    S = snuffer(t0, t1)
    cam = Cam()
    cam.key(t0, (0, 0.5, 20), (0, 1.5, 0), lens=26, fstop=16)
    cam.key(t1, (0, 0.8, 15), (0, 1.5, 0), lens=26, fstop=16, roll=-6)
    cam.handheld(0.5)
    sfx(t0, "heartbeat")


# ================================================================== THE TURN
@S(65, 212, 216, "Then I noticed something: Eddie's eyes slide sideways")
def s65(t0, t1):
    night(t0, t1, lamps=False)
    K = candles(t0, t1)
    E = guard(t0, t1, "scared")
    E.face(W_(214), "side_l")
    cam = Cam()
    cam.push(t0, t1, E_HEAD, 4.2, 3.4, yaw=8, pitch=-4, lens=36, fstop=2.0)
    cam.handheld(0.8)


@S(66, 216, 220, "There was no wind: the smoke from the dead candles rises perfectly straight")
def s66(t0, t1):
    night(t0, t1, houses=False, lamps=False)
    K = candles(t0, t1)
    for n in (3, 4, 5, 6):
        x, y, z = K.pos[n]
        for j in range(4):
            sphere(f"st{n}_{j}", 0.07 + j * 0.02, (x, y, z + 0.2 + j * 0.35), mat("wisp_grey", (0.55, 0.57, 0.62), 0.9,
                   emit=(0.15, 0.16, 0.2), estr=0.3, alpha=0.45), (1, 1, 2.0), seg=8)
    cam = Cam()
    cam.push(t0, t1, K.pos[5], 4.5, 3.6, yaw=120, pitch=6, lens=30, fstop=2.8)
    cam.handheld(0.5)


@S(67, 220, 224, "The trees weren't moving: dead still forest")
def s67(t0, t1):
    night(t0, t1, houses=False, lamps=False)
    K = candles(t0, t1)
    cam = Cam()
    cam.push(t0, t1, (25, 45, 8), 30, 26, yaw=200, pitch=4, lens=28, fstop=11)
    cam.handheld(0.3)


@S(68, 224, 232, "It wasn't the wind: the Snuffer leans down and breathes over the last candle")
def s68(t0, t1):
    night(t0, t1, lamps=False)
    K = candles(t0, t1)
    E = guard(t0, t1, "terror")
    S = snuffer(t0, t1)
    S.body.rotation_euler[0] = math.radians(0)
    S.body.keyframe_insert("rotation_euler", index=0, frame=F(t0))
    S.body.rotation_euler[0] = math.radians(-14)
    S.body.keyframe_insert("rotation_euler", index=0, frame=F(t0 + 1.2))
    S.breath(t0 + 0.6, t1 - t0 - 0.6)
    fl = K.flames[12]
    for i in range(6):
        fl.rotation_euler[0] = math.radians(25 if i % 2 else 5)
        fl.keyframe_insert("rotation_euler", index=0, frame=F(t0 + 0.8 + i * 0.35))
    cam = Cam()
    cam.push(t0, t1, (0, 4, 6.5), 18, 15, yaw=-70, pitch=2, lens=24, fstop=5.6)
    cam.handheld(0.8)
    sfx(t0 + 0.6, "breath")


@S(69, 232, 237, "It was breathing on them: Eddie's realisation")
def s69(t0, t1):
    night(t0, t1, lamps=False)
    K = candles(t0, t1)
    E = guard(t0, t1, "shock")
    E.face(W_(234), "gasp")
    E.act(W_(234), "recoil", 0.6)
    cam = Cam()
    cam.push(t0, t1, E_HEAD, 5.0, 3.6, yaw=-10, pitch=-2, lens=32, fstop=2.2)
    cam.crash(W_(234), 32, 40, 0.1)
    cam.handheld(1.0)


@S(70, 237, 243, "If darkness pulls it closer: two-shot, the black looming over the tiny flame")
def s70(t0, t1):
    night(t0, t1, lamps=False)
    K = candles(t0, t1)
    E = guard(t0, t1, "determined")
    S = snuffer(t0, t1)
    S.reach(t0, 0.7)
    cam = Cam()
    cam.orbit(t0, t1, (0, 6, 6), 20, 70, 50, pitch=4, lens=24, fstop=6)
    cam.handheld(0.6)


@S(71, 243, 248, "Then light pushes it back: Eddie's determined face, flame in his eyes")
def s71(t0, t1):
    night(t0, t1, lamps=False)
    K = candles(t0, t1)
    E = guard(t0, t1, "determined")
    E.act(W_(245), "fists", expr="determined")
    cam = Cam()
    cam.push(t0, t1, E_HEAD, 4.8, 3.6, yaw=-6, pitch=-8, lens=34, fstop=2.2)
    cam.handheld(0.7)
    sfx(W_(244), "rise", 0.7)


# ================================================================== FIGHT BACK
def hand_candle_eddie(t0, t1, expr="determined", loc=E_POS):
    E = guard(t0, t1, expr, loc=loc)
    E.pose(t0, armL=(75, -18), armR=(75, -18))
    c = collection("HC")
    root = empty("hc", (0, -1.35, 3.0), parent=E.root)
    cyl("hc_wax", 0.2, 0.9, (0, 0, 0), mat("wax", hexc("#efe4c8"), 0.55, emit=hexc("#f3c88a"), estr=0.15), 16, parent=root)
    fr, lt = P.hand_flame("hf", E, energy=90)
    fr.location = (0, -1.35, 3.75)
    return E, root


@S(72, 248, 258, "So I cupped the last flame: Eddie lifts the last candle, hands around the flame")
def s72(t0, t1):
    night(t0, t1, lamps=False)
    K = candles(t0, t1, hand=True)
    E, hc = hand_candle_eddie(t0, t1)
    S = snuffer(t0, t1)
    cam = Cam()
    cam.push(t0, t1, (0, 4.0, 3.8), 6.0, 3.6, yaw=-20, pitch=4, lens=32, fstop=2.4)
    cam.handheld(0.8)


@S(73, 258, 261, "...and lit candle eleven: flare")
def s73(t0, t1):
    night(t0, t1, houses=False, lamps=False)
    K = candles(t0, t1, hand=True)
    E, hc = hand_candle_eddie(t0, t1, loc=(-0.9, 4.8, 0))
    E.pose(t0, rot=-25)
    p = K.pos[11]
    cam = Cam()
    cam.push(t0, t1, p, 3.6, 2.6, yaw=-50, pitch=10, lens=32, fstop=2.4)
    cam.crash(RELIGHT[11], 32, 38, 0.08)
    cam.handheld(0.8)
    sfx(RELIGHT[11] - 0.05, "ignite")


@S(74, 261, 262, "THUD: the Snuffer is shoved back")
def s74(t0, t1):
    night(t0, t1, lamps=False)
    K = candles(t0, t1, hand=True)
    S = snuffer(t0, t1)
    S.arms(t0, (40, 20), (40, 20))
    S.arms(t0 + 0.2, (130, 40), (130, 40))
    puff_snow("ps", (0, k_y(10), 0.3), W_(261))
    cam = Cam()
    cam.push(t0, t1, (0, k_y(10), 8), 18, 20, yaw=10, pitch=-2, lens=24, fstop=6)
    thud_fx(W_(261), cam)
    cam.handheld(1.4)
    sfx(W_(261), "screech", 0.7)


@S(75, 262, 265, "It stepped back: blades up against the light, Eddie holds the candle out")
def s75(t0, t1):
    night(t0, t1, lamps=False)
    K = candles(t0, t1, hand=True)
    E, hc = hand_candle_eddie(t0, t1, "angry")
    E.pose(t0, rot=180)
    S = snuffer(t0, t1)
    S.arms(t0, (120, 40), (130, 40))
    cam = Cam()
    cam.push(t0, t1, (0, 9, 6), 16, 13, yaw=-150, pitch=0, lens=24, fstop=5)
    cam.handheld(0.8)


@S(76, 265, 266, "Ten: relit")
def s76(t0, t1):
    night(t0, t1, houses=False, lamps=False)
    K = candles(t0, t1, hand=True)
    p = K.pos[10]
    cam = Cam()
    cam.push(t0, t1, p, 3.0, 2.4, yaw=-90, pitch=10, lens=34, fstop=2.4)
    cam.handheld(0.8)
    sfx(RELIGHT[10] - 0.05, "ignite")


@S(77, 266, 267, "THUD: back again")
def s77(t0, t1):
    night(t0, t1, lamps=False)
    K = candles(t0, t1, hand=True)
    S = snuffer(t0, t1)
    S.arms(t0, (130, 40), (120, 40))
    puff_snow("ps", (0, k_y(9), 0.3), W_(266))
    cam = Cam()
    cam.key(t0, (-6, 4, 4), (0, k_y(9), 9), lens=26, fstop=6)
    cam.key(t1, (-5.6, 4.4, 4), (0, k_y(9), 9), lens=26, fstop=6)
    thud_fx(W_(266), cam)
    cam.handheld(1.4)


@S(78, 267, 268, "Nine: relit, three flames now")
def s78(t0, t1):
    night(t0, t1, houses=False, lamps=False)
    K = candles(t0, t1, hand=True)
    cam = Cam()
    cam.push(t0, t1, K.pos[9], 3.2, 2.5, yaw=-120, pitch=12, lens=32, fstop=2.4)
    cam.handheld(0.8)
    sfx(RELIGHT[9] - 0.05, "ignite")


@S(79, 268, 269, "THUD: it staggers back toward the forest")
def s79(t0, t1):
    night(t0, t1)
    K = candles(t0, t1, hand=True)
    S = snuffer(t0, t1)
    S.arms(t0, (140, 50), (140, 50))
    puff_snow("ps", (0, k_y(8), 0.3), W_(268))
    cam = Cam()
    cam.push(t0, t1, (0, k_y(8), 8), 26, 30, yaw=-10, pitch=4, lens=26, fstop=8)
    thud_fx(W_(268), cam)
    cam.handheld(1.2)


@S(80, 269, 272, "It was working!: Eddie's fist pump, the Snuffer retreats behind him")
def s80(t0, t1):
    night(t0, t1)
    K = candles(t0, t1, hand=True)
    E, hc = hand_candle_eddie(t0, t1, "joy")
    E.pose(t0 + 0.1, armL=(170, 20))
    S = snuffer(t0, t1)
    cam = Cam()
    cam.push(t0, t1, (0, 5.4, 4.4), 7.5, 6.0, yaw=-5, pitch=4, lens=28, fstop=3)
    cam.handheld(1.0)
    sfx(t0, "rise", 0.5)


# ================================================================== CLIFFHANGER
HOLLIS_POS = (0.9, 8.0, 0.0)
H_ROT = facing(HOLLIS_POS, E_POS)


@S(81, 272, 277, "Then someone tapped my shoulder: a hand from behind, Eddie freezes")
def s81(t0, t1):
    night(t0, t1)
    K = candles(t0, t1, hand=True)
    E, hc = hand_candle_eddie(t0, t1, "joy")
    tt = W_(274)
    E.face(tt + 0.05, "shock")
    H = P.hollis(t0, t1, "smile")
    H.pose(t0, loc=HOLLIS_POS, rot=H_ROT, armR=(10, 5))
    H.pose(tt - 0.15, armR=(100, 10))
    H.pose(tt, armR=(85, 8))
    H.pose(tt + 0.25, armR=(100, 10))
    cam = Cam()
    cam.push(t0, t1, (0.4, 6.6, 5.0), 6.0, 5.0, yaw=100, pitch=8, lens=28, fstop=2.8)
    cam.handheld(0.8)
    sfx(tt, "tap")
    sfx(tt + 0.05, "sting", 0.4)


@S(82, 277, 281, "It was Mr. Hollis: Eddie turns, relief")
def s82(t0, t1):
    night(t0, t1)
    K = candles(t0, t1, hand=True)
    E, hc = hand_candle_eddie(t0, t1, "shock")
    E.pose(t0, rot=0)
    E.pose(t0 + 0.35, rot=160)
    E.face(W_(280), "relief")
    H = P.hollis(t0, t1, "smile")
    H.pose(t0, loc=HOLLIS_POS, rot=H_ROT)
    cam = Cam()
    cam.push(t0, t1, (0.5, 7.0, 4.8), 8.0, 6.5, yaw=-80, pitch=4, lens=26, fstop=3)
    cam.handheld(0.7)


@S(83, 281, 286, "Eddie, give me the candle: Hollis smiles, too wide")
def s83(t0, t1):
    night(t0, t1)
    K = candles(t0, t1, hand=True)
    H = P.hollis(t0, t1, "smile")
    H.pose(t0, loc=HOLLIS_POS, rot=H_ROT)
    lips(H, t0, t1)
    H.face(t0, eyes="half")
    cam = Cam()
    hp = (HOLLIS_POS[0], HOLLIS_POS[1], 4.8)
    cam.push(t0, t1, hp, 5.0, 4.0, yaw=H_ROT, pitch=-4, lens=32, fstop=2.4)
    cam.handheld(0.6)


@S(84, 286, 291, "I'll take it from here: ECU, a wisp of black smoke drifts off his collar")
def s84(t0, t1):
    night(t0, t1)
    K = candles(t0, t1, hand=True)
    H = P.hollis(t0, t1, "smile", smoke=True)
    H.pose(t0, loc=HOLLIS_POS, rot=H_ROT)
    lips(H, t0, t1)
    H.face(t0, eyes="half")
    Msm = mat("shadow_smoke2", hexc("#1a1a24"), 1.0, alpha=0.45)
    for i in range(4):
        ob = sphere(f"col_sm{i}", 0.25, (0.6 - i * 0.3, -0.3, 4.0), Msm, seg=10)
        ob.parent = H.root
        ob.keyframe_insert("location", frame=F(t0))
        ob.location = (0.8 - i * 0.3, -0.2, 5.6 + i * 0.2)
        ob.keyframe_insert("location", frame=F(t1))
    hp = (HOLLIS_POS[0], HOLLIS_POS[1], 4.9)
    cam = Cam()
    cam.push(t0, t1, hp, 3.6, 2.8, yaw=H_ROT + 5, pitch=-2, lens=38, fstop=2.2)
    cam.handheld(0.6)
    sfx(t0, "drone", 0.5)


@S(85, 291, 296, "He reached for the flame: his hand comes in, the flame shies away")
def s85(t0, t1):
    night(t0, t1)
    K = candles(t0, t1, hand=True)
    E, hc = hand_candle_eddie(t0, t1, "worried")
    E.pose(t0, rot=170)
    H = P.hollis(t0, t1, "smile")
    H.pose(t0, loc=HOLLIS_POS, rot=H_ROT, armR=(10, 5))
    H.pose(t1, armR=(85, -10))
    fl = D.objects.get("hf")
    if fl:
        fl.rotation_euler[0] = 0
        fl.keyframe_insert("rotation_euler", index=0, frame=F(t0 + 0.5))
        fl.rotation_euler[0] = math.radians(35)
        fl.keyframe_insert("rotation_euler", index=0, frame=F(t1))
    cam = Cam()
    cam.push(t0, t1, (0.5, 6.8, 3.9), 6.0, 4.6, yaw=-95, pitch=6, lens=28, fstop=2.8)
    cam.handheld(0.7)


@S(86, 296, 305, "That's when I looked down at the snow: Eddie's eyes drop, camera tilts down")
def s86(t0, t1):
    night(t0, t1)
    K = candles(t0, t1, hand=True)
    E, hc = hand_candle_eddie(t0, t1, "worried")
    E.pose(t0, rot=170)
    E.face(W_(300), "lookdown")
    E.pose(W_(300), head=(0, 28, 0))
    H = P.hollis(t0, t1, "smile")
    H.pose(t0, loc=HOLLIS_POS, rot=H_ROT, armR=(85, -10))
    cam = Cam()
    ep = (E_POS[0], E_POS[1], 4.7)
    cam.key(t0, orbit_pos(ep, 4.6, 170, 0), ep, lens=32, fstop=2.4)
    cam.key(t1, orbit_pos((0.6, 7.0, 2.5), 6.0, 150, 25), (0.6, 7.5, 1.0), lens=30, fstop=3, ease="EASE_IN_OUT")
    cam.handheld(0.7)
    sfx(W_(300), "heartbeat", 0.8)


@S(87, 305, None, "His footprints were huge: smoke at his feet, a trail of giant scorched prints behind him")
def s87(t0, t1):
    night(t0, t1)
    K = candles(t0, t1, hand=True)
    H = P.hollis(t0, t1, "smile", smoke=True)
    H.pose(t0, loc=HOLLIS_POS, rot=H_ROT)
    P.footprint_trail("hp", (1.5, 30, 0), (1.0, 10.0, 0), 7, s=1.1)
    cam = Cam()
    cam.key(t0, (7.0, 7.5, 1.6), (1.0, 9.5, 0.6), lens=24, fstop=5)
    cam.key(t1, (7.5, 6.0, 5.0), (1.2, 16.0, 0.0), lens=24, fstop=5, ease="EASE_IN_OUT")
    cam.crash(W_(308), 24, 30, 0.1)
    cam.handheld(0.8)
    sfx(W_(306), "sting")
    sfx(W_(308), "drone")
