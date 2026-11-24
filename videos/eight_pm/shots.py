"""eight_pm (horror): at 8 PM every window and door must be shut. Or else. 72 shots keyed to word
indices of the uncut 2:08 recording."""
import os, sys, math, random
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from shotkit import *
from rbx import story
from rbx.story import *
from mathutils import Vector
import props as P

V = Video(__file__)
story.bind(V)
N = len(V.words)


def W_(i):
    return V.w(min(i, N - 1))


RED_T = W_(119) + 0.1
BELL = (W_(112), W_(113))
LILY_DOOR = (0, 7)                         # Eddie's front door on the street
LILY_WIN_EXT = (4.4, 7.0, 9.6)             # Lily's window, street side
KITCHEN_EXT = (-4.4, 7.0, 3.6)
HALL = (150.0, 0.0, 0.0)
HALL_SIZE = (18, 12, 8)
BATH = (150.0, 40.0, 0.0)
VIS_STREET_SCALE = 0.68                    # head reaches the upstairs windows


# ------------------------------------------------------------------ helpers
def red_now(t):
    return t >= RED_T + 1.5


def street_scene(t0, t1, lily_open=True, lights=True):
    P.night_world(1.0)
    P.moonlight(0.6)
    red_at = RED_T if (t0 < RED_T + 1.5 < t1 + 2) and not red_now(t0) else None
    c, houses = P.street(red=red_now(t0), red_at=red_at, lily_open=lily_open)
    P.clock_tower((0, 75, 0), t_ring=[b for b in BELL if t0 - 1 < b < t1 + 1], hour=8.0 if t0 > W_(111) else 7.97)
    if lights:
        P.fill((0, -30, 14), (0, 8, 5), 1800, (0.5, 0.6, 1.0), 20)
    return houses


def hall_scene(t0, t1, lights=500):
    P.night_world(0.6)
    R = P.room("hall", HALL, HALL_SIZE, wall="#c9b89a", floor="#6a4a32", light_energy=lights,
               windows=[("N", 4.0, 4.2, 3.0, 3.0)],
               doors=[("N", -4.0, 2.6, 6.0, "#5a1a16"), ("W", 3.0, 2.6, 6.0, "#7a5236")])
    wall_clock("hclock", (HALL[0] + 8.78, HALL[1] + 1.0, 6.0), t0)
    # stairs up in the south-west corner
    Ms = P.mat("stair", P.hexc("#5a3a26"), 0.7)
    for k in range(6):
        box(f"stair{k}", (3.0, 1.2, 0.9 * (k + 1)), (HALL[0] - 7.0, HALL[1] - 5.2 + k * 1.2, 0.45 * (k + 1)), Ms, 0.02)
    box("hall_rug", (5, 3.5, 0.05), (HALL[0], HALL[1], 0.03), P.mat("hrug", P.hexc("#8a3a3a"), 0.9), 0.02)
    light("hall_fill", "AREA", (HALL[0], HALL[1] - 5.0, 6.5), 350, (0.75, 0.8, 1.0), 6, target=(HALL[0], HALL[1] + 3, 2))
    box("hall_table", (2.4, 1.2, 2.6), (HALL[0] + 7.0, HALL[1] + 4.5, 1.3), P.mat("bed_wood", P.hexc("#6a4a32"), 0.6), 0.05)
    return R


def wall_clock(name, loc, t0):
    """Clock on the east wall (faces -X). Shows 7:58 / 7:59 / 8:00 by time."""
    root = empty(name, loc, rot=(0, 0, -90))
    cyl(name + "_f", 1.1, 0.15, (0, 0, 0), mat("clock_face", hexc("#f2ead2"), 0.5, emit=hexc("#f2ead2"), estr=0.6), 32,
        rot=(90, 0, 0), parent=root)
    cyl(name + "_r", 1.2, 0.12, (0, 0.03, 0), mat("clock_rim", hexc("#2a2420"), 0.5), 32, rot=(90, 0, 0), parent=root)
    Mh = mat("clock_hand", hexc("#151515"), 0.5)
    hp = empty(name + "_hh", (0, -0.12, 0), parent=root)
    box(name + "_hhb", (0.1, 0.05, 0.6), (0, 0, 0.3), Mh, 0.01, parent=hp)
    mp = empty(name + "_mh", (0, -0.14, 0), parent=root)
    box(name + "_mhb", (0.07, 0.05, 0.9), (0, 0, 0.45), Mh, 0.01, parent=mp)

    def mins_at(t):
        if t < W_(107): return 58
        if t < W_(111): return 59
        return 60
    m = mins_at(t0)
    for t, mm in ((t0, m), (W_(107), 59), (W_(111), 60)):
        if t < t0:
            continue
        mp.rotation_euler[1] = math.radians(mm * 6); mp.keyframe_insert("rotation_euler", index=1, frame=F(t))
        hp.rotation_euler[1] = math.radians((7 + mm / 60) * 30); hp.keyframe_insert("rotation_euler", index=1, frame=F(t))
        for fc in fcurves(mp.animation_data.action) + fcurves(hp.animation_data.action):
            for kp in fc.keyframe_points:
                kp.interpolation = "CONSTANT"
    return root


def hall_eddie(t0, t1, expr="worried", loc=(0, 0), rot=0):
    E = eddie(t0, t1, expr)
    E.pose(t0, loc=(HALL[0] + loc[0], HALL[1] + loc[1], 0), rot=rot)
    return E


def lily_scene(t0, t1, open_window=True, slam_t=None, closet_t=None, bright=False):
    P.night_world(0.5)
    R = P.lily_room(open_window=open_window, slam_t=slam_t, closet_t=closet_t, bright=bright)
    P.fill((P.LILY[0] - 2, P.LILY[1] - 5, 6), (P.LILY[0], P.LILY[1] + 2, 2), 120, (0.6, 0.7, 1.0), 5)
    return R


def visitor_at_window(t0, t1, rise=None, eyes_lit=True):
    """Visitor outside Lily's window (lily_room location), head centred in the opening."""
    wx, wy, wz = P.LILY_WIN
    head_z = wz + 0.8
    s = VIS_STREET_SCALE
    rz = head_z - 14.6 * s
    Vv = P.Visitor((wx, wy + 1.6, rz), 0, s)
    Vv.arms(t0, (0, 4), (0, 4))
    if rise:
        Vv.at(t0, (wx, wy + 1.6, rz - 4.0))
        Vv.at(rise[0], (wx, wy + 1.6, rz - 4.0))
        Vv.at(rise[1], (wx, wy + 1.6, rz))
    if eyes_lit:
        light("vis_rim", "POINT", (wx, wy + 3.5, head_z + 2), 300, (0.6, 0.7, 1.0), 0.5)
    return Vv


def sill_point():
    wx, wy, wz = P.LILY_WIN
    return (wx, wy + 0.25, wz - 2.0)


def lily_in_bed(t0, t1, asleep=True, expr="sleepy"):
    L = P.lily(t0, t1, expr, asleep=asleep)
    P.lie_in_bed(L, t0)
    return L


def black_cover(cam, t, dur=0.4):
    """Fade to black: a card right in front of the lens."""
    m = mat("black_cover", (0, 0, 0), 1.0, alpha=0.999)
    m.surface_render_method = "BLENDED"
    b = plane("cover", 4, 4, (0, 0, -0.2), m, parent=cam.ob)
    sets.set_obj_visible(b, t - 1 / 30, False)
    sets.set_obj_visible(b, t, True)
    return b


