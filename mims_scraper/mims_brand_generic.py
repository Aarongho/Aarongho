"""
Scraper MIMS Indonesia -> 2 file Excel terpisah: BRAND dan GENERIC.

Berdasarkan mims_huge_1.py. Perubahan:
  - Setiap subkelas di-scrape dua kali: mtype=brand dan mtype=generic.
  - Kolom tambahan: Type (brand/generic), Category Code, Category Query.
  - Hasil per subkelas tetap disimpan sebagai CSV (bisa resume), lalu
    di akhir digabung jadi:
        output_mims/mims_brand.xlsx
        output_mims/mims_generic.xlsx
  - Link yang sudah pernah di-scrape dilewati (resume per link, bukan per halaman).
  - Teks > 32.767 karakter dipotong khusus di Excel (batas Excel); CSV tetap utuh.

Jalankan di komputer sendiri:
    pip install playwright pandas openpyxl
    playwright install chromium
    python mims_brand_generic.py              # scrape + gabung ke Excel
    python mims_brand_generic.py --merge-only # hanya gabung CSV yang sudah ada ke Excel

Catatan: perhatikan Terms of Use MIMS sebelum mengambil data dalam jumlah besar,
dan beri jeda antar request supaya tidak membebani server mereka.
"""
import argparse
import asyncio
import gc
import random
import sys
import time
from pathlib import Path
from urllib.parse import parse_qs, urlencode, urlparse, urlunparse

import pandas as pd
from playwright.async_api import async_playwright

if sys.platform == "win32":
    asyncio.set_event_loop_policy(asyncio.WindowsProactorEventLoopPolicy())

# ================= CONFIG =================
MAX_PAGE_RETRY = 3
MAX_DETAIL_RETRY = 3
DELAY_BETWEEN_DETAILS = (1.0, 2.5)   # detik, jeda acak antar halaman detail
MTYPES = ["brand", "generic"]
OUTPUT_DIR = Path("output_mims")
EXCEL_CELL_LIMIT = 32767

USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/120.0.0.0 Safari/537.36"
)


def with_mtype(url, mtype):
    """Ganti parameter mtype di URL search (brand <-> generic)."""
    u = urlparse(url)
    q = {k: v[0] for k, v in parse_qs(u.query).items()}
    q["mtype"] = mtype
    return urlunparse(u._replace(query=urlencode(q)))


def csv_path(code, mtype):
    return OUTPUT_DIR / f"mims_{mtype}_{code}.csv"


# ================= SCRAPER ENGINE =================
async def scrape_subcategory(base_url, code, mtype):
    out_file = csv_path(code, mtype)
    OUTPUT_DIR.mkdir(exist_ok=True)

    # Resume: link yang sudah ada di CSV tidak diambil lagi
    all_data = pd.read_csv(out_file).to_dict("records") if out_file.exists() else []
    done = {r.get("Source URL") for r in all_data}
    if all_data:
        print(f"🔁 Resume {mtype} {code}: {len(all_data)} baris sudah ada")

    query = parse_qs(urlparse(base_url).query).get("q", [""])[0]

    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        try:
            context = await browser.new_context(
                user_agent=USER_AGENT, viewport={"width": 1366, "height": 768},
                locale="en-US", timezone_id="Asia/Jakarta",
            )
            page = await context.new_page()
            detail_page = await context.new_page()

            page_num = 1
            while True:
                url = base_url if page_num == 1 else f"{base_url}&page={page_num}"
                print(f"\n🌐 [{mtype} {code}] Page {page_num}: {url}")

                drug_links = []
                for _ in range(MAX_PAGE_RETRY):
                    try:
                        await page.goto(url, wait_until="domcontentloaded", timeout=60000)
                        await page.wait_for_selector("div.search-border-style", timeout=10000)
                        drug_links = await page.evaluate("""
                            () => Array.from(
                                document.querySelectorAll('div.search-border-style a[href*="/drug/info/"]')
                            ).map(a => a.href)
                        """)
                        drug_links = list(dict.fromkeys(drug_links))
                        if drug_links:
                            break
                    except Exception:
                        await asyncio.sleep(2)

                if not drug_links:
                    print(f"🛑 Tidak ada data lagi untuk {mtype} {code}.")
                    break

                for link in drug_links:
                    if link in done:
                        continue
                    for attempt in range(1, MAX_DETAIL_RETRY + 1):
                        try:
                            await detail_page.goto(link, wait_until="domcontentloaded", timeout=60000)
                            await detail_page.wait_for_function("""
                                () => {
                                    const h1 = document.querySelector('h1');
                                    if (!h1) return false;
                                    const t = h1.innerText.trim().toLowerCase();
                                    return t.length > 0 && t !== 'mims' && !t.includes('mims.com');
                                }
                            """, timeout=15000)

                            info = await detail_page.evaluate("""
                                () => {
                                    const data = {};
                                    const h1 = document.querySelector("h1");
                                    data["Name"] = h1 ? h1.innerText.trim() : null;
                                    data["Source URL"] = location.href;
                                    document.querySelectorAll(".monograph-section-header").forEach(sec => {
                                        const title = sec.innerText.trim();
                                        const content = sec.nextElementSibling?.innerText.trim();
                                        if (title && content) data[title] = content;
                                    });
                                    return data;
                                }
                            """)
                            if not (info and info.get("Name")):
                                raise ValueError("Nama tidak ditemukan")

                            info = {"Type": mtype, "Category Code": code, "Category Query": query, **info}
                            all_data.append(info)
                            done.add(link)
                            print(f"  ✅ {info['Name']}")
                            break
                        except Exception:
                            if attempt == MAX_DETAIL_RETRY:
                                print(f"  ❌ Dilewati: {link}")
                            await asyncio.sleep(random.uniform(1, 3))
                    await asyncio.sleep(random.uniform(*DELAY_BETWEEN_DETAILS))

                # simpan tiap halaman (aman kalau terputus)
                pd.DataFrame(all_data).to_csv(out_file, index=False, encoding="utf-8-sig")
                page_num += 1
        finally:
            await browser.close()

    print(f"🏁 Selesai {mtype} {code}: {len(all_data)} baris -> {out_file}")


