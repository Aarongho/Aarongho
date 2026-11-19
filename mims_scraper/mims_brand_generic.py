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
DELAY_BETWEEN_DETAILS = (1.5, 3.0)    # detik
CHALLENGE_WAIT = 180                  # detik menunggu kamu menyelesaikan cek Cloudflare
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
        title = (await page.title()).lower()
        if not any(t in title for t in ("just a moment", "attention required", "verify")):
            return True
        if i == 0:
            print("  ⏳ Pemeriksaan Cloudflare muncul. Selesaikan di jendela browser (kalau diminta)...")
        await asyncio.sleep(1)
    return False


async def is_logged_in(page):
    try:
        return (await page.locator("#HiddenLoginStatus").get_attribute("value")) == "yes"
    except Exception:
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
    return []


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
            info = await page.evaluate("""
                () => {
                    const data = {};
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
                        .forEach(h => addSection(h, ".monograph-section-content"));
                    // Presentation/Packing -> dipecah per Form: "Form N" + "Packing/Price N"
                    const packRows = [];
                    document.querySelectorAll(".packing-price-header").forEach(head => {
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
                    return data;
                }
            """)
            if info and info.get("Name"):
                info["Logged In"] = "Ya" if await is_logged_in(page) else "Tidak"
                if len(info) <= 2:  # cuma Name + URL -> struktur halaman beda, simpan untuk dicek
                    await save_debug(page, "detail_" + link.rsplit("/", 1)[-1])
                return info
        except Exception:
            pass
        await asyncio.sleep(random.uniform(2, 4))
    print(f"  ❌ Dilewati: {link}")
    return None


# ================= JOB RUNNER =================
def job_csv(job):
    return OUTPUT_DIR / "parts" / f"{job}.csv"


async def run_job(context, job, list_url, fixed_mtype=None, category=None):
    """job = nama unik (mis. 'alphabet_a' atau 'class_1a_brand')."""
    out = job_csv(job)
    out.parent.mkdir(parents=True, exist_ok=True)
    done_flag = out.with_suffix(".done")
    if done_flag.exists():
        print(f"⏭️  {job} sudah selesai sebelumnya, dilewati.")
        return
    rows = pd.read_csv(out, dtype=str).to_dict("records") if out.exists() else []
    done = {r.get("Link") for r in rows}
    if rows:
        print(f"🔁 Resume {job}: {len(rows)} obat sudah ada")

    list_page = await context.new_page()
    detail_page = await context.new_page()
    seen_links = set()
    try:
        for n in range(1, MAX_PAGES + 1):
            url = with_page(list_url, n)
            print(f"\n🌐 [{job}] halaman {n}: {url}")
            links = await collect_links(list_page, url, f"{job}_page{n}")
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
                info = await scrape_detail(detail_page, link)
                if info:
                    # tipe dari link obat (halaman brand juga memuat link generic); kalau
                    # link tidak menyebut tipe, pakai tipe halaman pencarian
                    mtype = mtype_of(link)
                    if mtype == "unknown" and fixed_mtype:
                        mtype = fixed_mtype
                    rows.append({"Type": mtype, "Category Code": category or "", "Link": link, **info})
                    done.add(link)
                    pd.DataFrame(rows).to_csv(out, index=False, encoding="utf-8-sig")  # checkpoint per obat
                    print(f"  ✅ [{mtype}] {info['Name']}")
                await asyncio.sleep(random.uniform(*DELAY_BETWEEN_DETAILS))
            pd.DataFrame(rows).to_csv(out, index=False, encoding="utf-8-sig")
    finally:
        await list_page.close()
        await detail_page.close()
    print(f"🏁 {job}: {len(rows)} obat -> {out}")


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
    front = ["Type", "Name", "Category Code", "Manufacturer", "Distributor", "Marketer",
             "Contents", "Indications/Uses", "Dosage/Direction for Use", "Administration",
             "Overdosage", "Contraindications", "Special Precautions", "Use In Pregnancy & Lactation",
             "Adverse Reactions", "Drug Interactions", "Caution For Usage", "Storage",
             "Description", "Action", "Mechanism of Action", "MIMS Class", "ATC Classification",
             "Regulatory Classification", "Presentation/Packing", "Link", "Source URL", "Logged In"]
    pack_cols = sorted([c for c in df.columns if re.match(r"^(Form|Packing/Price) \d+$", c)],
                       key=lambda c: (int(c.split()[-1]), not c.startswith("Form")))
    tail = [c for c in ("Link", "Source URL", "Logged In") if c in df]
    head = [c for c in front if c in df and c not in tail]
    rest = [c for c in df.columns if c not in front and c not in pack_cols]
    df = df[head + pack_cols + rest + tail]

    for mtype, part in df.groupby("Type"):
        part = part.dropna(axis=1, how="all")
        part.to_csv(OUTPUT_DIR / f"mims_{mtype}.csv", index=False, encoding="utf-8-sig")
        xl = part.apply(lambda col: col.map(lambda x: x[:EXCEL_CELL_LIMIT] if isinstance(x, str) else x))
        xl.to_excel(OUTPUT_DIR / f"mims_{mtype}.xlsx", index=False)
        print(f"📗 {mtype}: {len(part)} obat, {len(part.columns)} kolom -> {OUTPUT_DIR / f'mims_{mtype}.xlsx'}")
    if "unknown" in set(df["Type"]):
        print("ℹ️ Ada obat bertipe 'unknown' (link tanpa mtype). Kirim contoh link-nya agar bisa dipisahkan.")


if __name__ == "__main__":
    ap = argparse.ArgumentParser(description="Scraper MIMS Indonesia (brand & generic)")
    ap.add_argument("mode", nargs="?", choices=["alphabet", "class", "merge"])
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
        if sys.stdin and sys.stdin.isatty():
            input("\nSelesai. Tekan Enter untuk menutup...")
        sys.exit(0)

    OUTPUT_DIR.mkdir(exist_ok=True)
    if args.mode != "merge":
        asyncio.run(main_scrape(args))
    merge_to_excel()