# ================================================================== HOOK
@S(1, 0, 2, "8:01: Eddie's house under red streetlights, the tall Visitor at the wall, Lily's window open")
def s01(t0, t1):
    houses = street_scene(t0 + 100, t1 + 100)
    Vv = P.Visitor((5.6, 5.4, 0), 0, VIS_STREET_SCALE)
    Vv.arms(t0, (150, 10), (150, 10))
    light("vis_rim", "POINT", (5.6, 9, 12), 2500, (1.0, 0.2, 0.15), 1.0)
    cam = Cam()
    cam.push(t0, t1, (2.5, 7, 6.5), 24, 19, yaw=-12, pitch=4, lens=24, fstop=8)
    cam.crash(t0 + 0.05, 22, 26, 0.1)
    cam.handheld(1.2)
    sfx(t0, "sting")
    sfx(t0, "wind", 0.6)


@S(2, 2, 9, "My little sister's window was still open: curtains blowing out of it")
def s02(t0, t1):
    houses = street_scene(t0 + 100, t1 + 100)
    P.curtains("ec", (LILY_WIN_EXT[0], LILY_WIN_EXT[1] + 0.3, LILY_WIN_EXT[2] + 1.6), "S", 2.4, 3.0, blow=True)
    cam = Cam()
    cam.push(t0, t1, LILY_WIN_EXT, 12, 7.5, yaw=-15, pitch=-8, lens=28, fstop=4)
    cam.handheld(0.8)


@S(3, 9, 14, "And something was climbing in: long pale fingers curl over the sill, Lily asleep")
def s03(t0, t1):
    lily_scene(t0, t1)
    lily_in_bed(t0, t1)
    P.sill_hands("sh", sill_point(), t_curl=(t0 + 0.4, t0 + 1.4))
    cam = Cam()
    sp = sill_point()
    cam.push(t0, t1, (sp[0], sp[1] - 1, sp[2] + 0.3), 5.0, 3.6, yaw=-25, pitch=12, lens=30, fstop=2.8)
    cam.handheld(0.8)
    sfx(t0 + 0.4, "creak", 0.7)
    sfx(W_(12), "drone", 0.7)


# ================================================================== RULE
@S(4, 14, 19, "In this town: aerial over the night street, clock tower behind")
def s04(t0, t1):
    street_scene(t0, t1, lily_open=False)
    cam = Cam()
    cam.orbit(t0, t1, (0, 20, 4), 70, -25, 10, pitch=32, lens=26, fstop=16)
    cam.handheld(0.5)
    sfx(t0, "whoosh", 0.6)
    sfx(t0, "crickets", 0.5)


@S(5, 19, 23, "At exactly 8 PM: the clock tower face, crash zoom")
def s05(t0, t1):
    street_scene(t0, t1, lily_open=False)
    face = (0, 75 - 4.3, 20.5)
    cam = Cam()
    cam.push(t0, t1, face, 18, 12, yaw=0, pitch=-4, lens=30, fstop=8)
    cam.crash(W_(21), 30, 40, 0.1)
    cam.handheld(0.8)
    sfx(W_(21), "bell", 0.6)


@S(6, 23, 28, "Every window and every door: a neighbour slams her door; windows go dark one by one")
def s06(t0, t1):
    houses = street_scene(t0, t1, lily_open=False)
    h = houses[-22]["hinge"]
    h.rotation_euler[2] = math.radians(-80); h.keyframe_insert("rotation_euler", index=2, frame=F(t0))
    h.rotation_euler[2] = 0; h.keyframe_insert("rotation_euler", index=2, frame=F(W_(27) + 0.1))
    k = townie(4, t0, t1, "worried")
    k.pose(t0, loc=(-22.5, 6.0, 0), rot=180)
    k.pose(W_(27), loc=(-22.5, 7.5, 0))
    cam = Cam()
    cam.push(t0, t1, (-22, 7, 4), 18, 14, yaw=20, pitch=4, lens=26, fstop=6)
    cam.handheld(0.8)
    sfx(W_(27) + 0.1, "door")


@S(7, 28, 31, "Must be shut: CU a bolt slams across")
def s07(t0, t1):
    bolt_insert(t0, t1, ("N", -4.0), W_(30))
    sfx(W_(30), "thud", 0.5)


@S(8, 31, 33, "Or else: the Visitor at the end of the street, eyes glinting")
def s08(t0, t1):
    street_scene(t0 + 60, t1 + 60, lily_open=False, lights=False)
    Vv = P.Visitor((-48, 1.0, 0), -90, VIS_STREET_SCALE)
    Vv.head_tilt(t0, 18)
    light("vis_rim", "POINT", (-48, 5, 12), 2500, (1.0, 0.15, 0.1), 1.0)
    cam = Cam()
    cam.push(t0, t1, (-48, 1, 8), 26, 20, yaw=-80, pitch=0, lens=30, fstop=6)
    cam.handheld(0.8)
    sfx(t0, "sting")


# ------------------------------------------------------------------ society
def vignette(day=False):
    if day:
        P.day_world(1.0)
        light("vg_sun", "SUN", (0, 0, 50), 3.5, (1, 0.95, 0.85), 2, rot=(50, 0, 30))
    else:
        P.night_world(1.0)
        P.moonlight(0.6)
    box("vg_ground", (400, 400, 0.4), (-200, 0, -0.2), mat("grass_dusk", hexc("#3a4a2e") if not day else hexc("#5fb04a"), 0.9), 0)


@S(9, 33, 39, "School ends at 7: kids sprint out of the school under a dusky sky, clock at 7")
def s09(t0, t1):
    vignette()
    P.night_world(1.4)
    Mb = mat("school_brick", hexc("#a0503a"), 0.8)
    box("school", (30, 10, 14), (-200, 12, 7), Mb, 0.1)
    box("school_door", (5, 0.3, 6), (-200, 6.9, 3), mat("door_dark", hexc("#050506"), 1.0), 0)
    P.sign("school_sign", "SCHOOL", (-200, 6.6, 12), 2.2, "#ffffff", emit=1.5)
    P.sign("school_time", "ENDS 7:00 PM", (-200, 6.6, 9.4), 1.2, "#ff4a3a", emit=4.0)
    for i in range(5):
        k = townie(i, t0, t1, "panic")
        x = -206 + i * 3
        k.run(t0, t1, (x, 6.0 - i * 0.8, 0), (x + random.uniform(-2, 2), -10 - i, 0)) if hasattr(k, "run") else None
    P.fill((-200, -20, 10), (-200, 8, 5), 1500, (1.0, 0.7, 0.5), 12)
    cam = Cam()
    cam.push(t0, t1, (-200, 4, 5), 24, 18, yaw=-10, pitch=6, lens=24, fstop=8)
    cam.handheld(0.8)
    sfx(t0 + 0.1, "kids_laugh", 0.4)
    sfx(t0 + 0.2, "footsteps", 0.6)


