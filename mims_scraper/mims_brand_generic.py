"""
Scraper MIMS Indonesia -> 2 file Excel terpisah: BRAND dan GENERIC.

Dua cara mengambil daftar obat (bisa satu per satu):
  1. ALFABET  : https://www.mims.com/indonesia/browse/alphabet/<huruf>?cat=drug
       python mims_brand_generic.py alphabet            # semua huruf a-z
       python mims_brand_generic.py alphabet a          # huruf a saja
       python mims_brand_generic.py alphabet a b c
  2. KELAS    : kelas MIMS (1a, 1b, ... 40c), brand dan generic
       python mims_brand_generic.py class               # semua kelas di CLASSES
       python mims_brand_generic.py class 1a            # kelas 1a saja
       python mims_brand_generic.py class 1a 1b --mtype generic
  SEMUA SEKALIGUS (tanpa pilih apa-apa):
       python mims_brand_generic.py                     # semua kelas + alfabet a-z
  Gabung ulang CSV ke Excel tanpa scraping:
       python mims_brand_generic.py merge

Hasil:
  output_mims/mims_brand.xlsx, output_mims/mims_generic.xlsx (+ versi .csv)
  output_mims/debug/   -> HTML + screenshot kalau sebuah halaman tidak berisi link obat

Penting:
  - Browser dibuka sebagai JENDELA BIASA (bukan headless) dengan profil tersimpan di
    folder "mims_browser_profile". Kalau muncul pemeriksaan Cloudflare / "Verify you
    are human", selesaikan sendiri di jendela itu; script menunggu sampai 3 menit.
    Kalau kamu login MIMS di jendela itu, login-nya juga tersimpan untuk run berikutnya.
  - CHECKPOINT: progres disimpan setiap selesai 1 obat di output_mims/parts/<job>.csv.
    Kalau terputus, jalankan lagi: obat yang sudah diambil dilewati, dan kelas/huruf yang
    sudah tuntas (ada file <job>.done) tidak dibuka lagi. Hapus file .done untuk mengulang.
  - Perhatikan Terms of Use MIMS dan jangan percepat jeda antar request.

Install (sekali):
    pip install playwright pandas openpyxl
    playwright install chromium
"""
import argparse
import asyncio
import random
import re
import string
import sys
from pathlib import Path
from urllib.parse import parse_qs, quote_plus, urlparse

import pandas as pd
from playwright.async_api import async_playwright

# (Windows: Python 3.8+ sudah memakai Proactor event loop secara default, tidak perlu diset.)

# ================= CONFIG =================
BASE = "https://www.mims.com/indonesia"
OUTPUT_DIR = Path("output_mims")
PROFILE_DIR = Path("mims_browser_profile")
MAX_PAGE_RETRY = 3
MAX_DETAIL_RETRY = 3
MAX_PAGES = 200                       # pengaman agar paging tidak berputar terus
DELAY_BETWEEN_DETAILS = (3.0, 6.0)    # detik; lebih pelan = lebih jarang muncul captcha
CHALLENGE_WAIT = 900                  # detik menunggu kamu menyelesaikan captcha / cek "bukan robot"
LOGIN_FILE = Path("login.txt")        # baris 1 = email MIMS, baris 2 = password (opsional, untuk auto login)
EXIT_NEED_HUMAN = 2                   # kode keluar: perlu tindakan manusia -> .bat TIDAK restart otomatis
EXCEL_CELL_LIMIT = 32767
MTYPES = ["brand", "generic"]

