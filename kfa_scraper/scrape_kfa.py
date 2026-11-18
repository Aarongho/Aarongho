#!/usr/bin/env python3
"""
Scraper KFA Browser (Kamus Farmasi) - SATUSEHAT Kemenkes
https://satusehat.kemkes.go.id/kfa-browser/farmasi/

Mengambil:
  1. Tabel "Daftar Produk Varian" (Kode KFA, Nama Produk, Merk Dagang, Unit Logistik
     Terkecil, Bentuk Sediaan, Golongan Obat, Nomor Izin Edar, Fornas)
  2. Detail tiap produk (/product-variant/<kode>), semua tab, sebagai kolom tambahan:
     - Informasi Umum (Informasi Umum, ATC, Informasi Dagang, Zat Aktif, Hierarki)
     - Produk Aktual Info (Deskripsi, Penggunaan, Peringatan, Efek Samping)
     - Referensi Identifier (nama identifier produk aktual & virtual)
     - Program & Kemandirian (LKPP, KBKI, TKDN, negara registrar/manufacturer, ...)
     - Inventory (Packaging, Harga Kemasan, Contained Quantity Type; dipisah "; ")
     - Formula Nasional (Kelas Terapi, Sub Kelas Terapi, Tingkat Faskes; start date terbaru)

Data diambil dari API JSON yang dipakai website itu sendiri (bukan parsing HTML).

Contoh:
  python scrape_kfa.py --limit 10                 # coba 10 data dulu
  python scrape_kfa.py --search amoxicillin       # filter pencarian
  python scrape_kfa.py                            # semua data (~22rb produk)
"""
import argparse
import html
import json
import re
import os
import time
from concurrent.futures import ThreadPoolExecutor

import pandas as pd
import requests

BASE = "https://satusehat.kemkes.go.id/kfa-browser/farmasi/api"
HEADERS = {
    "Content-Type": "application/json",
    "Accept": "application/json",
    "User-Agent": "Mozilla/5.0 (KFA scraper)",
}

session = requests.Session()
session.headers.update(HEADERS)


def post(path, payload, retries=5):
    for attempt in range(retries):
        try:
            r = session.post(f"{BASE}/{path}", json=payload, timeout=30)
            if r.status_code == 200:
                return r.json()
            if r.status_code == 404:  # produk ada di list tapi detailnya tidak ditemukan
                print(f"  404 {path} {payload} -> dilewati")
                return {}
            print(f"  HTTP {r.status_code} {path} {payload} (percobaan {attempt + 1})")
        except requests.RequestException as e:
            print(f"  Error {path} {payload}: {e} (percobaan {attempt + 1})")
        time.sleep(2 ** attempt)
    raise RuntimeError(f"Gagal ambil {path} {payload}")


# ---------------------------------------------------------------- list page
def fetch_list_page(page, size, search="", farmalkes_type=""):
    payload = {"search": search, "page": page, "size": size,
               "farmalkes_type": farmalkes_type, "sorts": {}}
    if search:  # tanpa search_by, kata kunci diabaikan oleh API
        payload["search_by"] = "kfa_code" if search.isdigit() else "name"
    return post("search/product-variants", payload)


def parse_list_row(r):
    return {
        "Kode KFA": r.get("kfaCode"),
        "Nama Produk": r.get("name"),
        "Merk Dagang": r.get("tradeName"),
        "Unit Logistik Terkecil": r.get("uomName"),
        "Bentuk Sediaan": r.get("dosageFormName"),
        "Tipe": (r.get("farmalkesType") or {}).get("name"),
        "Golongan Obat": None,  # diisi dari detail (Obat Keras / Obat Bebas / ...)
        "Nomor Izin Edar": r.get("nie"),
        "Fornas": "Ya" if r.get("isFornas") else "Tidak",
    }


# -------------------------------------------------------------- detail page
ATC_LEVELS = {
    "1": "Kelompok Utama Anatomi",
    "2": "Subkelompok Terapeutik",
    "3": "Subkelompok Farmakologi",
    "4": "Subgrup Kimia",
    "5": "Substansi Kimia (ATC)",
}


def fetch_detail(kfa_code):
    return post("detail/product-variants", {"kfa_code": kfa_code}).get("data") or {}