@S(10, 39, 45, "Pizza places stop delivering at 7:30: shop sign flips to CLOSED")
def s10(t0, t1):
    vignette()
    box("pizza", (16, 8, 10), (-200, 62, 5), mat("pizza_wall", hexc("#e8d6a0"), 0.8), 0.1)
    P.sign("pizza_sign", "PIZZA", (-200, 57.8, 8.2), 2.0, "#ff6a2a", emit=6.0)
    box("pizza_win", (8, 0.1, 3.5), (-200, 57.9, 3.2), mat("win_lit", (1, 0.8, 0.5), 0.3, emit=(1.0, 0.72, 0.4), estr=2.5), 0)
    card_root = empty("closed_piv", (-200, 57.6, 5.6))
    P.sign("closed_a", "OPEN", (0, -0.06, 0), 0.6, "#5aff6a", emit=6.0, parent=card_root)
    P.sign("closed_b", "CLOSED 7:30", (0, 0.06, 0), 0.5, "#ff3a2a", emit=6.0, rot=(90, 0, 180), parent=card_root)
    tf = W_(44)
    card_root.keyframe_insert("rotation_euler", index=2, frame=F(tf - 0.1))
    card_root.rotation_euler[2] = math.pi
    card_root.keyframe_insert("rotation_euler", index=2, frame=F(tf + 0.15))
    k = townie(6, t0, t1, "panic")
    k.pose(t0, loc=(-194, 54, 0), rot=-90)
    box("pizzabox", (1.4, 1.4, 0.3), (0, -1.2, 3.0), mat("pz_box", hexc("#c8a070"), 0.8), 0.02, parent=k.root)
    k.pose(t0, armL=(80, -10), armR=(80, -10))
    P.fill((-200, 40, 8), (-200, 58, 4), 900, (1.0, 0.8, 0.6), 10)
    cam = Cam()
    cam.push(t0, t1, (-199, 57.6, 5), 13, 9.5, yaw=-15, pitch=0, lens=26, fstop=4)
    cam.handheld(0.8)
    sfx(tf, "click", 0.7)


def barnes_house(day=False, empty_=False):
    vignette(day)
    h = P.house2("bh", (-200, -52, 0), collection("BARNES"), "#6a5a4a", lit_windows=not day)
    flap = P.cat_flap("flap", h["hinge"])
    return h, flap


@S(11, 45, 50, "Mr. Barnes waves from his porch, his cat beside him")
def s11(t0, t1):
    h, flap = barnes_house()
    B = P.barnes(t0, t1, "happy")
    B.pose(t0, loc=(-198, -59, 0), rot=10)
    B.act(t0 + 0.2, "wave")
    W2.cat("bcat", (-196.5, -59.5, 0), rot=10)
    P.fill((-200, -75, 8), (-200, -58, 4), 1200, (1.0, 0.8, 0.6), 10)
    cam = Cam()
    cam.push(t0, t1, (-198, -59, 4.4), 10, 8, yaw=10, pitch=2, lens=26, fstop=3)
    cam.handheld(0.8)


@S(12, 50, 56, "...forgot to close his cat flap: CU the flap swinging in the dark")
def s12(t0, t1):
    h, flap = barnes_house()
    P.fill((-200, -70, 3), (-200, -57, 1), 600, (0.6, 0.7, 1.0), 6)
    cam = Cam()
    cam.push(t0, t1, (-200.0, -57.3, 1.0), 4.2, 3.2, yaw=-15, pitch=6, lens=30, fstop=2.4)
    cam.handheld(0.8)
    sfx(t0 + 0.3, "creak", 0.5)


@S(13, 56, 63, "In the morning, his house was empty: door hanging open, nobody home")
def s13(t0, t1):
    h, flap = barnes_house(day=True)
    h["hinge"].rotation_euler[2] = math.radians(-75)
    noise(h["hinge"], "rotation_euler", 2, 0.05, 15)
    cam = Cam()
    cam.push(t0, t1, (-200, -57, 3), 18, 13, yaw=-8, pitch=4, lens=26, fstop=8)
    cam.handheld(0.6)
    sfx(t0, "wind", 0.6)


@S(14, 63, 68, "Even the cat was gone: an empty food bowl, the flap swinging")
def s14(t0, t1):
    h, flap = barnes_house(day=True)
    cyl("bowl", 0.6, 0.3, (-197.6, -58.4, 0.15), mat("bowl", hexc("#d9453a"), 0.4), 24)
    P.sign("bowl_t", "KITTY", (-197.6, -59.02, 0.18), 0.18, "#ffffff", rot=(90, 0, 0))
    cam = Cam()
    cam.push(t0, t1, (-197.8, -58.4, 0.5), 3.5, 2.6, yaw=-30, pitch=18, lens=32, fstop=2.4)
    cam.handheld(0.6)
    sfx(t0 + 0.2, "meow", 0.0)
    sfx(t0 + 0.2, "aww", 0.3)


# ================================================================== PIVOT
@S(15, 68, 77, "Mom and Dad were working late: a note on the fridge")
def s15(t0, t1):
    R = hall_scene(t0, t1)
    fx_, fy_ = HALL[0] + 6.5, HALL[1] + 5.0
    box("fridge", (3, 2.4, 7), (fx_, fy_, 3.5), mat("fridge", hexc("#e8eaee"), 0.25), 0.15)
    note = plane("note", 2.0, 1.6, (fx_ - 0.3, fy_ - 1.22, 4.8), mat("note_y", hexc("#f2e27a"), 0.8), rot=(90, 0, 0))
    P.sign("note1", "WORKING LATE!", (fx_ - 0.3, fy_ - 1.25, 5.2), 0.22, "#202020")
    P.sign("note2", "LOCK UP BY 8:00", (fx_ - 0.3, fy_ - 1.25, 4.8), 0.22, "#c8261e")
    P.sign("note3", "LOVE, MOM", (fx_ - 0.3, fy_ - 1.25, 4.4), 0.2, "#202020")
    cam = Cam()
    cam.push(t0, t1, (fx_ - 0.3, fy_ - 1.2, 4.8), 4.6, 3.2, yaw=-5, pitch=2, lens=34, fstop=3)
    cam.handheld(0.6)
    sfx(t0, "paper", 0.6)


@S(16, 77, 83, "My name is Eddie: Eddie in the hallway, keys in hand")
def s16(t0, t1):
    hall_scene(t0, t1)
    E = hall_eddie(t0, t1, "smile")
    E.act(t0 + 0.1, "wave")
    cam = Cam()
    cam.push(t0, t1, (HALL[0], HALL[1], 4.7), 6.5, 5.0, yaw=-10, pitch=2, lens=28, fstop=2.8)
    cam.handheld(0.7)


@S(17, 83, 92, "In charge of locking the house: Eddie gulps, eyes the dark front door")
def s17(t0, t1):
    hall_scene(t0, t1)
    E = hall_eddie(t0, t1, "worried", rot=180)
    E.act(W_(89), "hold", expr="worried")
    cam = Cam()
    cam.push(t0, t1, (HALL[0] - 1.5, HALL[1] + 3, 4.0), 9.0, 7.0, yaw=-25, pitch=8, lens=24, fstop=4,
             look=(HALL[0] - 2, HALL[1] + 4, 3.5))
    cam.handheld(0.7)


# ================================================================== LOCK-UP RACE
def clock_shot(t0, t1, ti):
    hall_scene(t0, t1)
    c = (HALL[0] + 8.7, HALL[1] + 1.0, 6.0)
    cam = Cam()
    cam.push(t0, t1, c, 4.5, 3.2, yaw=-90, pitch=0, lens=32, fstop=2.4)
    if ti:
        cam.crash(ti, 32, 40, 0.08)
    cam.handheld(1.0)
    sfx(t0, "tick", 0.8)


@S(18, 92, 93, "7:58: wall clock")
def s18(t0, t1):
    clock_shot(t0, t1, t0 + 0.05)


@S(19, 93, 98, "I ran through the house: Eddie sprints across the hall")
def s19(t0, t1):
    hall_scene(t0, t1)
    E = eddie(t0, t1, "panic")
    E.run(t0, t1, (HALL[0] + 6, HALL[1] - 3, 0), (HALL[0] - 5, HALL[1] + 2, 0))
    cam = Cam()
    cam.track(E, t0, t1, offset=(2.5, -4.5, 1.2), look_up=4.0, lens=24)
    cam.handheld(1.4)
    sfx(t0, "footsteps")


