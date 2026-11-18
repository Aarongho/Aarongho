#!/usr/bin/env python3
"""
Scrape SEMUA tab KFA Browser (https://satusehat.kemkes.go.id/kfa-browser/farmasi/):
  varian    -> Produk Varian   (/product-variant/<kode>)
  template  -> Produk Template (/product-templates/<kode>)
  kemasan   -> Produk Kemasan  (/packaging-products/<kode>)
  zat_aktif -> Zat Aktif       (/active-substance/<kode>)

Tiap tab menghasilkan satu CSV di folder output/. Hasil detail di-cache (.jsonl),
jadi kalau terputus cukup jalankan ulang dan proses dilanjutkan.

Contoh:
  python scrape_kfa_all.py --limit 10                  # coba 10 data per tab
  python scrape_kfa_all.py --tabs template kemasan     # tab tertentu saja
  python scrape_kfa_all.py                             # semua tab, semua data
"""
import argparse
import json
import os
from concurrent.futures import ThreadPoolExecutor

import pandas as pd

from scrape_kfa import (ATC_LEVELS, fetch_all as fetch_variant_detail, fmt_num,
                        html_to_text, join_unique, parse_detail as parse_variant_detail,
                        parse_fornas, parse_list_row as parse_variant_list_row, post)


# ------------------------------------------------------------------ helpers
def search_all(endpoint, search="", search_by=None, size=100, limit=0, log=False):
    """Ambil semua halaman dari endpoint search/<endpoint>."""
    out, page = [], 1
    while True:
        payload = {"search": search, "page": page, "size": size, "farmalkes_type": "", "sorts": {}}
        if search_by:
            payload["search_by"] = search_by
        res = post(f"search/{endpoint}", payload)
        data, meta = res.get("data") or [], res.get("meta") or {}
        out += data
        if log:
            print(f"  list {endpoint} halaman {page}/{meta.get('totalPage')} -> {len(out)}/{meta.get('totalData')}")
        if not data or page >= (meta.get("totalPage") or 0) or (limit and len(out) >= limit):
            return out[:limit] if limit else out
        page += 1


def yes(v):
    return "Ya" if v else "-"


def names(items):
    return join_unique(i.get("name") for i in items or [])


def hierarchy_cols(d, types):
    out = {}
    for t in types:
        vals = [f"{h.get('kfaCode')} - {h.get('name')}" for h in d.get("hierarchies") or []
                if h.get("type") == t and h.get("kfaCode")]
        out[f"Hierarki {t}"] = "; ".join(vals) or None
    return out


def atc_cols(atcs, rxterm=None):
    atc = {v: [] for v in ATC_LEVELS.values()}
    for a in atcs or []:
        col = ATC_LEVELS.get(str(a.get("level")))
        if col:
            atc[col].append(f"{a.get('code')} - {a.get('name')}")
    out = {c: "; ".join(atc[c]) or None for c in
           ["Substansi Kimia (ATC)", "Kelompok Utama Anatomi", "Subkelompok Terapeutik",
            "Subkelompok Farmakologi", "Subgrup Kimia"]}
    out["Referensi Zat Aktif"] = rxterm or None
    return out


def ingredient_cols(ing):
    ing = ing or []
    return {
        "Zat Aktif": "; ".join(i.get("name") or "" for i in ing) or None,
        "Kekuatan Zat Aktif": "; ".join(i.get("strength") or "" for i in ing) or None,
        "Zat Aktif & Kekuatan": "; ".join(f"{i.get('name')} {i.get('strength')}" for i in ing) or None,
    }


def text_cols(d):
    return {
        "Deskripsi": html_to_text(d.get("description")),
        "Penggunaan": html_to_text(d.get("indication")),
        "Peringatan": html_to_text(d.get("warning")),
        "Efek Samping": html_to_text(d.get("sideEffect")),
    }


def detail(endpoint, code):
    return post(f"detail/{endpoint}", {"kfa_code": code}).get("data") or {}