# ================= GABUNG KE EXCEL =================
def merge_to_excel():
    for mtype in MTYPES:
        files = sorted(OUTPUT_DIR.glob(f"mims_{mtype}_*.csv"))
        if not files:
            print(f"⚠️ Tidak ada CSV {mtype}")
            continue
        df = pd.concat([pd.read_csv(f, dtype=str) for f in files], ignore_index=True)

        # Obat yang sama bisa muncul di beberapa kategori -> satu baris, kategorinya digabung
        cats = (df.groupby("Source URL")["Category Code"]
                  .apply(lambda s: "; ".join(dict.fromkeys(s.dropna()))))
        df = df.drop_duplicates("Source URL").copy()
        df["Category Code"] = df["Source URL"].map(cats)

        # Kolom identitas di depan
        front = ["Type", "Name", "Category Code", "Category Query", "Source URL"]
        df = df[[c for c in front if c in df] + [c for c in df.columns if c not in front]]

        df.to_csv(OUTPUT_DIR / f"mims_{mtype}.csv", index=False, encoding="utf-8-sig")
        xl = df.apply(lambda col: col.map(
            lambda x: x[:EXCEL_CELL_LIMIT] if isinstance(x, str) else x))
        xl.to_excel(OUTPUT_DIR / f"mims_{mtype}.xlsx", index=False)
        print(f"📗 {mtype}: {len(df)} baris, {len(df.columns)} kolom -> {OUTPUT_DIR / f'mims_{mtype}.xlsx'}")


# ================= SUBCLASS LIST =================
# Isi dengan daftar subkelas kamu (URL boleh mtype=brand; versi generic dibuat otomatis).
SUBCLASS_LINKS = [
    # 31. Health Supplements & Food
    {"code": "31a", "url": "https://www.mims.com/indonesia/drug/search?q=appetite+enhancers&mtype=brand&code=31a"},
    {"code": "31b", "url": "https://www.mims.com/indonesia/drug/search?q=supplements+%26+adjuvant+therapy&mtype=brand&code=31b"},
    {"code": "31c", "url": "https://www.mims.com/indonesia/drug/search?q=other+complementary+health+products&mtype=brand&code=31c"},
    # 40. Dermatological & Personal Care
    {"code": "40a", "url": "https://www.mims.com/indonesia/drug/search?q=emollients%2c+cleansers+%26+skin+protectives&mtype=brand&code=40a"},
    {"code": "40b", "url": "https://www.mims.com/indonesia/drug/search?q=oral+care&mtype=brand&code=40b"},
    {"code": "40c", "url": "https://www.mims.com/indonesia/drug/search?q=personal+care&mtype=brand&code=40c"},
]


# ================= MAIN =================
if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--merge-only", action="store_true", help="Hanya gabung CSV yang ada ke Excel")
    ap.add_argument("--mtype", choices=MTYPES, nargs="+", default=MTYPES)
    args = ap.parse_args()

    if not args.merge_only:
        for item in SUBCLASS_LINKS:
            for mtype in args.mtype:
                print(f"\n{'=' * 60}\n🚀 {mtype.upper()} - {item['code']}\n{'=' * 60}")
                try:
                    asyncio.run(scrape_subcategory(with_mtype(item["url"], mtype), item["code"], mtype))
                except Exception as e:
                    print(f"🚨 Error kategori {item['code']} ({mtype}): {e}")
                gc.collect()
                time.sleep(3)

    merge_to_excel()