def door_shot(t0, t1, key, t_click, dx=0):
    R = hall_scene(t0, t1)
    hinge, kn = R["door"][key]
    E = eddie(t0, t1, "panic")
    if key[0] == "N":
        E.pose(t0, loc=(HALL[0] - 4.0 + dx, HALL[1] + 4.0, 0), rot=180)
        tgt = (HALL[0] - 4.0, HALL[1] + 4.5, 4)
        yaw = 25
    else:
        E.pose(t0, loc=(HALL[0] - 7.0, HALL[1] + dx, 0), rot=-90)
        tgt = (HALL[0] - 8, HALL[1] + 3.0, 4)
        yaw = 70
    E.act(t0 + 0.05, "reach", expr="panic")
    cam = Cam()
    cam.push(t0, t1, tgt, 6.0, 5.0, yaw=yaw, pitch=6, lens=26, fstop=3)
    cam.handheld(1.2)
    if t_click:
        sfx(t_click, "click")
    return R, E


@S(20, 98, 100, "Front door")
def s20(t0, t1):
    door_shot(t0, t1, ("N", -4.0), None)


def bolt_insert(t0, t1, key, t_click):
    R = hall_scene(t0, t1)
    hinge, kn = R["door"][key]
    nm = "hall_bolt" + key[0] + str(key[1])
    b = D.objects.get(nm)
    if b:
        b.location[0] -= 0.5; b.keyframe_insert("location", index=0, frame=F(t_click - 0.05))
        b.location[0] += 0.5; b.keyframe_insert("location", index=0, frame=F(t_click + 0.03))
    bpy.context.scene.frame_set(F(t0))
    p = tuple(b.matrix_world.translation) if b else (HALL[0], HALL[1], 2.7)
    cam = Cam()
    yaw = 0 if key[0] == "N" else 90
    cam.push(t0, t1, p, 2.0, 1.5, yaw=yaw + 15, pitch=8, lens=36, fstop=2.0)
    cam.crash(t_click, 36, 44, 0.06)
    cam.handheld(1.0)
    sfx(t_click, "click")


@S(21, 100, 101, "Click")
def s21(t0, t1):
    bolt_insert(t0, t1, ("N", -4.0), W_(100))


@S(22, 101, 103, "Back door")
def s22(t0, t1):
    door_shot(t0, t1, ("W", 3.0), None, dx=3.0)


@S(23, 103, 104, "Click")
def s23(t0, t1):
    bolt_insert(t0, t1, ("W", 3.0), W_(103))


def window_shot(t0, t1, t_slam, room="hall"):
    if room == "hall":
        R = hall_scene(t0, t1)
        sash = R["sash"][("N", 4.0)]
        wp = R["win"][("N", 4.0)]
        E = eddie(t0, t1, "panic")
        E.pose(t0, loc=(wp[0] - 1.6, wp[1] - 1.8, 0), rot=180)
        yaw = 30
    else:
        P.night_world(0.6)
        R = P.room("bath", BATH, (10, 10, 8), wall="#a8c8d8", floor="#e8e8ee", light_energy=400,
                   windows=[("E", 0.0, 4.6, 2.6, 2.6)])
        box("tub", (3, 6, 2), (BATH[0] - 2.5, BATH[1] + 1, 1), mat("tub", hexc("#f4f4f6"), 0.2), 0.3)
        sash = R["sash"][("E", 0.0)]
        wp = R["win"][("E", 0.0)]
        E = eddie(t0, t1, "panic")
        E.pose(t0, loc=(wp[0] - 2.0, wp[1], 0), rot=90)
        yaw = -130
    P.open_sash(sash, None, True, 1.3)
    z = sash.location[2]
    sash.keyframe_insert("location", index=2, frame=F(t_slam - 0.12))
    sash.location[2] = z - 1.3
    sash.keyframe_insert("location", index=2, frame=F(t_slam))
    E.pose(t0, armL=(150, 10), armR=(150, 10))
    E.pose(t_slam, armL=(110, 10), armR=(110, 10))
    cam = Cam()
    cam.push(t0, t1, (wp[0], wp[1], wp[2] - 0.5), 5.5, 4.2, yaw=yaw, pitch=4, lens=28, fstop=2.8)
    cam.crash(t_slam, 28, 34, 0.06)
    cam.handheld(1.2)
    sfx(t_slam, "slam")
    return E


@S(24, 104, 107, "Kitchen window... SLAM")
def s24(t0, t1):
    window_shot(t0, t1, W_(106))


@S(25, 107, 108, "7:59")
def s25(t0, t1):
    clock_shot(t0, t1, W_(107))


@S(26, 108, 111, "Bathroom window... SLAM")
def s26(t0, t1):
    window_shot(t0, t1, W_(110), room="bath")


@S(27, 111, 112, "8:00: the clock hits eight, crash zoom")
def s27(t0, t1):
    clock_shot(t0, t1, W_(111))
    sfx(W_(111), "sting", 0.5)


@S(28, 112, 114, "DONG, DONG: the bell swings in the tower")
def s28(t0, t1):
    street_scene(t0, t1)
    cam = Cam()
    cam.push(t0, t1, (0, 75, 27.5), 16, 13, yaw=-10, pitch=-10, lens=30, fstop=8)
    cam.handheld(1.2)
    for b in BELL:
        sfx(b, "bell")
        cam.crash(b, 30, 33, 0.06)


@S(29, 114, 117, "The town bell: wide on the tower over the rooftops")
def s29(t0, t1):
    street_scene(t0, t1)
    cam = Cam()
    cam.push(t0, t1, (0, 40, 15), 60, 52, yaw=8, pitch=6, lens=26, fstop=11)
    cam.handheld(0.6)
    sfx(t0, "drone", 0.5)


@S(30, 117, 122, "Every streetlight turned red, one after another")
def s30(t0, t1):
    street_scene(t0, t1)
    cam = Cam()
    cam.push(t0, t1, (0, 2, 4), 22, 19, yaw=-40, pitch=14, lens=22, yaw1=-30, fstop=11)
    cam.handheld(0.6)
    for i in range(4):
        sfx(RED_T + i * 0.35, "buzz", 0.6)


# ================================================================== THE KNOCKING
@S(31, 122, 126, "Then I heard it: Eddie at the window inside, frozen, red light on his face")
def s31(t0, t1):
    R = hall_scene(t0, t1, lights=200)
    wp = R["win"][("N", 4.0)]
    E = eddie(t0, t1, "scared")
    E.pose(t0, loc=(wp[0], wp[1] - 2.2, 0), rot=0)
    E.look(t0 + 0.5, 60, -5)
    light("red_out", "AREA", (wp[0], wp[1] + 3, 5), 1200, (1.0, 0.1, 0.08), 3, target=(wp[0], wp[1] - 3, 4))
    cam = Cam()
    cam.push(t0, t1, (wp[0], wp[1] - 2.2, 4.7), 4.6, 3.6, yaw=0, pitch=0, lens=30, fstop=2.2)
    cam.handheld(0.8)


def knock_shot(t0, t1, x, tk, dist=20, yaw=-20):
    street_scene(t0, t1)
    Vv = P.Visitor((x + 1.5, 4.4, 0), 180, VIS_STREET_SCALE)
    Vv.arms(t0, (40, 6), (10, 6))
    Vv.knock(tk)
    light("vis_rim", "POINT", (x + 1.5, 1, 10), 1500, (1.0, 0.15, 0.1), 1.0)
    cam = Cam()
    cam.push(t0, t1, (x, 5, 5), dist, dist * 0.85, yaw=yaw, pitch=4, lens=26, fstop=6)
    cam.handheld(0.8)
    sfx(tk, "knock")
    return Vv