# ================= DAFTAR KELAS MIMS =================
# (kode, nama kelas persis seperti di MIMS). Tambahkan kelas 2a, 3a, 4a, ... di sini
# dengan menyalin namanya dari halaman MIMS.
CLASSES = [
    # 1. Gastrointestinal & Hepatobiliary System
    ("1a", "Antacids, Antireflux Agents & Antiulcerants"),
    ("1b", "GIT Regulators, Antiflatulents & Anti-Inflammatories"),
    ("1c", "Antispasmodics"),
    ("1d", "Antidiarrheals"),
    ("1e", "Laxatives, Purgatives"),
    ("1f", "Digestives"),
    ("1g", "Cholagogues, Cholelitholytics & Hepatic Protectors"),
    ("1h", "Anorectal Preparations"),
    ("1i", "Antiemetics"),
    ("1j", "Other Gastrointestinal Drugs"),
    # 5. Musculo-Skeletal System
    ("5a", "Disease-Modifying Anti-Rheumatic Drugs (DMARDs)"),
    ("5b", "Hyperuricemia & Gout Preparations"),
    ("5c", "Muscle Relaxants"),
    ("5d", "Anti-Inflammatory Enzymes"),
    ("5e", "Neuromuscular Disorder Drugs"),
    ("5f", "Other Drugs Acting on Musculo-Skeletal System"),
    # 6. Hormones
    ("6a", "Androgens & Related Synthetic Drugs"),
    ("6b", "Oestrogens, Progesterones & Related Synthetic Drugs"),
    ("6c", "Combined Sex Hormones"),
    ("6d", "Corticosteroid Hormones"),
    ("6e", "Trophic Hormones & Related Synthetic Drugs"),
    ("6f", "Anabolic Agents"),
    ("6g", "Other Drugs Affecting Hormonal Regulation"),
    # 7. Contraceptive Agents
    ("7a", "Oral Contraceptives"),
    ("7b", "Depot Contraceptives"),
    ("7c", "Other Contraceptives"),
    # 8. Anti-Infectives (Systemic)
    ("8a", "Aminoglycosides"), ("8b", "Cephalosporins"), ("8c", "Penicillins"),
    ("8d", "Other Beta-Lactams"), ("8e", "Chloramphenicols"), ("8f", "Macrolides"),
    ("8g", "Quinolones"), ("8h", "Tetracyclines"), ("8i", "Sulphonamides"),
    ("8j", "Antibacterial Combinations"), ("8k", "Other Antibiotics"), ("8l", "Anti-TB Agents"),
    ("8m", "Antileprotics"), ("8n", "Antifungals"), ("8p", "Antivirals"),
    ("8q", "Anthelmintics"), ("8r", "Antimalarials"), ("8s", "Antiamoebics"),
    ("8t", "Other Antiprotozoal Agents"),
    # 9. Oncology
    ("9a", "Cytotoxic Chemotherapy"), ("9b", "Cancer Hormone Therapy"),
    ("9c", "Cancer Immunotherapy"), ("9d", "Targeted Cancer Therapy"),
    ("9e", "Supportive Care Therapy"),
    # 10. Genito-Urinary System
    ("10a", "Preparations for Vaginal Conditions"), ("10b", "Urinary Antiseptics"),
    ("10c", "Drugs Acting on the Uterus"),
    ("10d", "Drugs for Erectile Dysfunction & Ejaculatory Disorders"),
    ("10e", "Drugs for Bladder & Prostate Disorders"),
    ("10f", "Other Drugs Acting on the Genito-Urinary System"),
    # 11. Endocrine & Metabolic System
    ("11a", "Insulin Preparations"), ("11b", "Antidiabetic Agents"), ("11c", "Thyroid Hormones"),
    ("11d", "Antithyroid Agents"), ("11e", "Anti-Obesity Agents"),
    ("11f", "Agents Affecting Bone Metabolism"), ("11g", "Other Agents Affecting Metabolism"),
    # 12. Allergy & Immune System
    ("12a", "Antihistamines & Antiallergics"), ("12b", "Vaccines, Antisera & Immunologicals"),
    ("12c", "Immunosuppressants"),
    # 13. Nutrition
    ("13a", "Infant Nutritional Products"), ("13b", "Enteral/Nutritional Products"),
    ("13c", "Parenteral Nutritional Products"), ("13d", "Electrolytes"),
    # 14. Eye
    ("14a", "Eye Anti-Infectives & Antiseptics"), ("14b", "Eye Antiseptics with Corticosteroids"),
    ("14c", "Eye Corticosteroids"), ("14d", "Mydriatic Drugs"), ("14e", "Miotic Drugs"),
    ("14f", "Antiglaucoma Preparations"),
    ("14g", "Ophthalmic Decongestants, Anesthetics, Anti-Inflammatories"),
    ("14h", "Ophthalmic Lubricants"), ("14i", "Other Eye Preparations"),
    # 15. Ear & Mouth / Throat
    ("15a", "Ear Anti-Infectives & Antiseptics"), ("15b", "Ear Antiseptics with Corticosteroids"),
    ("15c", "Ear Corticosteroids"), ("15d", "Other Ear Preparations"),
    ("15e", "Preparations for Oral Ulceration & Inflammation"),
    ("15f", "Oropharyngeal Anti-Infectives"),
    # 16. Dermatological Therapy
    ("16a", "Topical Antibiotics"), ("16b", "Topical Antifungals & Antiparasites"),
    ("16c", "Topical Antivirals"), ("16d", "Topical Anti-Infectives with Corticosteroids"),
    ("16e", "Topical Corticosteroids"), ("16f", "Acne Treatment Preparations"),
    ("16g", "Topical Antihistamines/Antipruritics"),
    ("16h", "Psoriasis, Seborrhea & Ichthyosis Preparations"),
    ("16i", "Warts & Calluses Preparations"), ("16j", "Skin Antiseptics & Disinfectants"),
    ("16k", "Other Dermatologicals"),
    # 17. Anaesthetics, Surgical Preparations & Wound Care
    ("17a", "Anaesthetics - Local & General"), ("17b", "Neuromuscular Blocking Agents"),
    ("17c", "Surgical Dressings & Wound Care"),
    # 18. Antidotes, Detoxifying Agents & Drugs Used in Substance Dependence
    ("18a", "Antidotes & Detoxifying Agents"), ("18b", "Drugs Used in Substance Dependence"),
    # 19-21
    ("19", "Intravenous & Other Sterile Solutions"),
    ("20", "Radiographic & Diagnostic Agents"),
    ("21", "Other Therapeutic Products"),
    # 30. Vitamins & Minerals
    ("30a", "Vitamins A, D & E"), ("30b", "Vitamin B-Complex / with C"), ("30c", "Vitamin C"),
    ("30d", "Calcium/with Vitamins"), ("30e", "Vitamins &/or Minerals"),
    ("30f", "Vitamins & Minerals (Geriatric)"), ("30g", "Vitamins & Minerals (Paediatric)"),
    ("30h", "Vitamins & Minerals (Pre & Post Natal) / Antianemics"),
    # 31. Health Supplements & Food
    ("31a", "Appetite Enhancers"), ("31b", "Supplements & Adjuvant Therapy"),
    ("31c", "Other Complementary Health Products"),
    # 40. Dermatological & Personal Care
    ("40a", "Emollients, Cleansers & Skin Protectives"), ("40b", "Oral Care"),
    ("40c", "Personal Care"),
]


def class_url(code, name, mtype):
    return f"{BASE}/drug/search?q={quote_plus(name.lower())}&mtype={mtype}&code={code}"


def alphabet_url(letter):
    return f"{BASE}/browse/alphabet/{letter}?cat=drug"


def with_page(url, n):
    return url if n == 1 else f"{url}&page={n}"


def mtype_of(link):
    """brand/generic dari URL obat (mtype=... atau path)."""
    q = parse_qs(urlparse(link).query)
    if q.get("mtype"):
        return q["mtype"][0].lower()
    path = urlparse(link).path.lower()
    if "/generic/" in path:
        return "generic"
    return "unknown"


# ================= BROWSER HELPERS =================
async def pass_challenge(page):
    """Tunggu sampai halaman bukan halaman cek Cloudflare lagi."""
    for i in range(CHALLENGE_WAIT):
        if not await is_captcha(page):
            if i > 0:
                print("  ✅ Captcha selesai, lanjut.")
            return True
        if i == 0:
            print("  🤖 Captcha / cek 'bukan robot' muncul. Selesaikan di jendela Chrome,")
            print("     script otomatis lanjut setelah itu (menunggu sampai 15 menit)...")
            alert()
        elif i % 60 == 0:
            alert()   # bunyi lagi tiap 1 menit sebagai pengingat
        await asyncio.sleep(1)
    print("  🛑 Captcha tidak diselesaikan dalam 15 menit. Script berhenti; progres tersimpan.")
    print("     Jalankan lagi JALANKAN_SEMUA.bat untuk lanjut dari checkpoint.")
    raise SystemExit(EXIT_NEED_HUMAN)


async def is_captcha(page):
    """Deteksi halaman captcha / 'bukan robot' (Cloudflare, reCAPTCHA, hCaptcha, dll.)."""
    try:
        title = (await page.title()).lower()
        if any(t in title for t in ("just a moment", "attention required", "verify", "captcha",
                                     "robot", "security check", "access denied")):
            return True
        return await page.evaluate("""
            () => {
                if (document.querySelector('iframe[src*="captcha"], iframe[src*="challenges.cloudflare"], ' +
                    'iframe[title*="challenge" i], .g-recaptcha, .h-captcha, #challenge-form, ' +
                    '#cf-challenge-running, [data-sitekey]')) return true;
                const t = (document.body && document.body.innerText || "").slice(0, 3000).toLowerCase();
                return /verify (that )?you are (a )?human|i'?m not a robot|bukan robot|are you a robot|complete the security check|captcha/.test(t)
                       && t.length < 3000;
            }
        """)
    except Exception:
        return False


