#!/usr/bin/env python3
"""
Scrape SEMUA tab KFA Browser (https://satusehat.kemkes.go.id/kfa-browser/farmasi/)
dengan SEMUA section & kolom di halaman detail.

  varian    -> Produk Varian   (/product-variant/<kode>)
  template  -> Produk Template (/product-templates/<kode>)
  kemasan   -> Produk Kemasan  (/packaging-products/<kode>)
  zat_aktif -> Zat Aktif       (/active-substance/<kode>)

Nama kolom: "Section (Kolom)", contoh "Formula Nasional (Referensi Dokumen)".
- Section berupa tabel (mis. Formula Nasional, Inventory, Referensi Identifier):
  semua baris digabung dengan "; " dan urutannya sejajar antar kolom
  (nilai ke-1 di kolom Nama = pasangan nilai ke-1 di kolom Kode, dst).
  Sel kosong di dalam tabel ditulis "-" supaya urutannya tetap sejajar.
- Produk yang tidak punya section tertentu -> kolomnya kosong.
- Produk yang halaman detailnya 404 di website tidak dimasukkan.

Hasil detail di-cache (output/*_detail_cache.jsonl). Kalau terputus, jalankan ulang
dan proses dilanjutkan dari cache.

Contoh:
  python scrape_kfa_all.py --limit 10                  # coba 10 data per tab
  python scrape_kfa_all.py --tabs template kemasan     # tab tertentu saja
  python scrape_kfa_all.py                             # semua tab, semua data
"""
import argparse
import json
import os
import re
from concurrent.futures import ThreadPoolExecutor

import pandas as pd

from scrape_kfa import fetch_all as fetch_variant_detail, fmt_num, html_to_text, post

SEP = "; "