# ------------------------------------------------------------ Produk Template
def template_list_row(r):
    return {
        "Kode KFA": r.get("kfaCode"),
        "Nama Produk": r.get("name"),
        "Unit Logistik Terkecil": r.get("uomName"),
        "Tipe": (r.get("farmalkesType") or {}).get("name"),
        "Jumlah Produk Varian": r.get("totalVariants"),
        "Fornas": "Ya" if r.get("isFornas") else "Tidak",
    }


def template_fetch(code):
    d = detail("product-templates", code)
    d["_variants"] = search_all("product-variants", code, "template_kfa_code")
    return d


def template_parse(d):
    out = {
        # Informasi Umum
        "Tipe": (d.get("farmalkesType") or {}).get("name"),
        "Unit of Measure (UCUM)": d.get("ucumSymbol"),
        "Bentuk Sediaan": d.get("dosageFormName"),
        "Golongan Obat": d.get("controlledDrugName"),
        "Cara Pemakaian Obat": d.get("routeAdministrationName"),
        # Informasi Dagang
        "HS Code": d.get("hsCode") or None,
    }
    out.update(atc_cols(d.get("atcs"), d.get("rxtermName")))
    out.update(ingredient_cols(d.get("ingredients")))
    out.update(hierarchy_cols(d, ["POV"]))
    # Produk Virtual Info
    out.update(text_cols(d))
    # Referensi Identifier
    out["Referensi Identifier Produk Virtual (Nama)"] = names(d.get("identifiers"))
    # Varian
    v = d.get("_variants") or []
    out["Produk Varian (Kode KFA)"] = "; ".join(x.get("kfaCode") or "" for x in v) or None
    out["Produk Varian (Nama Produk)"] = "; ".join(x.get("name") or "" for x in v) or None
    # Formula Nasional
    out.update(parse_fornas(d.get("fornases")))
    return out


# ------------------------------------------------------------- Produk Kemasan
def packaging_list_row(r):
    return {
        "Kode KFA": r.get("kfaCode"),
        "Nama Produk": r.get("variantDisplayName"),
        "Packaging": r.get("packageName"),
        "Harga Kemasan": fmt_num(r.get("price")) or None,
        "Contained Quantity Type": fmt_num(r.get("qty")) or None,
        "Unit of Measure": r.get("uomName"),
        "Tipe": (r.get("farmalkesType") or {}).get("name"),
    }


def packaging_parse(d):
    out = {
        "Aktif": "Ya" if d.get("isActive") else "Tidak",
        "Isi (Jumlah)": f"{fmt_num(d.get('qty'))} {d.get('uomName') or ''}".strip() or None,
        "Golongan Obat": (d.get("farmalkesType") or {}).get("name") or "-",
        "Kode LKPP": d.get("lkppCode") or "-",
        "Discontinued": yes(d.get("isDiscontinued")),
        "Referensi Identifier (Nama)": names(d.get("identifiers")),
    }
    out.update(hierarchy_cols(d, ["POV", "POA", "POAK"]))
    poa = [h for h in d.get("hierarchies") or [] if h.get("type") == "POA"]
    pov = [h for h in d.get("hierarchies") or [] if h.get("type") == "POV"]
    out["Kode KFA Produk Varian"] = poa[0].get("kfaCode") if poa else None
    out["Kode KFA Produk Template"] = pov[0].get("kfaCode") if pov else None
    return out


# ------------------------------------------------------------------ Zat Aktif
def ingredient_list_row(r):
    return {"Kode KFA": r.get("kfaCode"), "Nama": r.get("name"), "Unit of Measure": r.get("ucumSymbol")}


def ingredient_fetch(code):
    d = detail("active-ingredients", code)
    d["_templates"] = search_all("product-templates", code, "ingredient_kfa_code")
    return d