def alert():
    """Bunyi beep supaya kamu tahu perlu menyelesaikan captcha."""
    try:
        import winsound
        for _ in range(3):
            winsound.Beep(1000, 300)
    except Exception:
        print("\a", end="", flush=True)


def is_placeholder(info):
    """MIMS memberi teks 'Lorem Ipsum' ke pengunjung yang belum login."""
    vals = [str(v) for k, v in info.items() if k not in ("Name", "Source URL")]
    keys = [k for k in info if k not in ("Name", "Source URL")]
    hits = sum("lorem ipsum" in v.lower() for v in vals) + sum(k.lower().startswith("lor") for k in keys)
    return hits >= 2


async def is_logged_in(page):
    try:
        return (await page.locator("#HiddenLoginStatus").get_attribute("value")) == "yes"
    except Exception:
        return False


def read_login():
    try:
        lines = [l.strip() for l in LOGIN_FILE.read_text(encoding="utf-8").splitlines() if l.strip()]
        return (lines[0], lines[1]) if len(lines) >= 2 else None
    except Exception:
        return None


async def click_login(page):
    """Klik tombol 'Login / Masuk' di MIMS. Return True kalau ada yang diklik."""
    try:
        clicked = await page.evaluate("""
            () => {
                const vis = e => e.offsetParent !== null || e.getClientRects().length > 0;
                const els = Array.from(document.querySelectorAll("a, button, [role=button], input[type=submit]"));
                const masuk = els.find(e => vis(e) && /^\\s*masuk\\s*$/i.test(e.innerText || e.value || ""));
                const byText = masuk || els.find(e => vis(e) &&
                    /^\\s*(masuk|login|log in|sign in|log masuk)\\s*$/i.test(e.innerText || e.value || ""));
                const byHref = els.find(e => vis(e) && /login|signin|sign-in/i.test(e.getAttribute("href") || "")
                    && !/logout/i.test(e.getAttribute("href") || ""));
                const byAttr = els.find(e => vis(e) && /login|signin/i.test((e.id || "") + " " + (e.className || "")));
                const el = byText || byHref || byAttr;
                if (!el) return null;
                el.click();
                return (el.innerText || el.getAttribute("href") || "").trim().slice(0, 60);
            }
        """)
        if clicked:
            print(f"🔑 Tombol '{clicked}' diklik otomatis.")
            return True
    except Exception as e:
        print(f"  ⚠️ Gagal klik tombol login: {e}")
    return False


async def auto_login(page):
    """Klik 'Login'. Biasanya browser langsung login sendiri (sesi tersimpan); kalau ada
    login.txt dan form email/password muncul, form diisi otomatis. Captcha tetap kamu yang centang."""
    if not await click_login(page):
        return False
    await asyncio.sleep(3)
    creds = read_login()
    if creds:
        try:
            pw = page.locator('input[type="password"]').first
            await pw.wait_for(state="attached", timeout=15000)
            email, password = creds
            user_box = page.locator('input[type="email"], input[name*="mail" i], input[name*="user" i], '
                                    'input[id*="mail" i], input[id*="user" i]').first
            if await user_box.count() and await user_box.is_visible():
                await user_box.fill(email)
                if not await pw.is_visible():
                    await page.keyboard.press("Enter")
                    await pw.wait_for(state="visible", timeout=15000)
            if await pw.is_visible():
                await pw.fill(password)
                await pw.press("Enter")
                print("🔑 Email & password dari login.txt diisi.")
        except Exception:
            pass   # tidak ada form (sudah auto login) -> lanjut
    # tunggu sampai login; captcha 'verify you are human' -> kamu yang centang
    for i in range(200):
        try:
            if await is_captcha(page):
                if i % 20 == 0:
                    print("  🤖 Centang 'Verify you are human' di jendela Chrome ya...")
                    alert()
            else:
                for p in page.context.pages:   # login bisa terbuka di tab lain
                    if "mims.com" in p.url and await is_logged_in(p):
                        print("✅ Login berhasil.")
                        return True
        except Exception:
            pass
        await asyncio.sleep(3)
    return False


async def ensure_login(context):
    """Tanpa login MIMS hanya memberi isi monograf placeholder. Minta user login sekali."""
    page = await context.new_page()
    try:
        await page.goto(f"{BASE}/drug", wait_until="domcontentloaded", timeout=60000)
        await pass_challenge(page)
        if await is_logged_in(page):
            print("✅ Sudah login MIMS.")
            return True
        if await auto_login(page):
            return True
        print("\n" + "!" * 60)
        print("🔐 BELUM LOGIN. Tanpa login, MIMS hanya menampilkan isi palsu (placeholder).")
        print("   Silakan klik 'Masuk' / 'Daftar Gratis' di jendela Chrome dan login.")
        print("   Script menunggu sampai 10 menit...")
        print("!" * 60)
        for _ in range(200):
            await asyncio.sleep(3)
            try:
                for p in context.pages:
                    if "mims.com" in p.url and await is_logged_in(p):
                        print("✅ Login terdeteksi, scraping dimulai.")
                        return True
            except Exception:
                pass
        print("⚠️ Tidak login dalam 10 menit. Data yang diambil kemungkinan placeholder!")
        return False
    finally:
        await page.close()


async def save_debug(page, name):
    d = OUTPUT_DIR / "debug"
    d.mkdir(parents=True, exist_ok=True)
    safe = re.sub(r"[^A-Za-z0-9_-]+", "_", name)[:80]
    (d / f"{safe}.html").write_text(await page.content(), encoding="utf-8")
    await page.screenshot(path=str(d / f"{safe}.png"), full_page=True)
    print(f"  🐞 Halaman disimpan untuk dicek: {d / safe}.html / .png")


async def read_total(page):
    """Coba baca jumlah hasil yang ditulis MIMS di halaman daftar (mis. '32 results')."""
    try:
        txt = await page.evaluate("() => document.body.innerText")
        for pat in (r"(?:of|dari)\s+([\d.,]+)\s+(?:results?|hasil|items?|products?|drugs?|obat)\b",
                    r"([\d.,]+)\s+(?:results?|hasil|items?|products?|drugs?|obat)\s+(?:found|ditemukan)",
                    r"([\d.,]+)\s+(?:results?|hasil)\b"):
            m = re.search(pat, txt, re.I)
            if m:
                return int(re.sub(r"[.,]", "", m.group(1)))
    except Exception:
        pass
    return None


