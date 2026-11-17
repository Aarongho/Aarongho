#!/usr/bin/env python3
"""
Scraper KFA Browser (Kamus Farmasi) - SATUSEHAT Kemenkes
https://satusehat.kemkes.go.id/kfa-browser/farmasi/

Mengambil:
  1. Tabel "Daftar Produk Varian" (Kode KFA, Nama Produk, Merk Dagang, Unit Logistik
     Terkecil, Bentuk Sediaan, Golongan Obat, Nomor Izin Edar, Fornas)
  2. Detail tiap produk (/product-variant/<kode>) tab "Informasi Umum", semua section:
     Informasi Umum, ATC Kelas Terapi, Informasi Dagang, Bahan Zat Aktif & Kekuatan,
     Produk Hierarki -> ditambahkan sebagai kolom baru (yang belum ada di tabel list).

Data diambil dari API JSON yang dipakai website itu sendiri (bukan parsing HTML).

Contoh:
  python scrape_kfa.py --limit 10                 # coba 10 data dulu
  python scrape_kfa.py --search amoxicillin       # filter pencarian
  python scrape_kfa.py                            # semua data (~22rb produk)
"""
import argparse
import json
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
        "Golongan Obat": (r.get("farmalkesType") or {}).get("name"),
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

    # --- Section: Informasi Umum
    out["Tipe"] = (d.get("farmalkesType") or {}).get("name")
    out["Unit of Measure (UCUM)"] = d.get("ucumSymbol")
    # Di list "Golongan Obat" = jenis farmalkes (Obat/Vaksin/...),
    # di detail "Golongan Obat" = Obat Keras / Obat Bebas / dst.
    out["Golongan Obat (Detail)"] = d.get("controlledDrugName")
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

    return out


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
                cache[j["kfaCode"]] = j
    todo = [r["Kode KFA"] for r in rows if r["Kode KFA"] not in cache]
    print(f"Detail: {len(cache)} dari cache, {len(todo)} perlu diambil")

    with open(cache_file, "a", encoding="utf-8") as f, ThreadPoolExecutor(args.workers) as ex:
        for n, (code, d) in enumerate(zip(todo, ex.map(fetch_detail, todo)), 1):
            d["kfaCode"] = code
            cache[code] = d
            f.write(json.dumps(d, ensure_ascii=False) + "\n")
            if n % 50 == 0 or n == len(todo):
                print(f"  detail {n}/{len(todo)}")

    # 3. Gabungkan & simpan
    full = [{**r, **parse_detail(cache[r["Kode KFA"]])} for r in rows]
    df = pd.DataFrame(full)
    df.to_csv(f"{args.out}.csv", index=False, encoding="utf-8-sig")
    df.to_excel(f"{args.out}.xlsx", index=False)
    print(f"Selesai: {len(df)} baris, {len(df.columns)} kolom -> {args.out}.csv / {args.out}.xlsx")


if __name__ == "__main__":
    main()