def ingredient_parse(d):
    weight = d.get("weight")
    t = d.get("_templates") or []
    return {
        # Informasi Umum
        "Generik": yes(d.get("isGeneric")),
        "Tipe": (d.get("farmalkesType") or {}).get("name"),
        "BMHP": yes(d.get("isBmhp")),
        "Unit of Measure (UCUM)": d.get("ucumSymbol"),
        # Informasi Dagang
        "Discontinued": yes(d.get("isDiscontinued")),
        "Nama Dagang": d.get("tradeName") or "-",
        "Unit Logistik Terkecil": d.get("uomName"),
        "Berat Unit Logistik": f"{weight} {d.get('weightUomName') or ''}".strip() if weight not in (None, "") else "-",
        "Harga Eceran Tertinggi": d.get("hetPrice") or "-",
        "Kode HS": d.get("hsCode") or "-",
        # Referensi Identifier
        "Referensi Identifier Produk Aktual (Nama)": names(d.get("identifiers")),
        "Referensi Identifier Produk Virtual (Nama)": names(d.get("templateIdentifiers")),
        # Produk Hierarki (POV = produk template yang memakai zat aktif ini)
        "Jumlah Produk Template": len(t),
        "Produk Template (Kode KFA)": "; ".join(x.get("kfaCode") or "" for x in t) or None,
        "Produk Template (Nama Produk)": "; ".join(x.get("name") or "" for x in t) or None,
    }


# ----------------------------------------------------------------- runner
TABS = {
    "varian": dict(list_ep="product-variants", list_row=parse_variant_list_row,
                   fetch=fetch_variant_detail, parse=parse_variant_detail,
                   out="kfa_produk_varian_full", needs="_packagings"),
    "template": dict(list_ep="product-templates", list_row=template_list_row,
                     fetch=template_fetch, parse=template_parse,
                     out="kfa_produk_template_full", needs="_variants"),
    "kemasan": dict(list_ep="product-packagings", list_row=packaging_list_row,
                    fetch=lambda c: detail("product-packagings", c), parse=packaging_parse,
                    out="kfa_produk_kemasan_full", needs="kfaCode"),
    "zat_aktif": dict(list_ep="active-ingredients", list_row=ingredient_list_row,
                      fetch=ingredient_fetch, parse=ingredient_parse,
                      out="kfa_zat_aktif_full", needs="_templates"),
}


def run_tab(name, cfg, outdir, limit, workers):
    print(f"===== {name} =====")
    rows = [cfg["list_row"](r) for r in search_all(cfg["list_ep"], limit=limit, log=True)]
    out = os.path.join(outdir, cfg["out"] if not limit else f"{cfg['out']}_sample{limit}")
    cache_file = os.path.join(outdir, f"{cfg['out']}_detail_cache.jsonl")
    cache = {}
    if os.path.exists(cache_file):
        with open(cache_file, encoding="utf-8") as f:
            for line in f:
                j = json.loads(line)
                if cfg["needs"] in j or "_status" in j:
                    cache[j["kfaCode"]] = j
    todo = [r["Kode KFA"] for r in rows if r["Kode KFA"] not in cache]
    print(f"Detail {name}: {len(rows) - len(todo)} dari cache, {len(todo)} perlu diambil")

    def safe(code):
        try:
            d = cfg["fetch"](code)
            return d if d else {"_status": "detail tidak ditemukan (404)"}
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

    full = []
    for r in rows:
        d = cache.get(r["Kode KFA"])
        if d and "_status" in d:  # detail 404 di website -> tidak dimasukkan
            print(f"  dilewati {r['Kode KFA']}: {d['_status']}")
            continue
        row = {**r, **cfg["parse"](d)} if d else dict(r)
        row["Status Scrape"] = "gagal" if not d else d.get("_status", "ok")
        full.append(row)
    df = pd.DataFrame(full)
    df.to_csv(f"{out}.csv", index=False, encoding="utf-8-sig")
    print(f"Selesai {name}: {len(df)} baris, {len(df.columns)} kolom -> {out}.csv")
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