async def collect_links(page, url, debug_name):
    """Ambil semua link /drug/info/ di satu halaman daftar."""
    for attempt in range(1, MAX_PAGE_RETRY + 1):
        try:
            await page.goto(url, wait_until="domcontentloaded", timeout=60000)
            if not await pass_challenge(page):
                print("  ⚠️ Cek Cloudflare tidak selesai.")
                continue
            try:
                await page.wait_for_selector('a[href*="/drug/info/"]', timeout=15000)
            except Exception:
                pass
            links = await page.evaluate("""
                () => Array.from(document.querySelectorAll('a[href*="/drug/info/"]'))
                           .map(a => a.href.split('#')[0])
            """)
            links = list(dict.fromkeys(links))
            if links:
                return links
            if await page.locator("text=No search result found").count():
                return []   # daftar sudah habis (normal), tidak perlu debug
        except Exception as e:
            print(f"  ⚠️ Gagal buka halaman (percobaan {attempt}): {e}")
        await asyncio.sleep(3)
    await save_debug(page, debug_name)
    return None   # GAGAL (beda dengan [] = daftar memang habis)


BASIC_KEYS = {"Name", "Source URL", "Logged In", "Full Page Text", "Contents", "MIMS Class",
              "ATC Classification"}
DEBUG_COUNT = [0]


async def expand_all(page):
    """Scroll sampai bawah & klik tombol 'Show more / View full / Read more' agar semua isi muncul."""
    try:
        for _ in range(6):
            await page.mouse.wheel(0, 4000)
            await asyncio.sleep(0.3)
        await page.evaluate("""
            () => document.querySelectorAll("a,button,span,div").forEach(el => {
                const t = (el.innerText || "").trim().toLowerCase();
                if (t.length < 40 && /^(show more|read more|view more|see more|expand|view full|show all)/.test(t)
                    && !el.closest("a[href*='/drug/info/']"))
                    try { el.click(); } catch (e) {}
            })
        """)
        await asyncio.sleep(1)
    except Exception:
        pass


async def dump_samples(slugs):
    """Simpan HTML + screenshot beberapa obat ke output_mims/debug untuk dicek strukturnya."""
    async with async_playwright() as p:
        context = await p.chromium.launch_persistent_context(
            str(PROFILE_DIR), headless=False,
            viewport={"width": 1366, "height": 768}, locale="en-US", timezone_id="Asia/Jakarta")
        page = context.pages[0] if context.pages else await context.new_page()
        await ensure_login(context)
        for slug in slugs:
            url = slug if slug.startswith("http") else BASE + "/drug/info/" + slug
            try:
                await page.goto(url, wait_until="domcontentloaded", timeout=60000)
                await pass_challenge(page)
                await asyncio.sleep(3)
                await expand_all(page)
                await save_debug(page, "sample_" + url.rsplit("/", 1)[-1].replace("?", "_"))
            except Exception as e:
                print(f"  ⚠️ {url}: {e}")
        await context.close()
    print(f"\n✅ Selesai. Zip folder {OUTPUT_DIR / 'debug'} lalu kirim ke saya.")


async def open_full_prescribing(page):
    """Brand: buka tab 'Full Prescribing Info' kalau ada. Kalau tidak ada, tetap di Concise (basic)."""
    try:
        target = await page.evaluate("""
            () => {
                const a = Array.from(document.querySelectorAll("a"))
                    .find(a => /^\\s*full prescribing info(rmation)?\\s*$/i.test(a.innerText || ""));
                if (!a) return null;
                const href = a.getAttribute("href") || "";
                const here = location.href.split("#")[0];
                if (href && !href.startsWith("#") && !href.startsWith("javascript") && a.href.split("#")[0] !== here)
                    return {go: a.href};
                a.click();
                return {clicked: true};
            }
        """)
        if not target:
            return
        if target.get("go"):
            await page.goto(target["go"], wait_until="domcontentloaded", timeout=60000)
            await pass_challenge(page)
            await page.wait_for_selector("h1", state="attached", timeout=20000)
            await expand_all(page)
        else:
            await asyncio.sleep(1.5)
            await expand_all(page)
    except Exception as e:
        print(f"  ⚠️ Gagal buka Full Prescribing Info, pakai Concise: {e}")