@S(32, 126, 127, "KNOCK: far down the street")
def s32(t0, t1):
    knock_shot(t0, t1, -44, W_(126) + 0.05, 30, -30)


@S(33, 127, 128, "KNOCK: the next house")
def s33(t0, t1):
    knock_shot(t0, t1, -44, W_(127) + 0.05, 16, 20)


@S(34, 128, 129, "KNOCK: CU of long pale knuckles on wood")
def s34(t0, t1):
    Vv = knock_shot(t0, t1, -22, W_(128) + 0.05, 7, -40)


@S(35, 129, 135, "Something was walking down our street: the Visitor strides under red lights")
def s35(t0, t1):
    street_scene(t0, t1)
    Vv = P.Visitor((-30, 2, 0), -90, VIS_STREET_SCALE)
    Vv.walk(t0, t1, (-34, 2, 0), (-24, 2, 0))
    Vv.arms(t0, (8, 6), (8, 6))
    light("vis_rim", "POINT", (-28, -3, 11), 2000, (1.0, 0.15, 0.1), 1.0)
    cam = Cam()
    cam.key(t0, (-14, -14, 3), (-32, 3, 6), lens=26, fstop=6)
    cam.key(t1, (-12, -12, 3), (-24, 3, 6), lens=26, fstop=6)
    cam.handheld(0.8)
    sfx(t0, "footsteps", 0.5)


@S(36, 135, 139, "Knocking on every door: fingers rap the neighbour's door")
def s36(t0, t1):
    Vv = knock_shot(t0, t1, -22, W_(136), 11, 35)
    Vv.knock(W_(138))
    sfx(W_(138), "knock")


@S(37, 139, 140, "KNOCK: Eddie flinches inside")
def s37(t0, t1):
    hall_scene(t0, t1, lights=200)
    E = hall_eddie(t0, t1, "terror", loc=(0, 2))
    E.act(t0 + 0.05, "recoil", expr="terror")
    cam = Cam()
    cam.push(t0, t1, (HALL[0], HALL[1] + 2, 4.7), 4.4, 3.8, yaw=-10, pitch=0, lens=30, fstop=2.2)
    cam.handheld(1.4)
    sfx(t0 + 0.02, "knock")


@S(38, 140, 141, "KNOCK: the Visitor at Eddie's own front door")
def s38(t0, t1):
    knock_shot(t0, t1, 0, W_(140) + 0.05, 14, -25)


@S(39, 141, 146, "It stopped at our house: inside, Eddie stares at the front door, red glow at the crack")
def s39(t0, t1):
    R = hall_scene(t0, t1, lights=200)
    E = hall_eddie(t0, t1, "terror", loc=(-3.0, 0.5), rot=180)
    light("red_crack", "AREA", (HALL[0] - 4, HALL[1] + 6.6, 0.2), 600, (1.0, 0.08, 0.05), 2, target=(HALL[0] - 4, HALL[1] + 4, 0))
    cam = Cam()
    cam.push(t0, t1, (HALL[0] - 3.5, HALL[1] + 3, 3.5), 8.0, 6.0, yaw=-20, pitch=6, lens=24, fstop=4)
    cam.handheld(0.6)
    sfx(t0, "heartbeat")


@S(40, 146, 149, "The doorknob turned: CU, slowly")
def s40(t0, t1):
    R = hall_scene(t0, t1, lights=200)
    hinge, kn = R["door"][("N", -4.0)]
    piv = empty("knobpiv", tuple(kn.location), parent=hinge)
    kn.parent = piv
    kn.location = (0, 0, 0)
    box("knob_bar", (0.5, 0.08, 0.08), (0, -0.12, 0), mat("brass", hexc("#c9a240"), 0.3, metal=0.9), 0.02, parent=piv)
    piv.keyframe_insert("rotation_euler", index=1, frame=F(W_(147)))
    piv.rotation_euler[1] = math.radians(70)
    piv.keyframe_insert("rotation_euler", index=1, frame=F(W_(148) + 0.4))
    bpy.context.scene.frame_set(F(t0))
    p = tuple(kn.matrix_world.translation)
    cam = Cam()
    cam.push(t0, t1, p, 2.2, 1.6, yaw=10, pitch=6, lens=36, fstop=2.0)
    cam.handheld(0.6)
    sfx(W_(147), "creak", 0.6)


@S(41, 149, 150, "Locked: the bolt holds, rattling")
def s41(t0, t1):
    R = hall_scene(t0, t1, lights=200)
    hinge, kn = R["door"][("N", -4.0)]
    noise(hinge, "rotation_euler", 2, 0.02, 1.5)
    b = D.objects.get("hall_boltN-4.0")
    bpy.context.scene.frame_set(F(t0))
    p = tuple(b.matrix_world.translation)
    cam = Cam()
    cam.push(t0, t1, p, 2.4, 2.0, yaw=20, pitch=6, lens=34, fstop=2.2)
    cam.crash(t0 + 0.05, 34, 40, 0.06)
    cam.handheld(1.4)
    sfx(t0, "rattle")


@S(42, 150, 155, "It moved to the window: outside, it bends down to the kitchen window")
def s42(t0, t1):
    street_scene(t0, t1)
    Vv = P.Visitor((-4.4, 4.2, 0), 180, VIS_STREET_SCALE)
    Vv.walk(t0, t0 + 1.2, (-1.0, 4.2, 0), (-4.4, 4.2, 0))
    Vv.hip.rotation_euler[0] = 0; Vv.hip.keyframe_insert("rotation_euler", index=0, frame=F(t0 + 1.0))
    Vv.hip.rotation_euler[0] = math.radians(-28); Vv.hip.keyframe_insert("rotation_euler", index=0, frame=F(t0 + 2.2))
    light("vis_rim", "POINT", (-4.4, 0, 10), 1500, (1.0, 0.15, 0.1), 1.0)
    cam = Cam()
    cam.push(t0, t1, (-4, 5, 5), 16, 13, yaw=40, pitch=6, lens=24, fstop=6)
    cam.handheld(0.7)


def tap_shot(t0, t1, tt):
    R = hall_scene(t0, t1, lights=200)
    wp = R["win"][("N", 4.0)]
    fp = empty("tapf", (wp[0] + 0.2, wp[1] + 0.35, wp[2] + 0.2))
    Mp = mat("vis_pale", hexc("#d9d6d0"), 0.55)
    cyl("tapf_a", 0.07, 2.0, (0, 0.9, 0.6), Mp, 8, rot=(-60, 0, 0), parent=fp)
    sphere("tapf_tip", 0.07, (0, 0, 0), Mp, parent=fp, seg=8)
    for dt, y in ((-0.1, 0.25), (0.0, 0.0), (0.1, 0.25)):
        fp.location[1] = wp[1] + 0.35 + y; fp.keyframe_insert("location", index=1, frame=F(tt + dt))
    sphere("vis_eyeglint", 0.12, (wp[0] - 0.5, wp[1] + 1.6, wp[2] + 0.9), mat("glint", (1, 1, 1), 0.3, emit=(1, 1, 1), estr=8), seg=8)
    light("red_out", "AREA", (wp[0], wp[1] + 3, 5), 900, (1.0, 0.1, 0.08), 3, target=(wp[0], wp[1] - 3, 4))
    cam = Cam()
    cam.push(t0, t1, (wp[0], wp[1], wp[2]), 4.0, 3.5, yaw=-15, pitch=2, lens=30, fstop=2.4)
    cam.crash(tt, 30, 36, 0.05)
    cam.handheld(0.8)
    sfx(tt, "tap")