def parse_detail(d):
    """Kolom dari tab 'Informasi Umum' yang belum ada di tabel list."""
    out = {}
    tmpl = d.get("template") or {}

    # ===================== TAB: Informasi Umum =====================
    # --- Section: Informasi Umum
    out["Tipe"] = (d.get("farmalkesType") or {}).get("name")
    out["Golongan Obat"] = d.get("controlledDrugName")
    out["Unit of Measure (UCUM)"] = d.get("ucumSymbol")
    out["Cara Pemakaian Obat"] = d.get("routeAdministrationName")

    # --- Section: ATC Kelas Terapi (bisa lebih dari satu ATC -> digabung "; ")
    atc = {v: [] for v in ATC_LEVELS.values()}
    for a in tmpl.get("atcs") or []:
        col = ATC_LEVELS.get(str(a.get("level")))
        if col:
            atc[col].append(f"{a.get('code')} - {a.get('name')}")
    for col in ["Substansi Kimia (ATC)", "Kelompok Utama Anatomi", "Subkelompok Terapeutik",
                "Subkelompok Farmakologi", "Subgrup Kimia"]:
        out[col] = "; ".join(atc[col]) or None
    out["Referensi Zat Aktif"] = tmpl.get("rxtermName")

    # --- Section: Informasi Dagang (Nama Dagang & NIE sudah ada di list)
    out["Discontinued"] = "Ya" if d.get("isDiscontinued") else "-"
    out["Registrar"] = d.get("registrarName")
    out["Manufacturer"] = d.get("manufacturerName")

    # --- Section: Bahan Zat Aktif & Kekuatan
    ing = d.get("ingredients") or []
    out["Zat Aktif"] = "; ".join(i.get("name") or "" for i in ing) or None
    out["Kekuatan Zat Aktif"] = "; ".join(i.get("strength") or "" for i in ing) or None
    out["Zat Aktif & Kekuatan"] = "; ".join(
        f"{i.get('name')} {i.get('strength')}" for i in ing) or None

    # --- Section: Produk Hierarki
    for h in sorted(d.get("hierarchies") or [], key=lambda x: x.get("order", 0)):
        t = h.get("type")
        val = f"{h.get('kfaCode')} - {h.get('name')}"
        out[f"Hierarki {t}"] = f"{out[f'Hierarki {t}']}; {val}" if out.get(f"Hierarki {t}") else val

    # ===================== TAB: Produk Aktual Info =====================
    out["Deskripsi"] = html_to_text(d.get("description"))
    out["Penggunaan"] = html_to_text(d.get("indication"))
    out["Peringatan"] = html_to_text(d.get("warning"))
    out["Efek Samping"] = html_to_text(d.get("sideEffect"))

    # ===================== TAB: Referensi Identifier (nama saja) =====================
    out["Referensi Identifier Produk Aktual"] = join_unique(i.get("name") for i in d.get("identifiers") or [])
    out["Referensi Identifier Produk Virtual"] = join_unique(i.get("name") for i in d.get("templateIdentifiers") or [])

    # ===================== TAB: Program & Kemandirian =====================
    out["Tayang LKPP"] = "Ya" if d.get("isTayangLkpp") else "-"
    out["Kode LKPP"] = d.get("lkppCode") or None
    out["Kode KBKI"] = d.get("kbkiCode") or None
    out["Dapat Dibeli (LKPP)"] = "Ya" if d.get("isDapatDibeliLkpp") else "-"
    out["Izin Edar"] = d.get("ijinEdar") or "-"
    out["Produksi Buatan"] = d.get("produksiBuatan") or None
    out["Skor TKDN"] = d.get("scoreTkdn")
    out["Skor BMP"] = d.get("scoreBmp")
    out["Skor TKDN BMP"] = d.get("scoreTkdnBmp")
    out["Negara Registrar"] = d.get("registrarCountryName") or None
    out["Negara Manufacturer"] = d.get("manufacturerCountryName") or None

    # ===================== TAB: Inventory (Kemasan) =====================
    pk = d.get("_packagings") or []
    out["Packaging"] = "; ".join(p.get("packageName") or "" for p in pk) or None
    out["Harga Kemasan"] = "; ".join(fmt_num(p.get("price")) for p in pk) or None
    out["Contained Quantity Type"] = "; ".join(fmt_num(p.get("qty")) for p in pk) or None

    # ===================== TAB: Formula Nasional (start date terbaru) =====================
    out.update(parse_fornas(tmpl.get("fornases")))

    return out


def parse_fornas(fornases):
    """Kolom Formula Nasional, diambil dari baris dengan start date terbaru."""
    cols = ["Formula Nasional (Nama Produk)", "Kelas Terapi", "Sub Kelas Terapi",
            "Tingkat Faskes", "Fornas Start Date"]
    fornas = [f for f in fornases or [] if f.get("startDate")]
    if not fornas:
        return dict.fromkeys(cols)
    latest = max(f["startDate"] for f in fornas)
    rows = [f for f in fornas if f["startDate"] == latest]

    def fkt(level):
        return join_unique(f"{x.get('code')} - {x.get('name')}" for f in rows
                           for x in f.get("fkts") or [] if str(x.get("level")) == level)
    return {
        "Formula Nasional (Nama Produk)": join_unique(f.get("name") for f in rows),
        "Kelas Terapi": fkt("1"),
        "Sub Kelas Terapi": fkt("2"),
        "Tingkat Faskes": join_unique(f.get("tingkatFaskesName") for f in rows),
        "Fornas Start Date": latest[:10],
    }