async def scrape_detail(page, link):
    for attempt in range(1, MAX_DETAIL_RETRY + 1):
        try:
            await page.goto(link, wait_until="domcontentloaded", timeout=60000)
            await pass_challenge(page)
            await page.wait_for_function("""
                () => {
                    const h1 = document.querySelector('h1');
                    if (!h1) return false;
                    const t = h1.innerText.trim().toLowerCase();
                    return t.length > 0 && t !== 'mims' && !t.includes('mims.com');
                }
            """, timeout=20000)
            await expand_all(page)
            await open_full_prescribing(page)
            info = await page.evaluate("""
                () => {
                    const data = {};
                    // Kalau ada judul "Full Prescribing Info" di isi halaman, ambil section SESUDAHNYA saja
                    // (Full). Kalau tidak ada, pakai semua section (Concise / basic).
                    const isFullTitle = e => /^\\s*full prescribing info(rmation)?\\s*$/i.test(e.innerText || "")
                        && !e.closest("a, li, nav, ul") && e.offsetParent !== null;
                    const marker = Array.from(document.querySelectorAll("h1,h2,h3,h4,div,span,p"))
                        .filter(isFullTitle).filter(e => !Array.from(e.children).some(isFullTitle)).pop();
                    const inScope = el => !marker ||
                        (marker.compareDocumentPosition(el) & Node.DOCUMENT_POSITION_FOLLOWING);
                    const bodyText = document.body.innerText;
                    data["Prescribing Info"] = marker ? "Full"
                        : /Concise Prescribing Info/i.test(bodyText) ? "Concise"
                        : /Basic Prescribing Info/i.test(bodyText) ? "Basic" : "";
                    const h1 = document.querySelector("h1");
                    data["Name"] = h1 ? h1.innerText.trim() : null;
                    data["Source URL"] = location.href;
                    document.querySelectorAll(".monograph-header h3").forEach(h => {
                        const label = h.innerText.trim().replace(/:$/, "");
                        const val = h.nextElementSibling?.innerText.trim();
                        if (label && val && !(label in data)) data[label] = val;
                    });
                    // Semua section monograf (Contents, Indications/Uses, Dosage/Direction for Use,
                    // Administration, Contraindications, Special Precautions, Adverse Reactions,
                    // Drug Interactions, MIMS Class, ATC Classification, dst.) -> 1 kolom per judul
                    const addSection = (head, contentSel) => {
                        const title = head.innerText.trim().replace(/:$/, "");
                        if (!title) return;
                        let el = head.nextElementSibling;
                        if (contentSel) {
                            let n = head.nextElementSibling;
                            while (n && !n.matches(contentSel)) n = n.nextElementSibling;
                            if (n) el = n;
                        }
                        const content = el ? el.innerText.trim() : "";
                        if (!content) return;
                        data[title] = (title in data && data[title] !== content)
                            ? data[title] + "\\n" + content : content;
                    };
                    document.querySelectorAll(".monograph-section-header")
                        .forEach(h => { if (inScope(h)) addSection(h, ".monograph-section-content"); });
                    // Section yang hanya ada di Concise (tidak ada di Full) tetap diambil
                    if (marker) document.querySelectorAll(".monograph-section-header").forEach(h => {
                        const t = h.innerText.trim().replace(/:$/, "");
                        if (!inScope(h) && t && !(t in data)) addSection(h, ".monograph-section-content");
                    });
                    // Presentation/Packing -> dipecah per Form: "Form N" + "Packing/Price N"
                    const packRows = [];
                    document.querySelectorAll(".packing-price-header").forEach(head => {
                        if (!inScope(head)) return;
                        let box = head.nextElementSibling;
                        let n = head.nextElementSibling;
                        while (n && !n.matches(".packing-price-content")) n = n.nextElementSibling;
                        if (n) box = n;
                        if (!box) return;
                        const isHead = t => /^(form|packing\\s*\\/?\\s*&?\\s*price|packing|price)$/i.test(t);
                        const trs = box.querySelectorAll("tr");
                        if (trs.length) {                       // format tabel
                            trs.forEach(tr => {
                                const cells = Array.from(tr.querySelectorAll("td,th"))
                                    .map(c => c.innerText.trim()).filter(Boolean);
                                if (!cells.length || cells.every(isHead)) return;
                                packRows.push({form: cells[0], pack: cells.slice(1).join("; ")});
                            });
                            return;
                        }
                        // format teks: baris kemasan biasanya berisi "x 10's", "Rp", "'s", dll.
                        const isPack = t => /(\\d\\s*['’`]s\\b|[x×]\\s*\\d|\\d\\s*[x×]|rp\\s*\\d|\\(rp|\\d+\\s*(ml|g)\\s*x)/i.test(t);
                        const lines = box.innerText.split("\\n").map(t => t.trim()).filter(t => t && !isHead(t));
                        let cur = null;
                        lines.forEach(t => {
                            if (isPack(t) && cur) { cur.pack = cur.pack ? cur.pack + "; " + t : t; }
                            else { cur = {form: t, pack: ""}; packRows.push(cur); }
                        });
                    });
                    packRows.forEach((r, i) => {
                        data["Form " + (i + 1)] = r.form;
                        data["Packing/Price " + (i + 1)] = r.pack || "";
                    });
                    // Presentation/Packing memakai elemen berbeda
                    if (!packRows.length)   // gagal dipecah -> simpan teks utuh
                        document.querySelectorAll(".packing-price-header")
                            .forEach(h => addSection(h, ".packing-price-content"));
                    // Disclaimer di bawah halaman
                    const disc = Array.from(document.querySelectorAll("p,div,span,small,footer,section"))
                        .filter(e => /^\\s*Disclaimer:/i.test(e.innerText || ""))
                        .sort((a, b) => a.innerText.length - b.innerText.length)[0];
                    if (disc) data["Disclaimer"] = disc.innerText.trim().replace(/^Disclaimer:\\s*/i, "");
                    // Cadangan: SEMUA teks halaman obat, supaya tidak ada isi yang hilang
                    const main = document.querySelector(".monograph, #monograph, main, .main-content, article")
                                 || document.body;
                    data["Full Page Text"] = main.innerText.trim();
                    return data;
                }
            """)
            if info and info.get("Name") and is_placeholder(info):
                return "PLACEHOLDER"
            if info and info.get("Name"):
                info["Logged In"] = "Ya" if await is_logged_in(page) else "Tidak"
                n_sections = len([k for k in info if k not in BASIC_KEYS])
                if n_sections <= 4 and info.get("Prescribing Info") != "Basic" and DEBUG_COUNT[0] < 10:  # sedikit section -> format beda, simpan contoh
                    DEBUG_COUNT[0] += 1
                    await save_debug(page, "detail_" + link.rsplit("/", 1)[-1].replace("?", "_"))
                return info
        except SystemExit:
            raise
        except Exception:
            pass
        await pass_challenge(page)   # mungkin gagal karena captcha -> tunggu diselesaikan dulu
        await asyncio.sleep(random.uniform(2, 4))
    print(f"  ❌ Dilewati (dicoba lagi saat run berikutnya): {link}")
    return None


# ================= JOB RUNNER =================
def job_csv(job):
    return OUTPUT_DIR / "parts" / f"{job}.csv"