@S(43, 155, 156, "TAP: a long finger on the kitchen glass")
def s43(t0, t1):
    tap_shot(t0, t1, W_(155) + 0.05)


@S(44, 156, 157, "TAP")
def s44(t0, t1):
    tap_shot(t0, t1, W_(156) + 0.05)


@S(45, 157, 158, "Locked: Eddie backs away from the window")
def s45(t0, t1):
    R = hall_scene(t0, t1, lights=200)
    wp = R["win"][("N", 4.0)]
    E = eddie(t0, t1, "terror")
    E.pose(t0, loc=(wp[0], wp[1] - 2.5, 0), rot=180)
    E.pose(t1, loc=(wp[0], wp[1] - 4.0, 0))
    E.act(t0, "recoil")
    light("red_out", "AREA", (wp[0], wp[1] + 3, 5), 1200, (1.0, 0.1, 0.08), 3, target=(wp[0], wp[1] - 3, 4))
    cam = Cam()
    cam.push(t0, t1, (wp[0], wp[1] - 3, 4.5), 5.5, 5.0, yaw=-30, pitch=2, lens=26, fstop=3)
    cam.handheld(1.0)


# ================================================================== UPSTAIRS
@S(46, 158, 164, "Then, upstairs, a creak: Eddie at the foot of the stairs looks up")
def s46(t0, t1):
    hall_scene(t0, t1, lights=200)
    E = eddie(t0, t1, "scared")
    E.pose(t0, loc=(HALL[0] - 4.5, HALL[1] - 1.0, 0), rot=90)
    E.look(W_(160), 10, -30)
    E.face(W_(160), "lookup")
    cam = Cam()
    cam.push(t0, t1, (HALL[0] - 4.5, HALL[1] - 1.0, 4.5), 5.0, 4.0, yaw=55, pitch=-12, lens=26, fstop=3)
    cam.handheld(0.8)
    sfx(W_(163), "creak")


@S(47, 164, 170, "A cold breeze: frost breath from Eddie's mouth, he shivers")
def s47(t0, t1):
    hall_scene(t0, t1, lights=200)
    E = eddie(t0, t1, "scared")
    E.pose(t0, loc=(HALL[0] - 4.5, HALL[1] - 1.0, 0), rot=60)
    for i in range(8):
        E.pose(t0 + 0.3 + i * 0.12, torso=(0, 0, 2 * (-1) ** i))
    Mb = mat("breath", (0.85, 0.92, 1.0), 0.9, emit=(0.6, 0.7, 0.9), estr=0.8, alpha=0.35)
    for i in range(6):
        ts = W_(168) + i * 0.15
        ob = sphere(f"br{i}", 0.2, (0, -0.8, 4.3), Mb, parent=E.root, seg=10)
        ob.scale = (0.01,) * 3; ob.keyframe_insert("scale", frame=F(ts))
        ob.scale = (1.4, 1.4, 1.0); ob.keyframe_insert("scale", frame=F(ts + 0.3))
        ob.keyframe_insert("location", frame=F(ts))
        ob.location = (random.uniform(-0.4, 0.4), -2.0, 4.6)
        ob.scale = (0.01,) * 3; ob.keyframe_insert("location", frame=F(ts + 0.9)); ob.keyframe_insert("scale", frame=F(ts + 0.9))
    cam = Cam()
    cam.push(t0, t1, (HALL[0] - 4.5, HALL[1] - 1.0, 4.6), 4.6, 3.8, yaw=60 + 15, pitch=0, lens=30, fstop=2.4)
    cam.handheld(0.8)
    sfx(t0, "wind", 0.7)


@S(48, 170, 177, "Lily's window was wide open: outside, the Visitor slowly turns its head up toward it")
def s48(t0, t1):
    street_scene(t0, t1, lily_open=True)
    P.curtains("ec", (LILY_WIN_EXT[0], LILY_WIN_EXT[1] + 0.3, LILY_WIN_EXT[2] + 1.6), "S", 2.4, 3.0, blow=True)
    Vv = P.Visitor((-2.5, 4.2, 0), 180, VIS_STREET_SCALE)
    Vv.neck.rotation_euler[2] = 0; Vv.neck.keyframe_insert("rotation_euler", index=2, frame=F(t0 + 0.4))
    Vv.neck.rotation_euler[2] = math.radians(70); Vv.neck.keyframe_insert("rotation_euler", index=2, frame=F(t0 + 2.4))
    light("vis_rim", "POINT", (-2.5, 0, 10), 1500, (1.0, 0.15, 0.1), 1.0)
    cam = Cam()
    cam.push(t0, t1, (1, 6, 8), 17, 13, yaw=-20, pitch=-6, lens=24, fstop=6)
    cam.handheld(0.7)
    sfx(W_(175), "sting", 0.6)


@S(49, 177, 180, "I ran upstairs: Eddie bolts up the stairs")
def s49(t0, t1):
    hall_scene(t0, t1, lights=200)
    E = eddie(t0, t1, "panic")
    E.run(t0, t1, (HALL[0] - 7, HALL[1] - 6, 0), (HALL[0] - 7, HALL[1] + 0.5, 5.4))
    cam = Cam()
    cam.push(t0, t1, (HALL[0] - 7, HALL[1] - 3, 4.5), 8, 7.5, yaw=80, pitch=8, lens=22, fstop=4)
    cam.handheld(1.4)
    sfx(t0, "footsteps")


@S(50, 180, 183, "Lily was asleep: CU in bed, moonlight, nightlight")
def s50(t0, t1):
    lily_scene(t0, t1)
    L = lily_in_bed(t0, t1)
    bx, by = P.BED
    cam = Cam()
    cam.push(t0, t1, (bx, by + 1.6, 2.4), 4.6, 3.6, yaw=20, pitch=62, lens=30, fstop=2.4)
    cam.handheld(0.5)


@S(51, 183, 191, "Ten long, pale fingers curled over the windowsill")
def s51(t0, t1):
    lily_scene(t0, t1)
    lily_in_bed(t0, t1)
    sp = sill_point()
    P.sill_hands("sh", sp, t_curl=(W_(186), W_(188)))
    for h in (D.objects.get("sh_h-1"), D.objects.get("sh_h1")):
        h.location[1] += 1.2; h.keyframe_insert("location", index=1, frame=F(t0))
        h.location[1] -= 1.2; h.keyframe_insert("location", index=1, frame=F(W_(185)))
    cam = Cam()
    cam.push(t0, t1, (sp[0], sp[1] - 0.6, sp[2] + 0.2), 3.6, 2.6, yaw=-10, pitch=20, lens=30, fstop=2.4)
    cam.handheld(0.6)
    sfx(W_(187), "creak", 0.8)


@S(52, 191, 198, "Then a face rose into the window")
def s52(t0, t1):
    lily_scene(t0, t1)
    lily_in_bed(t0, t1)
    P.sill_hands("sh", sill_point())
    visitor_at_window(t0, t1, rise=(W_(193), W_(197)))
    wx, wy, wz = P.LILY_WIN
    cam = Cam()
    cam.push(t0, t1, (wx, wy, wz), 9.0, 7.5, yaw=-10, pitch=-4, lens=24, fstop=4)
    cam.handheld(0.6)
    sfx(W_(193), "rise", 0.8)