# =================================================================== helpers
def search_all(endpoint, search="", search_by=None, limit=0, log=False, workers=1):
    """Ambil semua halaman dari endpoint search/<endpoint> (maks 100 per halaman)."""
    def page(p):
        payload = {"search": search, "page": p, "size": 100, "farmalkes_type": "", "sorts": {}}
        if search_by:
            payload["search_by"] = search_by
        return post(f"search/{endpoint}", payload)

    first = page(1)
    out = first.get("data") or []
    total_pages = (first.get("meta") or {}).get("totalPage") or 0
    if limit:
        total_pages = min(total_pages, -(-limit // 100))
    rest = range(2, total_pages + 1)
    with ThreadPoolExecutor(workers) as ex:
        for n, res in enumerate(ex.map(page, rest), 2):
            out += res.get("data") or []
            if log and (n % 20 == 0 or n == total_pages):
                print(f"  daftar {endpoint}: halaman {n}/{total_pages}", flush=True)
    return out[:limit] if limit else out


def v(x):
    """Nilai tunggal: '' / None -> None."""
    if x is None or x == "" or x == [] or x == {}:
        return None
    return x


def yn(x):
    return "Ya" if x else "-"


def date(x):
    return (x or "")[:10] or None


def name_of(o):
    return (o or {}).get("name") or None


def table(section, rows, cols):
    """
    Section berbentuk tabel -> satu kolom per field, baris digabung "; ".
    cols: list of (nama_kolom, fungsi(row) -> nilai)
    """
    out = {}
    for col, get in cols:
        key = f"{section} ({col})"
        if not rows:
            out[key] = None
            continue
        vals = []
        for r in rows:
            val = get(r)
            val = " ".join(str(val).split()) if val is not None else ""  # rapikan tab/enter
            vals.append(val or "-")
        out[key] = SEP.join(vals)
    return out


def single(section, pairs):
    return {f"{section} ({k})": v(val) for k, val in pairs}


ATC_COLS = [("Substansi Kimia (ATC)", "5"), ("Kelompok Utama Anatomi", "1"),
            ("Subkelompok Terapeutik", "2"), ("Subkelompok Farmakologi", "3"),
            ("Subgrup Kimia", "4")]


def atc_section(atcs, rxterm):
    out = {}
    for col, lvl in ATC_COLS:
        vals = [f"{a.get('code')} - {a.get('name')}" for a in atcs or [] if str(a.get("level")) == lvl]
        out[f"ATC Kelas Terapi ({col})"] = SEP.join(vals) or None
    out["ATC Kelas Terapi (Referensi Zat Aktif)"] = v(rxterm)
    return out


def ingredient_section(ing):
    return table("Bahan Zat Aktif & Kekuatan", ing, [
        ("Kode KFA Zat Aktif", lambda i: i.get("kfaCode")),
        ("Zat Aktif", lambda i: i.get("name")),
        ("Kekuatan Zat Aktif", lambda i: i.get("strength")),
    ])


def identifier_section(section, ids, with_price=False):
    cols = [("Nama", lambda i: i.get("name")),
            ("Kode", lambda i: i.get("code"))]
    if with_price:
        cols.append(("Harga", lambda i: fmt_num(i.get("price"))))
    cols += [("Sumber", lambda i: i.get("sourceName")),
             ("URL", lambda i: i.get("url")),
             ("Use", lambda i: i.get("use")),
             ("Start Date", lambda i: date(i.get("startDate"))),
             ("End Date", lambda i: date(i.get("endDate")))]
    return table(section, ids, cols)


def fkt(f, level):
    vals = [f"{x.get('code')} - {x.get('name')}" for x in f.get("fkts") or [] if str(x.get("level")) == level]
    return ", ".join(vals) or None


def fornas_section(fornases, start="Start Date", end="End Date"):
    rows = sorted(fornases or [], key=lambda f: f.get("startDate") or "", reverse=True)  # terbaru dulu
    return table("Formula Nasional", rows, [
        ("Nama Produk", lambda f: f.get("name")),
        ("Kelas Terapi", lambda f: fkt(f, "1")),
        ("Sub Kelas Terapi", lambda f: fkt(f, "2")),
        ("Referensi Dokumen", lambda f: f.get("documentName")),
        (start, lambda f: date(f.get("startDate"))),
        (end, lambda f: date(f.get("endDate"))),
        ("Kedaluwarsa", lambda f: "Ya" if f.get("isExpired") else None),
        ("Tingkat Faskes", lambda f: f.get("tingkatFaskesName")),
    ])


def hierarchy_section(d, types):
    out = {}
    for t in types:
        hs = [h for h in d.get("hierarchies") or [] if h.get("type") == t and h.get("kfaCode")]
        out[f"Produk Hierarki ({t})"] = SEP.join(f"{h['kfaCode']} - {h.get('name')}" for h in hs) or None
    return out


def text_section(section, d):
    return {
        f"{section} (Deskripsi)": html_to_text(d.get("description")),
        f"{section} (Penggunaan)": html_to_text(d.get("indication")),
        f"{section} (Peringatan)": html_to_text(d.get("warning")),
        f"{section} (Efek Samping)": html_to_text(d.get("sideEffect")),
    }


def detail(endpoint, code):
    return post(f"detail/{endpoint}", {"kfa_code": code}).get("data") or {}


# ============================================================= Produk Varian
def variant_list(r):
    return single("Daftar Produk", [
        ("Kode KFA", r.get("kfaCode")),
        ("Nama Produk", r.get("name")),
        ("Merk Dagang", r.get("tradeName")),
        ("Unit Logistik Terkecil", r.get("uomName")),
        ("Bentuk Sediaan", r.get("dosageFormName")),
        ("Golongan Obat", name_of(r.get("farmalkesType"))),
        ("Nomor Izin Edar", r.get("nie")),
        ("Fornas", "Ya" if r.get("isFornas") else "Tidak"),
    ])


def variant_parse(d):
    tmpl = d.get("template") or {}
    out = {}
    # --- bagian atas halaman
    out.update(single("Ringkasan", [
        ("Nama Produk", d.get("name")),
        ("Kode KFA", d.get("kfaCode")),
        ("Tipe", name_of(d.get("farmalkesType"))),
        ("Unit of Measure", d.get("ucumSymbol")),
        ("Nomor Izin Edar BPOM", d.get("nie")),
        ("HET", fmt_num(d.get("hetPrice")) if d.get("hetPrice") is not None else None),
        ("Registrar", d.get("registrarName")),
        ("Manufaktur", d.get("manufacturerName")),
    ]))
    # --- tab Informasi Umum
    out.update(single("Informasi Umum", [
        ("Kode KFA", d.get("kfaCode")),
        ("Tipe", name_of(d.get("farmalkesType"))),
        ("Unit of Measure (UCUM)", d.get("ucumSymbol")),
        ("Bentuk Sediaan", d.get("dosageFormName")),
        ("Golongan Obat", d.get("controlledDrugName")),
        ("Cara Pemakaian Obat", d.get("routeAdministrationName")),
    ]))
    out.update(atc_section(tmpl.get("atcs"), tmpl.get("rxtermName")))
    out.update(single("Informasi Dagang", [
        ("Discontinued", yn(d.get("isDiscontinued"))),
        ("Nomor Izin Edar BPOM", d.get("nie")),
        ("Nama Dagang", d.get("tradeName")),
        ("Registrar", d.get("registrarName")),
        ("Manufacturer", d.get("manufacturerName")),
    ]))
    out.update(ingredient_section(d.get("ingredients")))
    out.update(table("Eksipien", d.get("excipients"), [
        ("Zat Eksipien", lambda e: e.get("name")),
        ("Kekuatan Eksipien", lambda e: e.get("strength")),
    ]))
    cvx, mvx = d.get("cvx") or {}, d.get("cvxMvx") or {}
    out.update(single("Info CVX", [
        ("Kode CVX", cvx.get("code")),
        ("Kelompok Vaksin", cvx.get("groupName")),
        ("Kode CVX MVX", mvx.get("code")),
        ("CVX Trade Name", mvx.get("name")),
    ]))
    out.update(hierarchy_section(d, ["POV", "POA"]))
    # --- tab Produk Aktual Info
    out.update(text_section("Produk Aktual Info", d))
    # --- tab Referensi Identifier
    out.update(identifier_section("Referensi Identifier Produk Aktual", d.get("identifiers")))
    out.update(identifier_section("Referensi Identifier Produk Virtual", d.get("templateIdentifiers")))
    # --- tab Program & Kemandirian
    out.update(single("Program & Kemandirian", [
        ("Tayang LKPP", yn(d.get("isTayangLkpp"))),
        ("Kode LKPP", d.get("lkppCode")),
        ("Nomor Izin Edar BPOM", d.get("nie")),
        ("Kode KBKI", d.get("kbkiCode")),
        ("Dapat Dibeli (LKPP)", yn(d.get("isDapatDibeliLkpp"))),
        ("Izin Edar", d.get("ijinEdar")),
        ("Produksi Buatan", d.get("produksiBuatan")),
        ("Skor TKDN", d.get("scoreTkdn")),
        ("Skor BMP", d.get("scoreBmp")),
        ("Skor TKDN BMP", d.get("scoreTkdnBmp")),
    ]))
    out.update(single("Registrar/Pabrik", [
        ("Registrar", d.get("registrarName")),
        ("Negara Registrar", d.get("registrarCountryName")),
        ("Manufacturer", d.get("manufacturerName")),
        ("Negara Manufacturer", d.get("manufacturerCountryName")),
    ]))
    # --- tab Inventory
    out.update(table("Inventory", d.get("_packagings"), [
        ("Kode KFA", lambda p: p.get("kfaCode")),
        ("Nama Produk", lambda p: p.get("variantDisplayName")),
        ("Packaging", lambda p: p.get("packageName")),
        ("Harga Kemasan", lambda p: fmt_num(p.get("price"))),
        ("Contained Quantity Type", lambda p: fmt_num(p.get("qty"))),
        ("Unit of Measure", lambda p: p.get("uomName")),
    ]))
    # --- tab Formula Nasional
    out.update(fornas_section(tmpl.get("fornases")))
    # --- tab Isi Paket (hanya Paket Obat)
    out.update(table("Isi Paket", d.get("packets"), [
        ("Nama Produk", lambda p: p.get("name")),
        ("Quantity", lambda p: fmt_num(p.get("qty"))),
        ("Satuan", lambda p: p.get("uomName")),
        ("Unit of Measure (UCUM)", lambda p: p.get("ucumSymbol")),
        ("Paket", lambda p: p.get("parentName")),
    ]))
    return out


# =========================================================== Produk Template
def template_list(r):
    return single("Daftar Produk", [
        ("Kode KFA", r.get("kfaCode")),
        ("Nama Produk", r.get("name")),
        ("Unit Logistik Terkecil", r.get("uomName")),
        ("Jenis Farmalkes", name_of(r.get("farmalkesType"))),
        ("Jumlah Produk Varian", r.get("totalVariants")),
        ("Fornas", "Ya" if r.get("isFornas") else "Tidak"),
    ])


def template_fetch(code):
    d = detail("product-templates", code)
    if d:
        d["_variants"] = search_all("product-variants", code, "template_kfa_code")
    return d


def template_parse(d):
    out = {}
    ing = d.get("ingredients") or []
    out.update(single("Ringkasan", [
        ("Nama Produk", d.get("name")),
        ("Kode KFA", d.get("kfaCode")),
        ("Tipe", name_of(d.get("farmalkesType"))),
        ("Unit of Measure", d.get("ucumSymbol")),
        ("Bentuk Sediaan", d.get("dosageFormName")),
        ("Golongan Obat", d.get("controlledDrugName")),
        ("Zat Aktif", SEP.join(i.get("name") or "-" for i in ing)),
    ]))
    out.update(single("Informasi Umum", [
        ("Kode KFA", d.get("kfaCode")),
        ("Tipe", name_of(d.get("farmalkesType"))),
        ("Unit of Measure (UCUM)", d.get("ucumSymbol")),
        ("Bentuk Sediaan", d.get("dosageFormName")),
        ("Golongan Obat", d.get("controlledDrugName")),
        ("Cara Pemakaian Obat", d.get("routeAdministrationName")),
    ]))
    out.update(atc_section(d.get("atcs"), d.get("rxtermName")))
    out.update(single("Informasi Dagang", [
        ("Unit Logistik Terkecil", d.get("uomName")),
        ("HS Code", d.get("hsCode")),
    ]))
    out.update(ingredient_section(ing))
    cvx = d.get("cvx") or {}
    out.update(single("Info CVX", [("Kode CVX", cvx.get("code")), ("Kelompok Vaksin", cvx.get("groupName"))]))
    out.update(hierarchy_section(d, ["POV"]))
    # --- tab Produk Virtual info
    out.update(text_section("Produk Virtual Info", d))
    # --- tab Referensi Identifier
    out.update(identifier_section("Referensi Identifier Produk Virtual", d.get("identifiers")))
    # --- tab Varian
    out.update(table("Produk Varian", d.get("_variants"), [
        ("Kode KFA", lambda x: x.get("kfaCode")),
        ("Nama Produk", lambda x: x.get("name")),
        ("Nomor Izin Edar BPOM", lambda x: x.get("nie")),
        ("Merek Dagang", lambda x: x.get("tradeName")),
        ("Registrar", lambda x: x.get("registrarName")),
        ("Manufaktur", lambda x: x.get("manufacturerName")),
    ]))
    # --- tab Formula Nasional
    out.update(fornas_section(d.get("fornases"), "Mulai Berlaku", "Akhir Berlaku"))
    return out


# ============================================================ Produk Kemasan
def packaging_list(r):
    return single("Daftar Produk", [
        ("Kode KFA", r.get("kfaCode")),
        ("Nama Produk", r.get("variantDisplayName")),
        ("Packaging", r.get("packageName")),
        ("Harga Kemasan", fmt_num(r.get("price")) if r.get("price") is not None else None),
        ("Contained Quantity", fmt_num(r.get("qty"))),
        ("Unit of Measure", r.get("uomName")),
        ("Jenis Farmalkes", name_of(r.get("farmalkesType"))),
    ])


def packaging_parse(d):
    out = {}
    isi = f"{fmt_num(d.get('qty'))} {d.get('uomName') or ''}".strip()
    price = fmt_num(d.get("price")) if d.get("price") is not None else None
    out.update(single("Ringkasan", [
        ("Nama Produk", d.get("variantDisplayName")),
        ("Kode KFA", d.get("kfaCode")),
        ("Aktif", "Ya" if d.get("isActive") else "Tidak"),
        ("Isi (Jumlah)", isi),
        ("Harga Kemasan", price),
        ("Golongan Obat", name_of(d.get("farmalkesType"))),
        ("Kode LKPP", d.get("lkppCode")),
    ]))
    out.update(single("Info Produk Kemasan", [
        ("Produk", d.get("variantDisplayName")),
        ("Aktif", "Ya" if d.get("isActive") else "Tidak"),
        ("Isi (Jumlah)", isi),
        ("Harga Kemasan", price),
        ("Golongan Obat", name_of(d.get("farmalkesType"))),
        ("Kode LKPP", d.get("lkppCode")),
        ("Discontinued", yn(d.get("isDiscontinued"))),
    ]))
    out.update(hierarchy_section(d, ["POV", "POA", "POAK"]))
    out.update(identifier_section("Referensi Identifier Produk Aktual Kemasan", d.get("identifiers"),
                                  with_price=True))
    return out


# ================================================================= Zat Aktif
def ingredient_list(r):
    return single("Daftar Produk", [
        ("Kode KFA", r.get("kfaCode")),
        ("Nama", r.get("name")),
        ("Unit of Measure", r.get("ucumSymbol")),
    ])


def ingredient_fetch(code):
    d = detail("active-ingredients", code)
    if d:
        d["_templates"] = search_all("product-templates", code, "ingredient_kfa_code")
    return d


def ingredient_parse(d):
    out = {}
    out.update(single("Ringkasan", [
        ("Nama", d.get("name")),
        ("Kode KFA", d.get("kfaCode")),
        ("Tipe", name_of(d.get("farmalkesType"))),
        ("Unit of Measure", d.get("ucumSymbol")),
        ("BMHP", yn(d.get("isBmhp"))),
        ("Generik", yn(d.get("isGeneric"))),
    ]))
    out.update(single("Informasi Umum", [
        ("Kode KFA", d.get("kfaCode")),
        ("Generik", yn(d.get("isGeneric"))),
        ("Tipe", name_of(d.get("farmalkesType"))),
        ("Unit of Measure (UCUM)", d.get("ucumSymbol")),
    ]))
    weight = d.get("weight")
    out.update(single("Informasi Dagang", [
        ("Discontinued", yn(d.get("isDiscontinued"))),
        ("Nama Dagang", d.get("tradeName")),
        ("Unit Logistik Terkecil", d.get("uomName")),
        ("Berat Unit Logistik", f"{weight} {d.get('weightUomName') or ''}".strip() if v(weight) else None),
        ("Harga Eceran Tertinggi", d.get("hetPrice")),
        ("Kode HS", d.get("hsCode")),
    ]))
    out.update(hierarchy_section(d, ["BZA"]))
    out.update(table("Produk Hierarki POV", d.get("_templates"), [
        ("Kode KFA", lambda x: x.get("kfaCode")),
        ("Nama Produk", lambda x: x.get("name")),
    ]))
    out.update(identifier_section("Referensi Identifier Produk Aktual", d.get("identifiers")))
    out.update(identifier_section("Referensi Identifier Produk Virtual", d.get("templateIdentifiers")))
    return out


# ==================================================================== runner
TABS = {
    "varian": dict(list_ep="product-variants", list_row=variant_list, fetch=fetch_variant_detail,
                   parse=variant_parse, out="kfa_produk_varian_full", needs="_packagings"),
    "template": dict(list_ep="product-templates", list_row=template_list, fetch=template_fetch,
                     parse=template_parse, out="kfa_produk_template_full", needs="_variants"),
    "kemasan": dict(list_ep="product-packagings", list_row=packaging_list,
                    fetch=lambda c: detail("product-packagings", c),
                    parse=packaging_parse, out="kfa_produk_kemasan_full", needs="kfaCode"),
    "zat_aktif": dict(list_ep="active-ingredients", list_row=ingredient_list, fetch=ingredient_fetch,
                      parse=ingredient_parse, out="kfa_zat_aktif_full", needs="_templates"),
}


def run_tab(name, cfg, outdir, limit, workers):
    print(f"===== {name} =====", flush=True)
    raw = search_all(cfg["list_ep"], limit=limit, log=True, workers=workers)
    codes = [r.get("kfaCode") for r in raw]
    out = os.path.join(outdir, cfg["out"] if not limit else f"{cfg['out']}_sample{limit}")
    cache_file = os.path.join(outdir, f"{cfg['out']}_detail_cache.jsonl")
    cache = {}
    if os.path.exists(cache_file):
        with open(cache_file, encoding="utf-8") as f:
            for line in f:
                j = json.loads(line)
                if cfg["needs"] in j or "_status" in j:
                    cache[j["kfaCode"]] = j
    todo = [c for c in codes if c not in cache]
    print(f"Detail {name}: {len(codes) - len(todo)} dari cache, {len(todo)} perlu diambil", flush=True)

    def safe(code):
        try:
            d = cfg["fetch"](code)
            return d if d and d.get("kfaCode") else {"_status": "detail tidak ditemukan (404)"}
        except Exception as e:
            print(f"  GAGAL {code}: {e}")
            return None

    failed = []
    with open(cache_file, "a", encoding="utf-8") as f, ThreadPoolExecutor(workers) as ex:
        for n, (code, d) in enumerate(zip(todo, ex.map(safe, todo)), 1):
            if d is None:
                failed.append(code)
            else:
                d["kfaCode"] = code
                cache[code] = d
                f.write(json.dumps(d, ensure_ascii=False) + "\n")
            if n % 200 == 0 or n == len(todo):
                print(f"  detail {name} {n}/{len(todo)}", flush=True)
    if failed:
        print(f"PERHATIAN {name}: {len(failed)} gagal, jalankan ulang untuk mencoba lagi: {failed[:20]}")

    rows, skipped = [], 0
    for r in raw:
        d = cache.get(r.get("kfaCode"))
        if d and "_status" in d:  # detail 404 di website -> tidak dimasukkan
            skipped += 1
            continue
        row = cfg["list_row"](r)
        if d:
            row.update(cfg["parse"](d))
        else:
            row["Status Scrape"] = "gagal"
        rows.append(row)
    df = pd.DataFrame(rows)
    df.to_csv(f"{out}.csv", index=False, encoding="utf-8-sig")
    print(f"Selesai {name}: {len(df)} baris, {len(df.columns)} kolom "
          f"({skipped} dilewati karena 404) -> {out}.csv", flush=True)
    return df


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--tabs", nargs="+", default=list(TABS), choices=list(TABS))
    ap.add_argument("--limit", type=int, default=0, help="Jumlah data per tab (0 = semua)")
    ap.add_argument("--workers", type=int, default=8)
    ap.add_argument("--outdir", default="output")
    args = ap.parse_args()
    os.makedirs(args.outdir, exist_ok=True)
    for t in args.tabs:
        run_tab(t, TABS[t], args.outdir, args.limit, args.workers)


if __name__ == "__main__":
    main()