async def run_job(context, job, list_url, fixed_mtype=None, category=None):
    """job = nama unik (mis. 'alphabet_a' atau 'class_1a_brand')."""
    out = job_csv(job)
    out.parent.mkdir(parents=True, exist_ok=True)
    done_flag = out.with_suffix(".done")
    skip_file = out.with_suffix(".skipped.txt")
    rows = pd.read_csv(out, dtype=str).to_dict("records") if out.exists() else []
    done = {r.get("Link") for r in rows}
    skipped = set(skip_file.read_text(encoding="utf-8").split()) - done if skip_file.exists() else set()

    def save_skipped():
        left = sorted(skipped - done)
        if left:
            skip_file.write_text("\n".join(left), encoding="utf-8")
        elif skip_file.exists():
            skip_file.unlink()

    async def scrape_one(page, link):
        info = await scrape_detail(page, link)
        if info == "PLACEHOLDER":
            print("  🔐 Isi halaman masih Lorem Ipsum (placeholder) -> belum login.")
            await ensure_login(page.context)
            info = await scrape_detail(page, link)
            if info == "PLACEHOLDER":
                print("  🛑 Masih placeholder setelah menunggu login. Scraping dihentikan agar")
                print("     tidak menyimpan data palsu. Login di jendela Chrome lalu jalankan lagi.")
                raise SystemExit(EXIT_NEED_HUMAN)
        if info:
            mtype = mtype_of(link)
            if mtype == "unknown" and fixed_mtype:
                mtype = fixed_mtype
            rows.append({"Type": mtype, "Category Code": category or "", "Link": link, **info})
            done.add(link)
            skipped.discard(link)
            pd.DataFrame(rows).to_csv(out, index=False, encoding="utf-8-sig")  # checkpoint per obat
            print(f"  ✅ [{mtype}] {info['Name']}")
        else:
            skipped.add(link)          # dicatat, dicoba lagi saat run berikutnya
        save_skipped()
        await asyncio.sleep(random.uniform(*DELAY_BETWEEN_DETAILS))

    if done_flag.exists():
        if not skipped:
            print(f"⏭️  {job} sudah selesai sebelumnya, dilewati.")
            return
        # kelas sudah selesai, tapi ada obat yang dulu ter-skip -> coba lagi dulu
        print(f"🔁 {job}: mencoba ulang {len(skipped)} obat yang dulu ter-skip")
        page = await context.new_page()
        try:
            for link in sorted(skipped):
                await scrape_one(page, link)
        finally:
            await page.close()
        cf = out.with_suffix(".count.json")
        if cf.exists():
            import json
            c = json.loads(cf.read_text(encoding="utf-8"))
            c["skipped"] = len(skipped - done)
            c["saved"] = c["links_found"] - c["skipped"]
            cf.write_text(json.dumps(c), encoding="utf-8")
        print(f"🏁 {job}: masih ter-skip {len(skipped - done)} obat")
        return
    if rows:
        print(f"🔁 Resume {job}: {len(rows)} obat sudah ada")

    list_page = await context.new_page()
    detail_page = await context.new_page()
    seen_links = set()
    mims_total = None
    try:
        for n in range(1, MAX_PAGES + 1):
            url = with_page(list_url, n)
            print(f"\n🌐 [{job}] halaman {n}: {url}")
            links = await collect_links(list_page, url, f"{job}_page{n}")
            if n == 1 and links:
                mims_total = await read_total(list_page)
            if links is None:
                print(f"  ⚠️ [{job}] halaman {n} gagal dibuka. Kelas ini TIDAK ditandai selesai,")
                print("     jadi akan diulang saat run berikutnya (obat yang sudah ada tidak diambil ulang).")
                break
            new = [l for l in links if l not in seen_links]
            if not new:
                print(f"🛑 [{job}] tidak ada link baru, selesai.")
                if n > 1 or rows:   # jangan tandai selesai kalau halaman pertama gagal/kosong
                    done_flag.write_text("selesai", encoding="utf-8")
                break
            seen_links.update(new)
            print(f"  🔗 {len(new)} link obat")

            for link in new:
                if link in done:
                    continue
                await scrape_one(detail_page, link)
            pd.DataFrame(rows).to_csv(out, index=False, encoding="utf-8-sig")
    finally:
        await list_page.close()
        await detail_page.close()
    left = skipped - done
    if seen_links:
        saved = len(seen_links & done)
        count_file = out.with_suffix(".count.json")
        import json
        count_file.write_text(json.dumps({"mims_total": mims_total, "links_found": len(seen_links),
                                          "saved": saved, "skipped": len(seen_links & left)}), encoding="utf-8")
        print(f"🔎 Crosscheck {job}: MIMS {mims_total if mims_total is not None else '?'} | "
              f"link ditemukan {len(seen_links)} | tersimpan {saved} | ter-skip {len(seen_links & left)}")
    print(f"🏁 {job}: {len(rows)} obat -> {out}" + (f" | ⚠️ {len(left)} ter-skip (dicoba lagi saat run berikutnya)" if left else ""))


async def main_scrape(args):
    jobs = []
    if args.mode == "alphabet":
        letters = args.items or list(string.ascii_lowercase)
        for l in letters:
            jobs.append((f"alphabet_{l}", alphabet_url(l), None, None))
    else:
        known = {c: n for c, n in CLASSES}
        codes = args.items or [c for c, _ in CLASSES]
        for c in codes:
            if c not in known:
                print(f"⚠️ Kelas {c} belum ada di CLASSES, dilewati.")
                continue
            for m in args.mtype:
                jobs.append((f"class_{c}_{m}", class_url(c, known[c], m), m, c))

    async with async_playwright() as p:
        context = await p.chromium.launch_persistent_context(
            str(PROFILE_DIR), headless=args.headless,
            viewport={"width": 1366, "height": 768}, locale="en-US", timezone_id="Asia/Jakarta",
        )
        await ensure_login(context)
        try:
            for job, url, mtype, cat in jobs:
                print(f"\n{'=' * 60}\n🚀 {job}\n{'=' * 60}")
                try:
                    await run_job(context, job, url, mtype, cat)
                except Exception as e:
                    print(f"🚨 Error {job}: {e}")
        finally:
            await context.close()


# ================= GABUNG KE EXCEL =================
NOISE = re.compile(r"\n?\s*(Click to view .*? (detailed )?prescribing information|View ADR Reporting Link|See More)\s*$",
                   re.I | re.M)


def split_packing(text):
    """'Form\\nX\\nPacking/Price\\nY\\nForm\\n...' -> [(X, Y), ...]"""
    lines = [l.strip() for l in str(text).splitlines() if l.strip()]
    pairs, cur, mode = [], None, None
    for l in lines:
        if l.lower() == "form":
            cur = [ "", "" ]; pairs.append(cur); mode = 0
        elif l.lower() in ("packing/price", "packing"):
            if cur is None:
                cur = ["", ""]; pairs.append(cur)
            mode = 1
        elif cur is not None and mode is not None:
            cur[mode] = (cur[mode] + "; " + l) if cur[mode] else l
    return [tuple(p) for p in pairs if p[0] or p[1]]


ACTION_KEYS = ("Mechanism of Action", "Duration", "Onset", "Absorption", "Distribution", "Metabolism",
               "Excretion", "Toxicology", "Pharmacodynamics")


def split_action(text):
    """Action -> Action (Mechanism of Action), Action (Absorption), dst."""
    out, cur = {}, None
    for line in str(text).splitlines():
        line = line.strip()
        if not line or line.rstrip(":") in ("Description", "Pharmacokinetics"):
            continue
        m = re.match(r"^([A-Za-z ]{3,30}):\s*(.*)$", line)
        if m and m.group(1).strip() in ACTION_KEYS:
            cur = f"Action ({m.group(1).strip()})"; out[cur] = m.group(2).strip()
        elif cur:
            out[cur] += " " + line
    return out