@S(53, 198, 201, "Huge black eyes: ECU")
def s53(t0, t1):
    lily_scene(t0, t1)
    visitor_at_window(t0, t1)
    P.sill_hands("sh", sill_point())
    wx, wy, wz = P.LILY_WIN
    cam = Cam()
    cam.push(t0, t1, (wx, wy + 1.2, wz + 1.0), 3.8, 3.0, yaw=0, pitch=-2, lens=34, fstop=2.4)
    cam.crash(W_(198), 34, 42, 0.08)
    cam.handheld(0.6)
    sfx(W_(198), "sting")


@S(54, 201, 206, "A smile way too wide: slow push on the grin")
def s54(t0, t1):
    lily_scene(t0, t1)
    visitor_at_window(t0, t1)
    P.sill_hands("sh", sill_point())
    wx, wy, wz = P.LILY_WIN
    cam = Cam()
    cam.push(t0, t1, (wx, wy + 1.0, wz + 0.45), 4.2, 2.8, yaw=8, pitch=-4, lens=34, fstop=2.4)
    cam.handheld(0.5)
    sfx(t0, "whisper", 0.6)


# ================================================================== THE TURN
@S(55, 206, 210, "Then I noticed something: Eddie in the doorway, eyes narrowing")
def s55(t0, t1):
    lily_scene(t0, t1)
    E = eddie(t0, t1, "scared")
    E.pose(t0, loc=(P.LILY[0] + 2.5, P.LILY[1] - 4.0, 0), rot=180)
    E.face(W_(208), "sus")
    cam = Cam()
    cam.push(t0, t1, (P.LILY[0] + 2.5, P.LILY[1] - 4.0, 4.7), 4.4, 3.6, yaw=180 - 10, pitch=0, lens=30, fstop=2.2)
    cam.handheld(0.7)


@S(56, 210, 219, "Its fingers stopped at the edge of the windowsill: they press against an invisible wall")
def s56(t0, t1):
    lily_scene(t0, t1)
    visitor_at_window(t0, t1)
    sp = sill_point()
    hands = P.sill_hands("sh", sp, curled=False)
    for h in hands:
        for dt in (0.0, 0.6, 1.2, 1.8, 2.4):
            h.location[1] = sp[1] + 0.6; h.keyframe_insert("location", index=1, frame=F(t0 + 0.5 + dt))
            h.location[1] = sp[1] + 0.45; h.keyframe_insert("location", index=1, frame=F(t0 + 0.8 + dt))
    wx, wy, wz = P.LILY_WIN
    pane = plane("barrier", 3.4, 4.0, (wx, wy - 0.05, wz), mat("barrier", hexc("#8ab4ff"), 0.2, emit=hexc("#8ab4ff"), estr=1.2,
                 alpha=0.12), rot=(90, 0, 0))
    cam = Cam()
    cam.push(t0, t1, (sp[0], sp[1] - 0.5, sp[2] + 0.3), 3.6, 2.8, yaw=-35, pitch=16, lens=30, fstop=2.4)
    cam.handheld(0.5)
    sfx(t0 + 0.5, "glitch", 0.4)


@S(57, 219, 227, "It couldn't cross the frame: it pushes, the barrier shimmers")
def s57(t0, t1):
    lily_scene(t0, t1)
    Vv = visitor_at_window(t0, t1)
    P.sill_hands("sh", sill_point(), curled=False)
    noise(Vv.root, "location", 1, 0.08, 3)
    wx, wy, wz = P.LILY_WIN
    plane("barrier", 3.4, 4.0, (wx, wy - 0.05, wz), mat("barrier", hexc("#8ab4ff"), 0.2, emit=hexc("#8ab4ff"), estr=1.2,
          alpha=0.12), rot=(90, 0, 0))
    cam = Cam()
    cam.push(t0, t1, (wx, wy, wz), 8.0, 6.5, yaw=25, pitch=-2, lens=24, fstop=4)
    cam.handheld(0.6)


@S(58, 227, 232, "It had to be invited: Eddie's realisation")
def s58(t0, t1):
    lily_scene(t0, t1)
    E = eddie(t0, t1, "shock")
    E.pose(t0, loc=(P.LILY[0] + 2.5, P.LILY[1] - 2.5, 0), rot=180)
    E.face(W_(231), "gasp")
    cam = Cam()
    cam.push(t0, t1, (P.LILY[0] + 2.5, P.LILY[1] - 2.5, 4.7), 4.0, 3.2, yaw=180 + 12, pitch=0, lens=32, fstop=2.2)
    cam.crash(W_(231), 32, 38, 0.08)
    cam.handheld(0.7)


@S(59, 232, 236, "And an open window: wide shot, the window gaping, curtains streaming")
def s59(t0, t1):
    lily_scene(t0, t1)
    lily_in_bed(t0, t1)
    visitor_at_window(t0, t1)
    P.sill_hands("sh", sill_point(), curled=False)
    cam = Cam()
    cam.push(t0, t1, (P.LILY[0], P.LILY[1] + 2, 3.5), 7.0, 5.8, yaw=-20, pitch=4, lens=20, fstop=5)
    cam.handheld(0.5)


@S(60, 236, 239, "Is an invitation: the smile stretches, Eddie's jaw sets")
def s60(t0, t1):
    lily_scene(t0, t1)
    Vv = visitor_at_window(t0, t1)
    Vv.head_tilt(t0, 0)
    Vv.head_tilt(t1, 20)
    P.sill_hands("sh", sill_point(), curled=False)
    E = eddie(t0, t1, "determined")
    E.pose(t0, loc=(P.LILY[0] + 1.5, P.LILY[1] + 1.0, 0), rot=180)
    wx, wy, wz = P.LILY_WIN
    cam = Cam()
    cam.push(t0, t1, (wx - 0.5, wy - 2.5, 4.6), 6.5, 5.5, yaw=-40, pitch=0, lens=26, fstop=3)
    cam.handheld(0.7)
    sfx(W_(238), "rise", 0.7)


# ================================================================== SLAM
@S(61, 239, 248, "So I grabbed the window and slammed it shut")
def s61(t0, t1):
    lily_scene(t0, t1, slam_t=W_(248))
    Vv = visitor_at_window(t0, t1)
    P.sill_hands("sh", sill_point(), curled=False)
    E = eddie(t0, t1, "determined")
    wx, wy, wz = P.LILY_WIN
    E.run(t0, W_(242), (P.LILY[0] + 2.5, P.LILY[1] - 2, 0), (wx, wy - 1.6, 0))
    E.act(W_(242), "reach", expr="angry")
    E.pose(W_(245), armL=(160, 10), armR=(160, 10))
    E.pose(W_(248) - 0.05, armL=(110, 10), armR=(110, 10))
    cam = Cam()
    cam.push(t0, t1, (wx, wy - 1.5, 4.5), 8.0, 6.0, yaw=-30, pitch=4, lens=24, fstop=3)
    cam.handheld(1.2)
    sfx(W_(240), "whoosh", 0.6)


@S(62, 248, 249, "SLAM!")
def s62(t0, t1):
    lily_scene(t0, t1, slam_t=t0 + 0.05)
    Vv = visitor_at_window(t0, t1)
    wx, wy, wz = P.LILY_WIN
    cam = Cam()
    cam.push(t0, t1, (wx, wy, wz + 0.3), 4.6, 4.0, yaw=-10, pitch=4, lens=28, fstop=2.4)
    cam.crash(t0 + 0.05, 30, 40, 0.06)
    cam.handheld(2.0)
    sfx(t0 + 0.05, "slam")
    sfx(t0 + 0.05, "boom", 0.5)