def html_to_text(h):
    if not h:
        return None
    t = re.sub(r"<br\s*/?>|</p>|</li>|</div>", "\n", h, flags=re.I)
    t = html.unescape(re.sub(r"<[^>]+>", "", t)).replace("\xa0", " ")
    t = re.sub(r"[ \t]+\n", "\n", t)
    return re.sub(r"\n{3,}", "\n\n", t).strip() or None


def join_unique(items):
    seen = []
    for x in items:
        x = re.sub(r"\s+", " ", x or "").strip()
        if x and x not in seen:
            seen.append(x)
    return "; ".join(seen) or None


def fmt_num(v):
    if v is None:
        return ""
    return str(int(v)) if float(v).is_integer() else str(v)


def fetch_packagings(kfa_code):
    out, page = [], 1
    while True:
        res = post("search/product-packagings", {
            "search": kfa_code, "search_by": "variant_kfa_code", "page": page,
            "size": 100, "farmalkes_type": "", "sorts": {}})
        out += res.get("data") or []
        if page >= ((res.get("meta") or {}).get("totalPage") or 0):
            return out
        page += 1


def fetch_all(kfa_code):
    try:
        d = fetch_detail(kfa_code)
        if not d:
            d = {"_status": "detail tidak ditemukan (404)"}
        d["_packagings"] = fetch_packagings(kfa_code)
        return d
    except Exception as e:  # jangan hentikan seluruh proses; tidak disimpan ke cache
        print(f"  GAGAL {kfa_code}: {e}")
        return None


# --------------------------------------------------------------------- main
def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--limit", type=int, default=0, help="Jumlah produk maksimum (0 = semua)")
    ap.add_argument("--search", default="", help="Kata kunci pencarian")
    ap.add_argument("--type", default="", help="farmalkes_type, mis. medicine/vaccine (kosong = semua)")
    ap.add_argument("--page-size", type=int, default=100)
    ap.add_argument("--workers", type=int, default=5, help="Jumlah request detail paralel")
    ap.add_argument("--out", default="kfa_produk_varian")
    args = ap.parse_args()

    # 1. Ambil semua baris tabel list
    rows, page = [], 1
    size = min(args.page_size, args.limit) if args.limit else args.page_size
    while True:
        res = fetch_list_page(page, size, args.search, args.type)
        data, meta = res.get("data") or [], res.get("meta") or {}
        rows += [parse_list_row(r) for r in data]
        print(f"List halaman {page}/{meta.get('totalPage')} -> {len(rows)}/{meta.get('totalData')} baris")
        if not data or page >= (meta.get("totalPage") or 0) or (args.limit and len(rows) >= args.limit):
            break
        page += 1
    if args.limit:
        rows = rows[: args.limit]

    # 2. Ambil detail tiap produk (dengan cache supaya bisa dilanjutkan kalau terputus)
    cache_file = f"{args.out}_detail_cache.jsonl"
    cache = {}
    if os.path.exists(cache_file):
        with open(cache_file, encoding="utf-8") as f:
            for line in f:
                j = json.loads(line)
                if "_packagings" in j:  # cache versi lama belum punya data kemasan
                    cache[j["kfaCode"]] = j
    todo = [r["Kode KFA"] for r in rows if r["Kode KFA"] not in cache]
    print(f"Detail: {len(cache)} dari cache, {len(todo)} perlu diambil")

    failed = []
    with open(cache_file, "a", encoding="utf-8") as f, ThreadPoolExecutor(args.workers) as ex:
        for n, (code, d) in enumerate(zip(todo, ex.map(fetch_all, todo)), 1):
            if d is None:
                failed.append(code)
                continue
            d["kfaCode"] = code
            cache[code] = d
            f.write(json.dumps(d, ensure_ascii=False) + "\n")
            if n % 50 == 0 or n == len(todo):
                print(f"  detail {n}/{len(todo)}")

    if failed:
        print(f"PERHATIAN: {len(failed)} produk gagal diambil, jalankan ulang untuk mencoba lagi: {failed[:20]}")

    # 3. Gabungkan & simpan
    full = []
    for r in rows:
        d = cache.get(r["Kode KFA"])
        row = {**r, **parse_detail(d)} if d and "_status" not in d else dict(r)
        row["Status Scrape"] = (d or {}).get("_status", "ok") if d else "gagal"
        full.append(row)
    df = pd.DataFrame(full)
    df.to_csv(f"{args.out}.csv", index=False, encoding="utf-8-sig")
    df.to_excel(f"{args.out}.xlsx", index=False)
    print(f"Selesai: {len(df)} baris, {len(df.columns)} kolom -> {args.out}.csv / {args.out}.xlsx")


if __name__ == "__main__":
    main()