def tidy_tables(x):
    """Tabel (mis. Renal Impairment: CrCl | Dosage) -> baris 'sel | sel', tanpa baris kosong berlebih."""
    if not isinstance(x, str) or "\t" not in x:
        return x
    lines = [" | ".join(c.strip() for c in l.split("\t") if c.strip()) for l in x.splitlines()]
    return re.sub(r"\n{3,}", "\n\n", "\n".join(lines)).strip()


def clean_df(df):
    # buang teks tombol/link seperti "Click to view ... prescribing information"
    for c in df.columns:
        df[c] = df[c].map(lambda x: NOISE.sub("", x).strip() if isinstance(x, str) else x)
    for c in df.columns:
        df[c] = df[c].map(tidy_tables)
    if "Action" in df:
        parts = df["Action"].map(lambda x: split_action(x) if isinstance(x, str) else {})
        for d in parts:
            for k in d:
                if k not in df:
                    df[k] = None
        for i, d in parts.items():
            for k, v in d.items():
                df.at[i, k] = v
            if d:
                df.at[i, "Action"] = None   # sudah dipecah per sub-bagian
    # satukan kolom "What are the brands available for X in Indonesia?"
    qcols = [c for c in df.columns if c.lower().startswith("what are the brands available")]
    if qcols:
        df["Brands Available in Indonesia"] = df[qcols].bfill(axis=1).iloc[:, 0]
        df = df.drop(columns=qcols)
    for c in ("Brands Available in Indonesia", "Other Known Brands"):
        if c in df:
            df[c] = df[c].map(lambda x: "; ".join(l.strip() for l in x.splitlines() if l.strip())
                              if isinstance(x, str) else x)
    # pecah Presentation/Packing -> Form N / Packing/Price N (kalau belum dipecah)
    if "Presentation/Packing" in df:
        for i, txt in df["Presentation/Packing"].items():
            if not isinstance(txt, str) or not txt.strip():
                continue
            if any(isinstance(df.at[i, c], str) and df.at[i, c] for c in df.columns if c.startswith("Form ")):
                continue
            for n, (form, pack) in enumerate(split_packing(txt), 1):
                for col, val in ((f"Form {n}", form), (f"Packing/Price {n}", pack)):
                    if col not in df:
                        df[col] = None
                    df.at[i, col] = val
        pc = [c for c in df.columns if c.startswith("Form ")]
        if pc:
            filled = df[pc].notna().any(axis=1)
            df.loc[filled, "Presentation/Packing"] = None
    # Indications and Dosage -> kolom per indikasi di sheet yang sama:
    # "Indications and Dosage 1 (Route)", "... 1 (Indication)", "... 1 (Adult)", "... 1 (Child)", dst.
    if "Indications and Dosage" in df:
        new = {}
        for i, txt in df["Indications and Dosage"].items():
            if not isinstance(txt, str) or not txt.strip():
                continue
            rows = split_indications(txt)
            if not rows:
                continue
            for n, r in enumerate(rows, 1):
                for k, v in r.items():
                    new.setdefault(f"Indications and Dosage {n} ({k})", {})[i] = v
            df.at[i, "Indications and Dosage"] = None   # sudah dipecah
        if new:
            df = pd.concat([df, pd.DataFrame(new)], axis=1)
    return df.replace("", None)


POP_RE = re.compile(r"^([A-Z][A-Za-z /-]{1,30}):\s*(.*)$")


ROUTE_WORDS = ("oral", "intravenous", "intramuscular", "subcutaneous", "topical", "ophthalmic", "otic",
               "nasal", "intranasal", "rectal", "vaginal", "inhalation", "transdermal", "sublingual",
               "buccal", "parenteral", "intrathecal", "epidural", "intradermal", "intravitreal",
               "intra-articular", "intralesional", "intravesical", "cutaneous", "dental", "local",
               "infiltration", "intraocular", "intracameral", "intracavernosal", "intraosseous",
               "intraperitoneal", "intrapleural", "intrauterine", "irrigation", "perineural",
               "respiratory", "dermal", "spinal", "iv", "im", "sc", "nebulisation", "nebulization")


def is_route(line):
    parts = [p.strip().lower() for p in re.split(r",|/|\band\b", line) if p.strip()]
    return 0 < len(parts) <= 6 and len(line) < 80 and all(
        any(p == w or p.startswith(w + " ") or p.endswith(" " + w) for w in ROUTE_WORDS) for p in parts)


def split_indications(text):
    """'Indications and Dosage' generic -> list baris: Route, Indication, Adult, Child, Elderly, ..."""
    rows, cur, last = [], None, None
    for line in [l.strip() for l in str(text).splitlines()]:
        if not line:
            continue
        m = POP_RE.match(line)
        if is_route(line):
            cur = {"Route": line}; rows.append(cur); last = "Route"
        elif cur is None:
            cur = {"Route": "", "Indication": line}; rows.append(cur); last = "Indication"
        elif last == "Route":
            cur["Indication"] = line; last = "Indication"
        elif m and len(m.group(1).split()) <= 3:
            pop = m.group(1).strip()
            cur[pop] = (cur[pop] + " " + m.group(2)).strip() if pop in cur else m.group(2)
            last = pop
        else:   # lanjutan teks sebelumnya
            cur[last] = (cur.get(last, "") + " " + line).strip()
    return rows


def indications_sheet(df):
    out = []
    if "Indications and Dosage" not in df:
        return pd.DataFrame()
    for _, r in df[df["Indications and Dosage"].notna()].iterrows():
        for n, row in enumerate(split_indications(r["Indications and Dosage"]), 1):
            out.append({"Name": r["Name"], "No": n, **row, "Link": r["Link"]})
    t = pd.DataFrame(out)
    if t.empty:
        return t
    first = ["Name", "No", "Route", "Indication", "Adult", "Child", "Elderly"]
    cols = [c for c in first if c in t] + [c for c in t if c not in first and c != "Link"] + ["Link"]
    return t[cols]


SAMPLE_SLUGS = ["aciblock", "acidrine", "acitral", "acran", "ranitidine?mtype=generic", "arcolase"]