@S(63, 249, 256, "It screamed and vanished into the dark: outside, it drops away from the wall")
def s63(t0, t1):
    street_scene(t0, t1, lily_open=False)
    Vv = P.Visitor((4.4, 5.6, 0), 0, VIS_STREET_SCALE)
    Vv.arms(t0, (150, 30), (150, 30))
    Vv.at(t0, (4.4, 5.6, 0))
    Vv.at(W_(250) + 0.5, (4.4, 6.5, 0))
    Vv.at(W_(253), (4.4, -30, -10))
    light("vis_rim", "POINT", (4.4, 2, 12), 1500, (1.0, 0.15, 0.1), 1.0)
    cam = Cam()
    cam.push(t0, t1, (3, 7, 7), 20, 24, yaw=-15, pitch=6, lens=24, fstop=6)
    cam.handheld(1.4)
    sfx(W_(250), "screech")


# ================================================================== CLIFFHANGER
@S(64, 256, 259, "I hugged Lily")
def s64(t0, t1):
    lily_scene(t0, t1, open_window=False)
    bx, by = P.BED
    L = P.lily(t0, t1, "relief")
    L.pose(t0, loc=(bx, by + 0.5, 1.8), rot=0, legL=(85, 4), legR=(85, -4))
    E = eddie(t0, t1, "relief")
    E.pose(t0, loc=(bx + 0.2, by - 1.6, 0), rot=180)
    E.pose(t0 + 0.3, armL=(80, -40), armR=(80, -40), torso=(0, 15, 0))
    cam = Cam()
    cam.push(t0, t1, (bx, by - 0.5, 4.0), 6.0, 5.0, yaw=-20, pitch=8, lens=24, fstop=3)
    cam.handheld(0.5)
    sfx(t0, "aww", 0.3)


@S(65, 259, 262, "We were safe: calm wide of the room, window shut, nightlight glowing")
def s65(t0, t1):
    lily_scene(t0, t1, open_window=False)
    bx, by = P.BED
    L = P.lily(t0, t1, "relief")
    L.pose(t0, loc=(bx, by + 0.5, 1.8), rot=0, legL=(85, 4), legR=(85, -4))
    E = eddie(t0, t1, "relief")
    E.pose(t0, loc=(bx + 0.2, by - 1.6, 0), rot=180, armL=(80, -40), armR=(80, -40), torso=(0, 15, 0))
    cam = Cam()
    cam.push(t0, t1, (P.LILY[0], P.LILY[1], 3.0), 6.0, 5.5, yaw=20, pitch=10, lens=18, fstop=6)
    cam.handheld(0.3)


@S(66, 262, 268, "Then she woke up and whispered: Lily's eyes open")
def s66(t0, t1):
    lily_scene(t0, t1, open_window=False)
    bx, by = P.BED
    L = P.lily(t0, t1, "sleepy")
    L.pose(t0, loc=(bx, by + 0.5, 1.8), rot=0, legL=(85, 4), legR=(85, -4))
    L.face(t0, eyes="half", mouth="flat")
    L.face(W_(264), eyes="normal", mouth="o")
    cam = Cam()
    cam.push(t0, t1, (bx, by + 0.5, 1.8 + 4.62 * 0.78), 3.6, 2.8, yaw=0, pitch=0, lens=32, fstop=2.2)
    cam.handheld(0.5)


@S(67, 268, 274, "Eddie, I didn't open my window: Lily whispering, scared")
def s67(t0, t1):
    lily_scene(t0, t1, open_window=False)
    bx, by = P.BED
    L = P.lily(t0, t1, "scared")
    L.pose(t0, loc=(bx, by + 0.5, 1.8), rot=-20, legL=(85, 4), legR=(85, -4))
    lips(L, t0, t1)
    cam = Cam()
    cam.push(t0, t1, (bx, by + 0.5, 1.8 + 4.62 * 0.78), 3.4, 2.6, yaw=-20, pitch=0, lens=34, fstop=2.0)
    cam.handheld(0.5)


@S(68, 274, 277, "Then who did?: Eddie's terror")
def s68(t0, t1):
    lily_scene(t0, t1, open_window=False)
    bx, by = P.BED
    E = eddie(t0, t1, "terror")
    E.pose(t0, loc=(bx + 0.2, by - 1.6, 0), rot=180)
    cam = Cam()
    cam.push(t0, t1, (bx + 0.2, by - 1.6, 4.7), 4.0, 3.2, yaw=180 + 10, pitch=0, lens=32, fstop=2.0)
    cam.crash(t0 + 0.05, 32, 38, 0.08)
    cam.handheld(1.0)
    sfx(t0, "heartbeat")


@S(69, 277, 284, "Behind us, the closet door creaked open: darkness, two eyes, then black")
def s69(t0, t1):
    lily_scene(t0, t1, open_window=False, closet_t=W_(279))
    bx, by = P.BED
    L = P.lily(t0, t1, "terror")
    L.pose(t0, loc=(bx, by + 0.5, 1.8), rot=-60, legL=(85, 4), legR=(85, -4))
    E = eddie(t0, t1, "terror")
    E.pose(t0, loc=(bx + 0.4, by - 1.6, 0), rot=-90)
    cx, cy = P.LILY[0] + 7.6, P.LILY[1] - 2.0
    for s in (-1, 1):
        e = sphere(f"closet_eye{s}", 0.16, (cx + 0.4, cy + s * 0.35, 4.6), mat("closet_eye", (1, 1, 1), 0.3, emit=hexc("#f4f0e2"),
                   estr=12), (0.6, 1.4, 0.55), seg=10)
        sets.set_obj_visible(e, W_(282) - 1 / 30, False)
        sets.set_obj_visible(e, W_(282), True)
    cam = Cam()
    cam.push(t0, t1, (cx - 1, cy, 3.6), 11, 6.5, yaw=-95, pitch=2, lens=26, fstop=4)
    cam.handheld(0.6)
    black_cover(cam, min(W_(283) + 2.2, t1 - 0.6))
    sfx(W_(280), "creak")
    sfx(W_(282), "sting")
    sfx(W_(283) + 2.2, "boom", 0.6)


@S(70, 284, None, "OUTRO: lights on, Eddie and Lily cheer: like and subscribe for part 2!")
def s70(t0, t1):
    lily_scene(t0, t1, open_window=False, bright=True)
    P.fill((P.LILY[0], P.LILY[1] - 5, 6), (P.LILY[0], P.LILY[1], 3), 1500, (1.0, 0.9, 0.8), 8)
    E = eddie(t0, t1, "joy")
    E.pose(t0, loc=(P.LILY[0] + 1.6, P.LILY[1] - 1.0, 0), rot=10)
    E.act(t0, "cheer", expr="joy")
    E.jump(t0 + 0.1, 1.2, 0.45)
    L = P.lily(t0, t1, "joy")
    L.pose(t0, loc=(P.LILY[0] - 0.6, P.LILY[1] - 1.0, 0), rot=-10)
    L.act(t0, "wave")
    lips(E, t0, t1)
    confetti("cf", (P.LILY[0] + 0.5, P.LILY[1] - 1, 7), (5, 3, 1), t0 + 0.1, dur=1.4, n=60)
    P.sign("p2", "PART 2?", (P.LILY[0] + 0.5, P.LILY[1] + 2.5, 6.6), 1.0, "#ff3a2a", emit=3.0)
    cam = Cam()
    cam.push(t0, t1, (P.LILY[0] + 0.5, P.LILY[1] - 1.0, 4.4), 4.8, 4.4, yaw=0, pitch=4, lens=16, fstop=5)
    cam.handheld(0.6)
    sfx(t0, "cheer", 0.7)
    sfx(t0, "confetti", 0.6)