def report_unfinished():
    """Ringkasan: kelas yang belum selesai & obat yang masih ter-skip."""
    parts = OUTPUT_DIR / "parts"
    skipped = {f.name.replace(".skipped.txt", ""): len(f.read_text(encoding="utf-8").split())
               for f in parts.glob("*.skipped.txt")}
    unfinished = [f.stem for f in parts.glob("*.csv") if not f.with_suffix(".done").exists()]
    import json
    print("\n🔎 Crosscheck jumlah per kelas (MIMS = angka di halaman daftar, '?' = tidak tertulis):")
    for f in sorted(parts.glob("*.count.json")):
        c = json.loads(f.read_text(encoding="utf-8"))
        flag = "" if c["saved"] == c["links_found"] else "  <-- belum lengkap"
        if c.get("mims_total") not in (None, c["links_found"]):
            flag += f"  <-- MIMS bilang {c['mims_total']}"
        print(f"   {f.name.replace('.count.json', ''):<28} MIMS {str(c.get('mims_total') or '?'):>5} | "
              f"link {c['links_found']:>4} | tersimpan {c['saved']:>4} | skip {c['skipped']:>3}{flag}")
    if not skipped and not unfinished:
        print("\n✅ Cek kelengkapan: semua kelas selesai, tidak ada obat yang ter-skip.")
        return True
    print("\n⚠️ Cek kelengkapan:")
    for j in sorted(unfinished):
        print(f"   - {j}: belum selesai")
    for j, n in sorted(skipped.items()):
        print(f"   - {j}: {n} obat ter-skip")
    print("   Jalankan JALANKAN_SEMUA.bat lagi -> hanya bagian ini yang diulang.")
    return False


def merge_to_excel():
    files = sorted((OUTPUT_DIR / "parts").glob("*.csv"))
    if not files:
        print("⚠️ Belum ada data di output_mims/parts")
        return
    df = pd.concat([pd.read_csv(f, dtype=str) for f in files], ignore_index=True)
    # perbaiki tipe dari link (data lama bisa tertandai brand padahal link generic)
    from_link = df["Link"].map(mtype_of)
    df["Type"] = from_link.where(from_link != "unknown", df["Type"])
    df["Category Code"] = df["Category Code"].fillna("")
    cats = df.groupby("Link")["Category Code"].apply(lambda s: "; ".join(dict.fromkeys(x for x in s if x)))
    df = df.drop_duplicates("Link").copy()
    df["Category Code"] = df["Link"].map(cats)
    df = clean_df(df)
    front = ["Type", "Name", "Category Code", "Prescribing Info", "Manufacturer", "Distributor", "Marketer",
             "Contents", "Indications/Uses", "Dosage/Direction for Use", "Indications and Dosage",
             "Renal Impairment", "Hepatic Impairment", "Reconstitution", "Incompatibility", "Administration",
             "Overdosage", "Contraindications", "Special Precautions", "Use In Pregnancy & Lactation",
             "Adverse Reactions", "Patient Counseling Information", "Monitoring Parameters",
             "Drug Interactions", "Food Interaction", "Lab Interference", "Caution For Usage", "Storage",
             "Description", "Action", "Mechanism of Action"] + [f"Action ({k})" for k in ACTION_KEYS] + [ "MIMS Class", "ATC Classification",
             "Regulatory Classification", "Pregnancy Category (US FDA)", "Chemical Structure", "References",
             "Brands Available in Indonesia", "Other Known Brands",
             "Presentation/Packing", "Disclaimer", "Link", "Source URL", "Logged In", "Full Page Text"]
    pack_cols = sorted([c for c in df.columns if re.match(r"^(Form|Packing/Price) \d+$", c)],
                       key=lambda c: (int(c.split()[-1]), not c.startswith("Form")))
    tail = [c for c in ("Link", "Source URL", "Logged In", "Full Page Text") if c in df]
    head = [c for c in front if c in df and c not in tail]
    ind_cols = [c for c in df.columns if re.match(r"^Indications and Dosage \d+ \(", c)]
    sub = {"Route": 0, "Indication": 1, "Adult": 2, "Child": 3, "Elderly": 4}
    ind_cols.sort(key=lambda c: (int(re.search(r"\d+", c).group()),
                                 sub.get(c[c.index("(") + 1:-1], 9), c))
    if ind_cols:
        pos = head.index("Indications and Dosage") + 1 if "Indications and Dosage" in head else len(head)
        head = head[:pos] + ind_cols + head[pos:]
    rest = [c for c in df.columns if c not in front and c not in pack_cols and c not in ind_cols]
    df = df[head + pack_cols + rest + tail]

    for mtype, part in df.groupby("Type"):
        part = part.dropna(axis=1, how="all")
        part.to_csv(OUTPUT_DIR / f"mims_{mtype}.csv", index=False, encoding="utf-8-sig")
        xl = part.apply(lambda col: col.map(lambda x: x[:EXCEL_CELL_LIMIT] if isinstance(x, str) else x))
        xl.to_excel(OUTPUT_DIR / f"mims_{mtype}.xlsx", index=False, sheet_name="Obat")
        print(f"📗 {mtype}: {len(part)} obat, {len(part.columns)} kolom -> {OUTPUT_DIR / f'mims_{mtype}.xlsx'}")
    if "unknown" in set(df["Type"]):
        print("ℹ️ Ada obat bertipe 'unknown' (link tanpa mtype). Kirim contoh link-nya agar bisa dipisahkan.")


if __name__ == "__main__":
    ap = argparse.ArgumentParser(description="Scraper MIMS Indonesia (brand & generic)")
    ap.add_argument("mode", nargs="?", choices=["alphabet", "class", "merge", "sample", "cek"])
    ap.add_argument("items", nargs="*", help="huruf (alphabet) atau kode kelas (class); kosong = semua")
    ap.add_argument("--mtype", nargs="+", choices=MTYPES, default=MTYPES, help="untuk mode class")
    ap.add_argument("--headless", action="store_true", help="tanpa jendela (sering diblokir Cloudflare)")
    args = ap.parse_args()

    run_all = not args.mode   # tanpa argumen = ambil SEMUA, tanpa pertanyaan
    OUTPUT_DIR.mkdir(exist_ok=True)
    if run_all:
        print("▶ Mode SEMUA: semua kelas (brand + generic), lalu alfabet a-z.")
        for mode in ("class", "alphabet"):
            asyncio.run(main_scrape(argparse.Namespace(
                mode=mode, items=[], mtype=MTYPES, headless=args.headless)))
            merge_to_excel()   # Excel diperbarui setelah tiap tahap
        report_unfinished()
        if sys.stdin and sys.stdin.isatty():
            input("\nSelesai. Tekan Enter untuk menutup...")
        sys.exit(0)

    OUTPUT_DIR.mkdir(exist_ok=True)
    if args.mode == "cek":
        report_unfinished()
        sys.exit(0)
    if args.mode == "sample":
        asyncio.run(dump_samples(args.items or SAMPLE_SLUGS))
        sys.exit(0)
    if args.mode != "merge":
        asyncio.run(main_scrape(args))
    merge_to_excel()
